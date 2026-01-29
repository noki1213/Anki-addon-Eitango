from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from anki.notes import Note
from datetime import datetime
import re

# Constants
MODEL_NAME = "Eitango"
CACHE_FIELD = "ExamplesCache"

# -------------------------------------------------------------------------
# 1. Create/update the note type
# -------------------------------------------------------------------------
def create_model_if_needed():
    col = mw.col
    model = col.models.byName(MODEL_NAME)
    
    if not model:
        # Create a new model
        model = col.models.new(MODEL_NAME)
        model['type'] = 1 # 1 = Cloze
        
        # Field definitions
        # ExamplesCache: a field that pre-renders and stores the HTML for mobile
        fields = ["ID", "Word", "Meaning", "Sentence", "Note", CACHE_FIELD]
        for f in fields:
            col.models.addField(model, col.models.newField(f))
            
        # Template
        t = col.models.newTemplate("Eitango Card")
        t['qfmt'] = "{{cloze:Sentence}}"
        t['afmt'] = """
{{Word}}
<div>
{{Meaning}}
<hr>
{{cloze:Sentence}}
</div>
<div>
{{Note}}
</div>
<br>
{{ExamplesCache}}
"""
        col.models.addTemplate(model, t)
        
        # CSS
        model['css'] = """
.card {
 font-family: arial;
 font-size: 20px;
 text-align: left;
 color: black;
 background-color: white;
}
.cloze {
 font-weight: bold;
 color: teal;
}
.nightMode .cloze {
 color: teal;
}

/* Table style */
.example-table {
 width: 100%;
 border-collapse: collapse;
 margin-top: 20px;
 font-size: 0.8em;
 line-height: 1.5;
}
.example-table th, .example-table td {
 border-bottom: 1px solid #ccc;
 padding: 12px 8px;
 text-align: left;
}
.example-table th {
 background-color: #f0f0f0;
 color: #333;
}
.nightMode .example-table th {
 background-color: #333;
 color: #ccc;
}
.nightMode .example-table td {
 border-bottom: 1px solid #444;
}
"""
        col.models.add(model)
    else:
        # Add a field to the existing model (migration)
        flds = [f['name'] for f in model['flds']]
        if CACHE_FIELD not in flds:
            f = col.models.newField(CACHE_FIELD)
            col.models.addField(model, f)
            # The templates need updating too, but since the user may have customized them,
            # Only the field is added here. Template changes need to either be surfaced to the user or forced through.
            # For now, just add the field and leave it at that.

# -------------------------------------------------------------------------
# 2. Auto-fill the ID
# -------------------------------------------------------------------------
def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # Set the ID field (index 0) if it's empty
    if not note.fields[0]:
        note.fields[0] = datetime.now().strftime("%Y%m%d%H%M%S")
        editor.loadNote()

# -------------------------------------------------------------------------
# 3. Cache update logic (the core of mobile support)
# -------------------------------------------------------------------------
_is_updating = False

def update_cache_for_word(word):
    """
    指定された単語を持つ全てのEitangoノートを検索し、
    ExamplesCacheフィールドを一括更新する。
    """
    global _is_updating
    if _is_updating: return # 無限ループ防止
    
    if not word: return

    col = mw.col
    
    # Fetch all notes that share the same word
    # Note: this escaping is a simplified version
    query = f'"note:{MODEL_NAME}" "Word:{word}"'
    nids = col.find_notes(query)
    
    if not nids: return

    # Fetch all the note objects
    notes = [col.get_note(nid) for nid in nids]
    
    # Data collection
    # {nid: {'text': sentence, 'date': date, 'reps': reps}}
    note_data = {}
    
    for note in notes:
        raw_sentence = note['Sentence']
        if not raw_sentence: continue
        
        # Strip cloze-deletion tags
        clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
        
        # Creation date
        created_ts = note.id / 1000
        date_str = datetime.fromtimestamp(created_ts).strftime("%Y/%m/%d")
        
        # Reps
        total_reps = 0
        for c in note.cards():
            total_reps += c.reps
            
        note_data[note.id] = {
            'text': clean_sentence,
            'date': date_str,
            'reps': total_reps
        }
        
    # Update and save the cache field on each note
    _is_updating = True
    try:
        for target_note in notes:
            # Build a list to display everything except itself
            examples = []
            seen_texts = set()
            
            for nid, data in note_data.items():
                if nid == target_note.id: continue # 自分は除外
                
                # Check for duplicates (exclude if it's the same sentence)
                if data['text'] in seen_texts: continue
                seen_texts.add(data['text'])
                
                examples.append(data)
            
            # Generate the HTML
            if examples:
                html = "<table class='example-table'>"
                html += "<tr><th>Sentence</th><th>Date</th><th>Reps</th></tr>"
                for ex in examples:
                    html += f"<tr><td>{ex['text']}</td><td>{ex['date']}</td><td>{ex['reps']}</td></tr>"
                html += "</table>"
            else:
                html = "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"
            
            # Only save when something actually changed (avoids pointless writes)
            if target_note[CACHE_FIELD] != html:
                target_note[CACHE_FIELD] = html
                col.update_note(target_note) # ここで保存！
                
    finally:
        _is_updating = False

def on_editor_unfocus(changed, note, current_field_idx):
    """
    エディタでフィールドからフォーカスが外れたときに呼ばれる
    """
    if not changed: return
    if note.model()['name'] != MODEL_NAME: return
    
    # Check whether the field that changed was "Word"
    # note.fields is just a list of values, so match by index
    # Get the model's field list
    flds = [f['name'] for f in note.model()['flds']]
    if current_field_idx < len(flds) and flds[current_field_idx] == "Word":
        # The Word field changed, so run the cache update
        word = note.fields[current_field_idx]
        # Whether to delay this slightly or just run it right away — here we run it directly.
        # Note: calling col.update_note inside update_cache_for_word
        # This could conflict with the note currently open in the editor, so
        # Need to make sure the target is never the note itself.
        update_cache_for_word(word)

# -------------------------------------------------------------------------
# 4. Manual update action (for debugging and bulk updates)
# -------------------------------------------------------------------------
def update_all_cache():
    """
    全てのEitangoノートのキャッシュを強制的に更新する
    """
    col = mw.col
    # Fetch all Eitango notes
    nids = col.find_notes(f'"note:{MODEL_NAME}"')
    if not nids:
        showInfo("Eitangoノートが見つかりませんでした。")
        return

    # Group note IDs by word
    word_to_nids = {}
    for nid in nids:
        note = col.get_note(nid)
        word = note['Word']
        if not word: continue
        
        if word not in word_to_nids:
            word_to_nids[word] = []
        word_to_nids[word].append(nid)
    
    # Progress bar (simple)
    mw.progress.start(immediate=True)
    count = 0
    total = len(word_to_nids)
    
    try:
        for i, (word, target_nids) in enumerate(word_to_nids.items()):
            mw.progress.update(label=f"Updating: {word}", value=i, max=total)
            
            # Collect the data for this word's group
            group_data = []
            for nid in target_nids:
                note = col.get_note(nid)
                raw_sentence = note['Sentence']
                if not raw_sentence: continue
                
                # Strip the cloze deletion
                clean = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
                
                # Date
                ts = note.id / 1000
                dt = datetime.fromtimestamp(ts).strftime("%Y/%m/%d")
                
                # Reps
                reps = 0
                for c in note.cards():
                    reps += c.reps
                
                group_data.append({
                    'nid': nid,
                    'text': clean,
                    'date': dt,
                    'reps': reps
                })
            
            # Write to each note
            for nid in target_nids:
                note = col.get_note(nid)
                
                # List everything except itself
                examples = [d for d in group_data if d['nid'] != nid]
                
                # Generate the HTML
                if examples:
                    # De-duplicate (by text)
                    unique_ex = []
                    seen = set()
                    for ex in examples:
                        if ex['text'] not in seen:
                            seen.add(ex['text'])
                            unique_ex.append(ex)
                    
                    if unique_ex:
                        html = "<table class='example-table'>"
                        html += "<tr><th>Sentence</th><th>Date</th><th>Reps</th></tr>"
                        for ex in unique_ex:
                            html += f"<tr><td>{ex['text']}</td><td>{ex['date']}</td><td>{ex['reps']}</td></tr>"
                        html += "</table>"
                    else:
                         html = "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"
                else:
                    html = "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"
                
                if note[CACHE_FIELD] != html:
                    note[CACHE_FIELD] = html
                    col.update_note(note)
                    count += 1
                    
    finally:
        mw.progress.finish()
        
    showInfo(f"更新完了: {count} 件のノートを更新しました。")

# -------------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.editor_did_unfocus_field.append(on_editor_unfocus)
    
    # Add to the menu
    action = QAction("Update Eitango Examples", mw)
    qconnect(action.triggered, update_all_cache)
    mw.form.menuTools.addAction(action)

# Run when Anki starts
gui_hooks.profile_did_open.append(init_addon)

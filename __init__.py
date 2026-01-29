from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from datetime import datetime
import re

# Constants
MODEL_NAME = "Eitango"
CONF_NAME = "Eitango Addon"

# -------------------------------------------------------------------------
# 1. Create the note type (first launch only)
# -------------------------------------------------------------------------
def create_model_if_needed():
    col = mw.col
    model = col.models.byName(MODEL_NAME)
    
    if not model:
        # Create it as a Cloze (fill-in-the-blank) type
        model = col.models.new(MODEL_NAME)
        model['type'] = 1 # 1 = Cloze
        
        # Field definitions
        # Putting the ID first lets notes with the same Word still be added
        fields = ["ID", "Word", "Meaning", "Sentence"]
        for f in fields:
            col.models.addField(model, col.models.newField(f))
            
        # Define the templates (card design)
        t = col.models.newTemplate("Eitango Card")
        t['qfmt'] = "{{cloze:Sentence}}" # 表面: 穴埋め問題
        t['afmt'] = """
{{Word}}
<div>
{{Meaning}}
<hr>
{{cloze:Sentence}}
</div>
<br>
<div id='other-examples' style='text-align: left; font-size: 16px;'></div>
"""
        col.models.addTemplate(model, t)
        
        # CSS settings
        model['css'] = """
.card {
 font-family: arial;
 font-size: 20px;
 text-align: center;
 color: black;
 background-color: white;
}
.cloze {
 font-weight: bold;
 color: blue;
}
.nightMode .cloze {
 color: lightblue;
}
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
        print(f"モデル '{MODEL_NAME}' を作成しました。")
    else:
        # Skipping field checks against an existing model for now
        pass

# -------------------------------------------------------------------------
# 2. Auto-fill the ID
# -------------------------------------------------------------------------
def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # Set the ID field (index 0) if it's empty
    if not note.fields[0]:
        # YYYYMMDDHHMMSS format (e.g. 20260129183500)
        note.fields[0] = datetime.now().strftime("%Y%m%d%H%M%S")
        editor.loadNote()

# -------------------------------------------------------------------------
# 3. Show the other example sentences when the answer is revealed
# -------------------------------------------------------------------------
def on_show_answer(card):
    # Check whether the current card is an Eitango model
    note = card.note()
    if note.model()['name'] != MODEL_NAME:
        return
    
    word_field = note['Word']
    current_id = note['ID']
    
    if not word_field:
        return

    try:
        # 1. Split the words on commas
        words = [w.strip() for w in word_field.split(',') if w.strip()]
        
        if not words:
            return
            
        # 2. Build the search query
        # note:Eitango ("Word:*word1*" OR "Word:*word2*")
        # Using a wildcard (*) so it matches whenever any part of a field contains the word
        or_conditions = " OR ".join([f'"Word:*{w}*"' for w in words])
        query = f'"note:{MODEL_NAME}" ({or_conditions})'
        
        found_nids = mw.col.find_notes(query)
        
        examples = []
        for nid in found_nids:
            # Exclude itself (comparing by internal ID is the reliable way)
            if nid == note.id:
                continue

            other_note = mw.col.get_note(nid)
            
            # Check for duplicates via the ID field (just to be safe)
            if other_note['ID'] == current_id:
                continue

            raw_sentence = other_note['Sentence']
            if not raw_sentence:
                continue
                
            # Strip the cloze-deletion tags
            clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
            
            # -------------------------------------------------
            # Get info from Anki's system data
            # -------------------------------------------------
            
            # 1. Creation timestamp (note.id is the millisecond timestamp from when it was created)
            created_ts = other_note.id / 1000
            dt = datetime.fromtimestamp(created_ts)
            date_str = dt.strftime("%Y/%m/%d") # シンプルに日付だけにする（時刻は煩雑かも）
            
            # 2. Review count (pulled from the card info)
            # Fetch all cards linked to the note (usually just one, but Cloze notes can have several)
            cards = other_note.cards()
            total_reps = 0
            if cards:
                # Total review count across the notes shown as example sentences (summed per card)
                for c in cards:
                    total_reps += c.reps

            # String used for display
            info_str = f" <span style='font-size: 0.8em; color: gray;'>({date_str}, {total_reps} reps)</span>"
            
            # De-duplication: judge by the sentence alone, or by the sentence plus its extra info
            # Here we just skip displaying it when the sentence itself matches (kept simple)
            # If we ever want to also show identical sentences from a different date, check full_text instead
            full_text = clean_sentence + info_str
            
            # Check whether the existing list already has this content
            if not any(ex['text'] == clean_sentence for ex in examples):
                examples.append({
                    'text': clean_sentence,
                    'date': date_str,
                    'reps': total_reps
                })
        
        if examples:
            # Build the HTML table
            list_html = "<strong>Other Examples:</strong><table class='example-table'>"
            list_html += "<tr><th>Sentence</th><th>Date</th><th>Reps</th></tr>"
            for ex in examples:
                list_html += f"<tr><td>{ex['text']}</td><td>{ex['date']}</td><td>{ex['reps']}</td></tr>"
            list_html += "</table>"
            
            # Escaping
            list_html_js = list_html.replace("'", "\\'").replace("\n", "")
            
            js = f"""
            var div = document.getElementById('other-examples');
            if (div) {{
                div.innerHTML = '{list_html_js}';
            }}
            """
            mw.reviewer.web.eval(js)
        else:
            js = "var div = document.getElementById('other-examples'); if(div) { div.innerHTML = 'No other examples found.'; }"
            mw.reviewer.web.eval(js)

    except Exception as e:
        print(f"Error in Eitango addon: {str(e)}")

# -------------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)

# Run when Anki starts
gui_hooks.profile_did_open.append(init_addon)
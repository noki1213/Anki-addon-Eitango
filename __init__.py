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
{{cloze:Sentence}}
<hr>
<div style='font-size: 20px; font-weight: bold;'>{{Word}}</div>
<div style='color: gray;'>{{Meaning}}</div>
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
ul {
 padding-left: 20px;
}
li {
 margin-bottom: 5px;
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
    
    word = note['Word']
    current_id = note['ID']
    
    if not word:
        return

    # Search for other notes with the same word
    # note:Eitango "Word:xxxxx"
    # Escaping: if there's a double quote we'd need to handle it, e.g. by wrapping in single quotes, but
    # Handled in a simplified way here
    query = f'"note:{MODEL_NAME}" "Word:{word}"'
    found_nids = mw.col.find_notes(query)
    
    examples = []
    for nid in found_nids:
        other_note = mw.col.get_note(nid)
        
        # Exclude itself
        if other_note['ID'] == current_id:
            continue
            
        raw_sentence = other_note['Sentence']
        if not raw_sentence:
            continue
            
        # Strip the cloze-deletion tags: {{c1::answer::hint}} -> answer
        # A simple regex
        clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
        examples.append(clean_sentence)
    
    if examples:
        # Build the HTML list
        list_html = "<strong>Other Examples:</strong><ul>"
        for ex in examples:
            list_html += f"<li>{ex}</li>"
        list_html += "</ul>"
        
        # Escaping (make it safe as a JavaScript string)
        list_html_js = list_html.replace("'", "\\'").replace("\n", "")
        
        # Run JavaScript to rewrite the DOM
        js = f"""
        var div = document.getElementById('other-examples');
        if (div) {{
            div.innerHTML = '{list_html_js}';
        }}
        """
        mw.reviewer.web.eval(js)
    else:
        # If there are no example sentences
        js = "var div = document.getElementById('other-examples'); if(div) { div.innerHTML = 'No other examples found.'; }"
        mw.reviewer.web.eval(js)

# -------------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)

# Run when Anki starts
gui_hooks.profile_did_open.append(init_addon)
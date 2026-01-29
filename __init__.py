from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from anki.hooks import addHook
import time

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
<div id='other-examples'></div>
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
"""
        col.models.add(model)
        print(f"モデル '{MODEL_NAME}' を作成しました。")
    else:
        # Skipping field checks against an existing model for now
        pass

# -------------------------------------------------------------------------
# 2. Auto-fill the ID
# -------------------------------------------------------------------------
def on_editor_did_init(editor):
    # Fill the ID field when the editor opens, if it's empty
    # Note: assumes this runs when adding a new note
    note = editor.note
    if note is None:
        return
        
    if note.model()['name'] != MODEL_NAME:
        return

    # Fill the ID field (index 0) with a timestamp if it's empty
    if not note.fields[0]:
        # Unique ID in milliseconds
        unique_id = str(int(time.time() * 1000))
        note.fields[0] = unique_id
        editor.loadNote() # UIに反映

# Rather than hooking every time the Add window opens,
# It's safer to assign the ID at the point a new note gets set, etc.
# The usual choice here would be gui_hooks.editor_did_init_shortcuts, but
# Just use editor_did_load_note, kept simple
from aqt import gui_hooks

def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # Set the ID field (index 0) if it's empty
    if not note.fields[0]:
        note.fields[0] = str(int(time.time() * 1000))
        editor.loadNote()

# -------------------------------------------------------------------------
# Initialization
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)

# Run when Anki starts
from aqt import gui_hooks
gui_hooks.profile_did_open.append(init_addon)
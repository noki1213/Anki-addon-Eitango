from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from anki.notes import Note
from datetime import datetime, timedelta
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
		fields = ["Head", "Usage", "Phrase", "Note", CACHE_FIELD]
		for f in fields:
			col.models.addField(model, col.models.newField(f))

		# Template
		t = col.models.newTemplate("Eitango Card")
		t['qfmt'] = "{{cloze:Phrase}}"
		t['afmt'] = """
{{Head}}
<div>
{{Usage}}
<hr>
{{cloze:Phrase}}
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
/* Style for clickable rows */
.example-table tr:not(:first-child) {
 cursor: pointer;
 transition: background-color 0.1s;
}
.example-table tr:not(:first-child):hover {
 background-color: #e8f0fe;
}
.nightMode .example-table tr:not(:first-child):hover {
 background-color: #444;
}
"""
		col.models.add(model)
	else:
		# Add a field to the existing model (only if ExamplesCache is missing)
		flds = [f['name'] for f in model['flds']]
		if CACHE_FIELD not in flds:
			f = col.models.newField(CACHE_FIELD)
			col.models.addField(model, f)

# -------------------------------------------------------------------------
# 2. Shared logic: parse multiple Heads, gather the other example-sentence data, and generate the HTML
# -------------------------------------------------------------------------
def parse_words(head_field):
	"""
	Headフィールドをカンマ区切りで分割し、単語リストを返す
	例: "tell, inform" -> ["tell", "inform"]
	"""
	if not head_field:
		return []
	return [w.strip() for w in head_field.split(',') if w.strip()]

def get_examples_html(words, current_nid):
	"""
	指定された単語リストのいずれかを含む他のノートから情報を集め、HTMLテーブルを生成する
	words: list of str（Headフィールドをカンマ分割したリスト）
	"""
	if not words:
		return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

	col = mw.col
	# Fetch all Eitango notes and check for a match on the Python side
	all_nids = col.find_notes(f'"note:{MODEL_NAME}"')

	# Compare case-insensitively
	words_set = set(w.lower() for w in words)

	group_data = []
	seen_texts = set()

	for nid in all_nids:
		if nid == current_nid:
			continue

		note = col.get_note(nid)
		note_words = parse_words(note['Head'])
		note_words_set = set(w.lower() for w in note_words)

		# Check whether there's a shared Head
		if not (words_set & note_words_set):
			continue

		raw_phrase = note['Phrase']
		if not raw_phrase:
			continue

		# Strip cloze-deletion tags
		clean = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_phrase)

		# De-duplicate
		if clean in seen_texts:
			continue
		seen_texts.add(clean)

		group_data.append({
			'nid': nid,
			'phrase': clean,
			'usage': note['Usage'],
		})

	if group_data:
		html = "<table class='example-table'>"
		html += "<tr><th>Phrase</th><th>Usage</th></tr>"
		for d in group_data:
			# Command to open the Browser on click
			onclick = f"onclick=\"pycmd('eitango_open:{d['nid']}');\""
			html += f"<tr {onclick}><td>{d['phrase']}</td><td>{d['usage']}</td></tr>"
		html += "</table>"
		return html
	else:
		return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

# -------------------------------------------------------------------------
# 3. Cache update logic
# -------------------------------------------------------------------------
_is_updating = False

def update_cache_for_words(words):
	"""
	指定された単語リストのいずれかを含む全ノートのキャッシュを更新する
	"""
	global _is_updating
	if _is_updating or not words: return

	col = mw.col
	all_nids = col.find_notes(f'"note:{MODEL_NAME}"')
	words_set = set(w.lower() for w in words)

	# Narrow down to the related notes
	related_nids = []
	for nid in all_nids:
		note = col.get_note(nid)
		note_words = parse_words(note['Head'])
		note_words_set = set(w.lower() for w in note_words)
		if words_set & note_words_set:
			related_nids.append(nid)

	_is_updating = True
	try:
		for nid in related_nids:
			note = col.get_note(nid)
			note_words = parse_words(note['Head'])
			html = get_examples_html(note_words, nid)
			if note[CACHE_FIELD] != html:
				note[CACHE_FIELD] = html
				col.update_note(note)
	finally:
		_is_updating = False

def on_editor_unfocus(changed, note, current_field_idx):
	if not changed or note.model()['name'] != MODEL_NAME: return
	flds = [f['name'] for f in note.model()['flds']]
	if current_field_idx < len(flds) and flds[current_field_idx] == "Head":
		words = parse_words(note.fields[current_field_idx])
		update_cache_for_words(words)

# -------------------------------------------------------------------------
# 4. Manual update action
# -------------------------------------------------------------------------
def update_all_cache():
	col = mw.col
	nids = col.find_notes(f'"note:{MODEL_NAME}"')
	if not nids:
		showInfo("Eitangoノートが見つかりませんでした。")
		return

	mw.progress.start(immediate=True)
	count = 0
	try:
		total = len(nids)
		for i, nid in enumerate(nids):
			note = col.get_note(nid)
			words = parse_words(note['Head'])
			mw.progress.update(label=f"Updating: {note['Head']}", value=i, max=total)
			html = get_examples_html(words, nid)
			# Force an update
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
	gui_hooks.editor_did_unfocus_field.append(on_editor_unfocus)

	action = QAction("Update Eitango Examples", mw)
	qconnect(action.triggered, update_all_cache)
	mw.form.menuTools.addAction(action)

# -------------------------------------------------------------------------
# 5. Handle click events
# -------------------------------------------------------------------------
def on_js_message(handled, message, context):
	"""
	JSからのメッセージ (pycmd) を処理する
	"""
	if not message.startswith("eitango_open:"):
		return handled

	nid_str = message.split(":")[1]

	try:
		import aqt
		nid = int(nid_str)

		# Open the Browser and search for/display that note
		browser = aqt.dialogs.open("Browser", mw)
		browser.search_for(f"nid:{nid}")

		return (True, None)
	except Exception as e:
		tooltip(f"Error opening browser: {str(e)}")
		return handled

# Run when Anki starts
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.profile_did_open.append(init_addon)

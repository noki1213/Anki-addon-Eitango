from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from anki.notes import Note
from datetime import datetime, timedelta
import re

# 定数
MODEL_NAME = "Eitango"
CACHE_FIELD = "ExamplesCache"

# CSSバージョン（変更のたびにここを更新するとAnkiに反映される）
CSS_VERSION = "v5"

CARD_CSS = """
/* Base Card Style — 影付き＋薄い背景色レイアウト */
.card {
	font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
	font-size: 18px;
	text-align: left;
	color: #333333;
	background-color: #ffffff;
	margin: 20px;
	line-height: 1.6;
}

.nightMode .card {
	background-color: #2C2C2C;
	color: #e0e0e0;
}

/* Typography & Cloze */
.cloze {
	font-weight: 700;
	color: #1fa291;
	background-color: rgba(31, 162, 145, 0.1);
	padding: 2px 6px;
	border-radius: 4px;
}

.nightMode .cloze {
	color: #5bc1b4;
	background-color: rgba(91, 193, 180, 0.15);
}

/* フィールド共通（影付き丸角ボックス） */
.field {
	margin-bottom: 12px;
	padding: 12px 15px;
	border-radius: 10px;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}
.field:last-child {
	margin-bottom: 0;
}

.nightMode .field {
	box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
}

/* フィールドヘッダー（ラベル＋音声ボタン横並び） */
.field-header {
	display: flex;
	align-items: center;
	gap: 8px;
	margin-bottom: 8px;
}

/* ラベル */
.field-label {
	font-size: 0.7em;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 1px;
	margin-bottom: 8px;
}

/* ヘッダー内のラベルは margin-bottom なし */
.field-header .field-label {
	margin-bottom: 0;
}

/* フィールドコンテンツ */
.field-content {
	font-size: 1.05em;
	line-height: 1.6;
}

/* Note フィールドは少し小さく */
.note-field .field-content {
	font-size: 0.92em;
}

/* 音声ボタン */
.field-audio {
	flex-shrink: 0;
}
.field-audio .replay-button svg {
	width: 20px !important;
	height: 20px !important;
}

/* Usage */
.usage-field    { background: rgba(255, 109, 124, 0.14); }
.usage-label    { color: #FF6D7C; }
.nightMode .usage-label { color: #ff8a96; }

/* Phrase */
.phrase-field   { background: rgba(91, 193, 180, 0.14); }
.phrase-label   { color: #3b968a; }
.nightMode .phrase-label { color: #5bc1b4; }

/* Sentence */
.sentence-field { background: rgba(96, 165, 250, 0.14); }
.sentence-label { color: #3b82f6; }
.nightMode .sentence-label { color: #60a5fa; }

/* Note */
.note-field     { background: rgba(156, 163, 175, 0.10); }
.note-label     { color: #6b7280; }
.nightMode .note-label { color: #9ca3af; }

/* 画像 */
.image-box {
	margin-top: 16px;
	text-align: center;
}
.image-box img {
	max-width: 100%;
	border-radius: 8px;
}

/* Example Table Styles */
.example-table {
	width: 100%;
	border-collapse: collapse;
	margin-top: 24px;
	font-size: 0.85em;
	line-height: 1.5;
	background-color: #f8fafc;
	border-radius: 8px;
	overflow: hidden;
}

.nightMode .example-table {
	background-color: rgba(255, 255, 255, 0.03);
}

.example-table th, .example-table td {
	border-bottom: 1px solid #e2e8f0;
	padding: 12px 14px;
	text-align: left;
}

.example-table th {
	background-color: #e2e8f0;
	color: #475569;
}

.nightMode .example-table th {
	background-color: rgba(255, 255, 255, 0.1);
	color: #e0e0e0;
	border-bottom: 1px solid #444;
}

.nightMode .example-table td {
	border-bottom: 1px solid #444;
}

.example-table tr:not(:first-child) {
	cursor: pointer;
	transition: background-color 0.1s;
}

.example-table tr:not(:first-child):hover {
	background-color: #cbd5e1;
}

.nightMode .example-table tr:not(:first-child):hover {
	background-color: rgba(255, 255, 255, 0.08);
}

/* アコーディオンセクション */ /* eitango-css-version: v5 */
.eitango-examples {
	margin-top: 16px;
}
.eitango-section {
	margin-top: 4px;
}
.eitango-section > summary {
	cursor: pointer;
	font-size: 0.85em;
	font-weight: bold;
	color: #555;
	padding: 4px 0;
	user-select: none;
	list-style: none;
}
.eitango-section > summary::-webkit-details-marker {
	display: none;
}
.eitango-section[open] > summary::before {
	content: '▼ ';
}
.eitango-section:not([open]) > summary::before {
	content: '▶ ';
}
.eitango-count {
	color: #aaa;
	font-weight: normal;
}
.nightMode .eitango-section > summary {
	color: #aaa;
}
"""

# カードテンプレート（表面）
CARD_FRONT = """<div class="field phrase-field">
	<div class="field-label phrase-label">Phrase</div>
	<div class="field-content">
		{{cloze:Phrase}}
	</div>
</div>"""

# カードテンプレート（裏面）
CARD_BACK = """{{#Usage}}
<div class="field usage-field">
	<div class="field-header">
		<div class="field-label usage-label">Usage</div>
		{{#UsageAudio}}<div class="field-audio">{{UsageAudio}}</div>{{/UsageAudio}}
	</div>
	<div class="field-content">{{Usage}}</div>
</div>
{{/Usage}}

<div class="field phrase-field">
	<div class="field-header">
		<div class="field-label phrase-label">Phrase</div>
		<div class="field-audio">{{PhraseAudio}}</div>
	</div>
	<div class="field-content">
		{{cloze:Phrase}}
	</div>
</div>

{{#Sentence}}
<div class="field sentence-field">
	<div class="field-label sentence-label">Sentence</div>
	<div class="field-content">{{Sentence}}</div>
</div>
{{/Sentence}}

{{#Note}}
<div class="field note-field">
	<div class="field-label note-label">Note</div>
	<div class="field-content">{{Note}}</div>
</div>
{{/Note}}

{{#Image}}
<div class="image-box">
	{{Image}}
</div>
{{/Image}}

{{#ExamplesCache}}
<div class="examples-box">
	{{ExamplesCache}}
</div>
{{/ExamplesCache}}"""

# -------------------------------------------------------------------------
# 1. ノートタイプの作成・更新
# -------------------------------------------------------------------------
def create_model_if_needed():
	col = mw.col
	model = col.models.byName(MODEL_NAME)

	if not model:
		# モデル新規作成
		model = col.models.new(MODEL_NAME)
		model['type'] = 1 # 1 = Cloze

		# フィールド定義
		fields = ["Link", "Usage", "Phrase", "Note", CACHE_FIELD]
		for f in fields:
			col.models.addField(model, col.models.newField(f))

		# テンプレート
		t = col.models.newTemplate("Eitango Card")
		t['qfmt'] = "{{cloze:Phrase}}"
		t['afmt'] = """
{{Link}}
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
		model['css'] = CARD_CSS
		col.models.add(model)
	else:
		# 既存モデルへのフィールド追加（ExamplesCacheがない場合のみ）
		flds = [f['name'] for f in model['flds']]
		if CACHE_FIELD not in flds:
			f = col.models.newField(CACHE_FIELD)
			col.models.addField(model, f)

		# CSSバージョンが古ければCSS・HTMLテンプレートを更新
		if f"eitango-css-version: {CSS_VERSION}" not in model['css']:
			model['css'] = CARD_CSS
			tmpl = model['tmpls'][0]
			tmpl['qfmt'] = CARD_FRONT
			tmpl['afmt'] = CARD_BACK
			col.models.save(model)

# -------------------------------------------------------------------------
# 2. 共通ロジック: 複数Linkの解析、他の例文データ収集とHTML生成
# -------------------------------------------------------------------------
def parse_words(head_field):
	"""
	Linkフィールドをカンマ区切りで分割し、単語リストを返す
	例: "tell, inform" -> ["tell", "inform"]
	"""
	if not head_field:
		return []
	return [w.strip() for w in head_field.split(',') if w.strip()]

def get_examples_html(words, current_nid):
	"""
	Linkワードごとにアコーディオンセクションを生成する。
	各セクションは ▼ word (件数) のヘッダーで開閉できる。
	"""
	if not words:
		return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

	col = mw.col
	all_nids = col.find_notes(f'"note:{MODEL_NAME}"')

	# ワードごとにグループ化
	groups = {w: [] for w in words}
	seen_per_word = {w: set() for w in words}

	for nid in all_nids:
		if nid == current_nid:
			continue

		note = col.get_note(nid)
		note_words = parse_words(note['Link'])
		note_words_lower = set(w.lower() for w in note_words)

		raw_phrase = note['Phrase']
		if not raw_phrase:
			continue

		# 穴埋めタグ除去
		clean = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_phrase)

		# 各ワードのグループに追加（重複排除）
		for w in words:
			if w.lower() in note_words_lower:
				if clean not in seen_per_word[w]:
					seen_per_word[w].add(clean)
					groups[w].append({
						'nid': nid,
						'phrase': clean,
						'usage': note['Usage'],
					})

	# 全グループが空ならメッセージ表示
	if not any(groups[w] for w in words):
		return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

	html = "<div class='eitango-examples'>"
	for w in words:
		data = groups[w]
		if not data:
			continue
		count = len(data)
		html += f"<details open class='eitango-section'>"
		html += f"<summary>{w} <span class='eitango-count'>({count})</span></summary>"
		html += "<table class='example-table'>"
		html += "<tr><th>Usage</th><th>Phrase</th></tr>"
		for d in data:
			onclick = f"onclick=\"pycmd('eitango_open:{d['nid']}');\""
			html += f"<tr {onclick}><td>{d['usage']}</td><td>{d['phrase']}</td></tr>"
		html += "</table>"
		html += "</details>"
	html += "</div>"
	return html

# -------------------------------------------------------------------------
# 3. キャッシュ更新ロジック
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

	# 関連するノートを絞り込む
	related_nids = []
	for nid in all_nids:
		note = col.get_note(nid)
		note_words = parse_words(note['Link'])
		note_words_set = set(w.lower() for w in note_words)
		if words_set & note_words_set:
			related_nids.append(nid)

	_is_updating = True
	try:
		for nid in related_nids:
			note = col.get_note(nid)
			note_words = parse_words(note['Link'])
			html = get_examples_html(note_words, nid)
			if note[CACHE_FIELD] != html:
				note[CACHE_FIELD] = html
				col.update_note(note)
	finally:
		_is_updating = False

def on_editor_unfocus(changed, note, current_field_idx):
	if not changed or note.model()['name'] != MODEL_NAME: return
	flds = [f['name'] for f in note.model()['flds']]
	if current_field_idx < len(flds) and flds[current_field_idx] == "Link":
		words = parse_words(note.fields[current_field_idx])
		update_cache_for_words(words)

# -------------------------------------------------------------------------
# 4. 手動更新アクション
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
			words = parse_words(note['Link'])
			mw.progress.update(label=f"Updating: {note['Link']}", value=i, max=total)
			html = get_examples_html(words, nid)
			# 強制的に更新
			note[CACHE_FIELD] = html
			col.update_note(note)
			count += 1
	finally:
		mw.progress.finish()

	showInfo(f"更新完了: {count} 件のノートを更新しました。")

# -------------------------------------------------------------------------
# 初期化処理
# -------------------------------------------------------------------------
def init_addon():
	create_model_if_needed()
	gui_hooks.editor_did_unfocus_field.append(on_editor_unfocus)

	action = QAction("Update Eitango Examples", mw)
	qconnect(action.triggered, update_all_cache)
	mw.form.menuTools.addAction(action)

# -------------------------------------------------------------------------
# 5. クリックイベントのハンドリング
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

		# ブラウザを開いてそのノートを検索・表示
		browser = aqt.dialogs.open("Browser", mw)
		browser.search_for(f"nid:{nid}")

		return (True, None)
	except Exception as e:
		tooltip(f"Error opening browser: {str(e)}")
		return handled

# Anki起動時に実行
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.profile_did_open.append(init_addon)

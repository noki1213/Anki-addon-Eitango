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
        fields = ["ID", "Word", "Meaning", "Sentence", "Note", CACHE_FIELD]
        for f in fields:
            col.models.addField(model, col.models.newField(f))
            
        # テンプレート
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

/* 表のスタイル */
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
        # 既存モデルへのフィールド追加（マイグレーション）
        flds = [f['name'] for f in model['flds']]
        if CACHE_FIELD not in flds:
            f = col.models.newField(CACHE_FIELD)
            col.models.addField(model, f)

# -------------------------------------------------------------------------
# 2. 共通ロジック: 他の例文データの収集とHTML生成
# -------------------------------------------------------------------------
def get_examples_html(word, current_nid):
    """
    指定された単語を持つ他のノートから情報を集め、HTMLテーブルを生成する
    """
    col = mw.col
    query = f'"note:{MODEL_NAME}" "Word:{word}"'
    nids = col.find_notes(query)
    
    if not nids:
        return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

    group_data = []
    seen_texts = set()

    for nid in nids:
        if nid == current_nid:
            continue
            
        note = col.get_note(nid)
        raw_sentence = note['Sentence']
        if not raw_sentence: continue
        
        # 穴埋めタグ除去
        clean = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
        
        # 重複排除
        if clean in seen_texts: continue
        seen_texts.add(clean)
        
        # 1. Created (作成日)
        ts = note.id / 1000
        created_str = datetime.fromtimestamp(ts).strftime("%Y/%m/%d")
        
        # 2. Reps (学習回数) & Due (期限)
        total_reps = 0
        due_dates = []
        
        for c in note.cards():
            total_reps += c.reps
            if c.type == 0: due_dates.append("New")
            elif c.type in (1, 3): due_dates.append("Learning")
            elif c.type == 2:
                days_diff = c.due - mw.col.sched.today
                if days_diff <= 0: due_dates.append("Due")
                else:
                    due_dt = datetime.now() + timedelta(days=days_diff)
                    due_dates.append(due_dt.strftime("%Y/%m/%d"))
        
        primary_due = "None"
        if due_dates:
            if "Due" in due_dates: primary_due = "Due"
            elif "Learning" in due_dates: primary_due = "Learning"
            else:
                dts = [d for d in due_dates if d not in ("New", "Learning", "Due")]
                primary_due = min(dts) if dts else "New"

        group_data.append({
            'text': clean,
            'created': created_str,
            'reps': total_reps,
            'due': primary_due
        })

    if group_data:
        html = "<table class='example-table'>"
        html += "<tr><th>Sentence</th><th>Created</th><th>Reps</th><th>Due</th></tr>"
        for d in group_data:
            html += f"<tr><td>{d['text']}</td><td>{d['created']}</td><td>{d['reps']}</td><td>{d['due']}</td></tr>"
        html += "</table>"
        return html
    else:
        return "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"

# -------------------------------------------------------------------------
# 3. キャッシュ更新ロジック
# -------------------------------------------------------------------------
_is_updating = False

def update_cache_for_word(word):
    global _is_updating
    if _is_updating or not word: return
    
    col = mw.col
    query = f'"note:{MODEL_NAME}" "Word:{word}"'
    nids = col.find_notes(query)
    
    _is_updating = True
    try:
        for nid in nids:
            note = col.get_note(nid)
            html = get_examples_html(word, nid)
            if note[CACHE_FIELD] != html:
                note[CACHE_FIELD] = html
                col.update_note(note)
    finally:
        _is_updating = False

def setup_id(editor):
    note = editor.note
    if not note or note.model()['name'] != MODEL_NAME: return
    if not note.fields[0]:
        note.fields[0] = datetime.now().strftime("%Y%m%d%H%M%S")
        editor.loadNote()

def on_editor_unfocus(changed, note, current_field_idx):
    if not changed or note.model()['name'] != MODEL_NAME: return
    flds = [f['name'] for f in note.model()['flds']]
    if current_field_idx < len(flds) and flds[current_field_idx] == "Word":
        update_cache_for_word(note.fields[current_field_idx])

# -------------------------------------------------------------------------
# 4. 手動更新アクション
# -------------------------------------------------------------------------
def update_all_cache():
    col = mw.col
    nids = col.find_notes(f'"note:{MODEL_NAME}"')
    if not nids:
        showInfo("Eitangoノートが見つかりませんでした。")
        return

    # 単語ごとにノートを分類
    word_map = {}
    for nid in nids:
        word = col.get_note(nid)['Word']
        if word:
            if word not in word_map: word_map[word] = []
            word_map[word].append(nid)
    
    mw.progress.start(immediate=True)
    count = 0
    try:
        total = len(word_map)
        for i, (word, group_nids) in enumerate(word_map.items()):
            mw.progress.update(label=f"Updating: {word}", value=i, max=total)
            for nid in group_nids:
                note = col.get_note(nid)
                html = get_examples_html(word, nid)
                if note[CACHE_FIELD] != html:
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
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.editor_did_unfocus_field.append(on_editor_unfocus)
    
    action = QAction("Update Eitango Examples", mw)
    qconnect(action.triggered, update_all_cache)
    mw.form.menuTools.addAction(action)

gui_hooks.profile_did_open.append(init_addon)
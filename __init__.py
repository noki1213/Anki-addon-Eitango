from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from anki.notes import Note
from datetime import datetime
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
        # ExamplesCache: モバイル用にHTMLを事前に計算して保存しておくフィールド
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
            # テンプレートも更新が必要だが、ユーザーがカスタマイズしている可能性があるため
            # ここではフィールド追加のみ行う。テンプレート変更はユーザーに案内するか、強制的更新が必要。
            # 今回は簡易的に、フィールドだけ足しておく。

# -------------------------------------------------------------------------
# 2. IDの自動入力
# -------------------------------------------------------------------------
def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # IDフィールド(0番目)が空ならセット
    if not note.fields[0]:
        note.fields[0] = datetime.now().strftime("%Y%m%d%H%M%S")
        editor.loadNote()

# -------------------------------------------------------------------------
# 3. キャッシュ更新ロジック (モバイル対応の中核)
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
    
    # 同じ単語を持つノートを全て取得
    # 注意: エスケープ処理は簡易版
    query = f'"note:{MODEL_NAME}" "Word:{word}"'
    nids = col.find_notes(query)
    
    if not nids: return

    # ノートオブジェクトを全て取得
    notes = [col.get_note(nid) for nid in nids]
    
    # データ収集
    # {nid: {'text': sentence, 'date': date, 'reps': reps}}
    note_data = {}
    
    for note in notes:
        raw_sentence = note['Sentence']
        if not raw_sentence: continue
        
        # 穴埋めタグ除去
        clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
        
        # 作成日
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
        
    # 各ノートのキャッシュフィールドを更新して保存
    _is_updating = True
    try:
        for target_note in notes:
            # 自分以外を表示するリストを作成
            examples = []
            seen_texts = set()
            
            for nid, data in note_data.items():
                if nid == target_note.id: continue # 自分は除外
                
                # 重複チェック (同文なら除外)
                if data['text'] in seen_texts: continue
                seen_texts.add(data['text'])
                
                examples.append(data)
            
            # HTML生成
            if examples:
                html = "<table class='example-table'>"
                html += "<tr><th>Sentence</th><th>Date</th><th>Reps</th></tr>"
                for ex in examples:
                    html += f"<tr><td>{ex['text']}</td><td>{ex['date']}</td><td>{ex['reps']}</td></tr>"
                html += "</table>"
            else:
                html = "<div style='font-size:0.8em; color:gray;'>No other examples found.</div>"
            
            # 変更がある場合のみ保存（無駄な書き込み防止）
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
    
    # 変更されたフィールドが「Word」かどうか確認
    # note.fields は値のリストなので、インデックスで照合
    # モデルのフィールドリストを取得
    flds = [f['name'] for f in note.model()['flds']]
    if current_field_idx < len(flds) and flds[current_field_idx] == "Word":
        # Wordフィールドが変更されたので、キャッシュ更新を実行
        word = note.fields[current_field_idx]
        # 少し遅延させるか、そのまま実行するか。ここでは直接実行。
        # 注意: update_cache_for_word内で col.update_note を呼ぶと
        # エディタ上のノートと競合する可能性があるので、
        # ターゲットが自分自身以外になるように気をつける必要がある。
        update_cache_for_word(word)

# -------------------------------------------------------------------------
# 4. 手動更新アクション (デバッグ・一括更新用)
# -------------------------------------------------------------------------
def update_all_cache():
    """
    全てのEitangoノートのキャッシュを強制的に更新する
    """
    col = mw.col
    # 全てのEitangoノートを取得
    nids = col.find_notes(f'"note:{MODEL_NAME}"')
    if not nids:
        showInfo("Eitangoノートが見つかりませんでした。")
        return

    # 単語ごとにノートIDをグループ化
    word_to_nids = {}
    for nid in nids:
        note = col.get_note(nid)
        word = note['Word']
        if not word: continue
        
        if word not in word_to_nids:
            word_to_nids[word] = []
        word_to_nids[word].append(nid)
    
    # プログレスバー（簡易）
    mw.progress.start(immediate=True)
    count = 0
    total = len(word_to_nids)
    
    try:
        for i, (word, target_nids) in enumerate(word_to_nids.items()):
            mw.progress.update(label=f"Updating: {word}", value=i, max=total)
            
            # この単語グループのデータを収集
            group_data = []
            for nid in target_nids:
                note = col.get_note(nid)
                raw_sentence = note['Sentence']
                if not raw_sentence: continue
                
                # 穴埋め除去
                clean = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
                
                # 日付
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
            
            # 各ノートに書き込み
            for nid in target_nids:
                note = col.get_note(nid)
                
                # 自分以外をリスト化
                examples = [d for d in group_data if d['nid'] != nid]
                
                # HTML生成
                if examples:
                    # 重複排除（テキスト単位）
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
# 初期化処理
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.editor_did_unfocus_field.append(on_editor_unfocus)
    
    # メニューに追加
    action = QAction("Update Eitango Examples", mw)
    qconnect(action.triggered, update_all_cache)
    mw.form.menuTools.addAction(action)

# Anki起動時に実行
gui_hooks.profile_did_open.append(init_addon)

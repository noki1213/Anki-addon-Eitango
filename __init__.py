from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from anki.hooks import addHook
import time

# 定数
MODEL_NAME = "Eitango"
CONF_NAME = "Eitango Addon"

# -------------------------------------------------------------------------
# 1. ノートタイプの作成 (初回起動時のみ)
# -------------------------------------------------------------------------
def create_model_if_needed():
    col = mw.col
    model = col.models.byName(MODEL_NAME)
    
    if not model:
        # Cloze(穴埋め)タイプとして作成
        model = col.models.new(MODEL_NAME)
        model['type'] = 1 # 1 = Cloze
        
        # フィールドの定義
        # IDを先頭にすることで、同じ単語(Word)でも登録できるようにする
        fields = ["ID", "Word", "Meaning", "Sentence"]
        for f in fields:
            col.models.addField(model, col.models.newField(f))
            
        # テンプレート(カードデザイン)の定義
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
        
        # CSSの設定
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
        # 既存モデルがある場合のフィールド確認などは今回は省略
        pass

# -------------------------------------------------------------------------
# 2. IDの自動入力
# -------------------------------------------------------------------------
def on_editor_did_init(editor):
    # エディタが開かれたときにIDフィールドが空なら埋める
    # 注: 新規追加時を想定
    note = editor.note
    if note is None:
        return
        
    if note.model()['name'] != MODEL_NAME:
        return

    # IDフィールド(index 0)が空ならタイムスタンプを入れる
    if not note.fields[0]:
        # ミリ秒単位のユニークID
        unique_id = str(int(time.time() * 1000))
        note.fields[0] = unique_id
        editor.loadNote() # UIに反映

# 追加画面が開くたびにフックするのではなく、
# 新しいノートがセットされたタイミングなどでIDを振るのが安全
# ここでは gui_hooks.editor_did_init_shortcuts を使うのが一般的だが
# シンプルに editor_did_load_note を使う
from aqt import gui_hooks

def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # IDフィールド(0番目)が空ならセット
    if not note.fields[0]:
        note.fields[0] = str(int(time.time() * 1000))
        editor.loadNote()

# -------------------------------------------------------------------------
# 初期化処理
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)

# Anki起動時に実行
from aqt import gui_hooks
gui_hooks.profile_did_open.append(init_addon)
from aqt import mw
from aqt.utils import showInfo, tooltip
from aqt.qt import *
from aqt import gui_hooks
from datetime import datetime
import re

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
<div id='other-examples' style='text-align: left; font-size: 16px;'></div>
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
        # 既存モデルがある場合のフィールド確認などは今回は省略
        pass

# -------------------------------------------------------------------------
# 2. IDの自動入力
# -------------------------------------------------------------------------
def setup_id(editor):
    note = editor.note
    if not note: return
    if note.model()['name'] != MODEL_NAME: return
    
    # IDフィールド(0番目)が空ならセット
    if not note.fields[0]:
        # YYYYMMDDHHMMSS 形式 (例: 20260129183500)
        note.fields[0] = datetime.now().strftime("%Y%m%d%H%M%S")
        editor.loadNote()

# -------------------------------------------------------------------------
# 3. 答え表示時に他の例文を表示
# -------------------------------------------------------------------------
def on_show_answer(card):
    # 現在のカードが Eitango モデルか確認
    note = card.note()
    if note.model()['name'] != MODEL_NAME:
        return
    
    word = note['Word']
    current_id = note['ID']
    
    if not word:
        return

    try:
        # 同じ単語を持つ他のノートを検索
        query = f'"note:{MODEL_NAME}" "Word:{word}"'
        found_nids = mw.col.find_notes(query)
        
        examples = []
        for nid in found_nids:
            other_note = mw.col.get_note(nid)
            
            # 自分自身は除外
            if other_note['ID'] == current_id:
                continue
                
            raw_sentence = other_note['Sentence']
            if not raw_sentence:
                continue
                
            # 穴埋めタグの除去
            clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
            examples.append(clean_sentence)
        
        if examples:
            # HTMLリストを作成
            list_html = "<strong>Other Examples:</strong><ul>"
            for ex in examples:
                list_html += f"<li>{ex}</li>"
            list_html += "</ul>"
            
            # エスケープ処理
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

    for nid in found_nids:
        other_note = mw.col.get_note(nid)
        
        # 自分自身は除外
        if other_note['ID'] == current_id:
            continue
            
        raw_sentence = other_note['Sentence']
        if not raw_sentence:
            continue
            
        # 穴埋めタグの除去: {{c1::答え::ヒント}} -> 答え
        # 簡易的な正規表現
        clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
        examples.append(clean_sentence)
    
    if examples:
        # HTMLリストを作成
        list_html = "<strong>Other Examples:</strong><ul>"
        for ex in examples:
            list_html += f"<li>{ex}</li>"
        list_html += "</ul>"
        
        # エスケープ処理 (JavaScriptの文字列として安全にする)
        list_html_js = list_html.replace("'", "\\'").replace("\n", "")
        
        # JavaScriptを実行してDOMを書き換え
        js = f"""
        var div = document.getElementById('other-examples');
        if (div) {{
            div.innerHTML = '{list_html_js}';
        }}
        """
        mw.reviewer.web.eval(js)
    else:
        # 例文がない場合
        js = "var div = document.getElementById('other-examples'); if(div) { div.innerHTML = 'No other examples found.'; }"
        mw.reviewer.web.eval(js)

# -------------------------------------------------------------------------
# 初期化処理
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)

# Anki起動時に実行
gui_hooks.profile_did_open.append(init_addon)
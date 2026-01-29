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
    
    word_field = note['Word']
    current_id = note['ID']
    
    if not word_field:
        return

    try:
        # 1. カンマで単語を分割
        words = [w.strip() for w in word_field.split(',') if w.strip()]
        
        if not words:
            return
            
        # 2. 検索クエリの構築
        # note:Eitango ("Word:*word1*" OR "Word:*word2*")
        # ワイルドカード(*)を使うことで、フィールドの一部にその単語が含まれていればヒットする
        or_conditions = " OR ".join([f'"Word:*{w}*"' for w in words])
        query = f'"note:{MODEL_NAME}" ({or_conditions})'
        
        found_nids = mw.col.find_notes(query)
        
        examples = []
        for nid in found_nids:
            # 自分自身は除外 (内部IDで比較するのが確実)
            if nid == note.id:
                continue

            other_note = mw.col.get_note(nid)
            
            # IDフィールドによる重複チェック(念のため)
            if other_note['ID'] == current_id:
                continue

            raw_sentence = other_note['Sentence']
            if not raw_sentence:
                continue
                
            # 穴埋めタグの除去
            clean_sentence = re.sub(r'\{\{c\d+::(.*?)(::.*?)?\}\}', r'\1', raw_sentence)
            
            # -------------------------------------------------
            # Ankiのシステムデータから情報を取得
            # -------------------------------------------------
            
            # 1. 作成日時 (note.id は作成時のミリ秒タイムスタンプ)
            created_ts = other_note.id / 1000
            dt = datetime.fromtimestamp(created_ts)
            date_str = dt.strftime("%Y/%m/%d") # シンプルに日付だけにする（時刻は煩雑かも）
            
            # 2. 学習回数 (カード情報から取得)
            # ノートに紐づくカードを全て取得 (通常は1つだが、Clozeは複数ありうる)
            cards = other_note.cards()
            total_reps = 0
            if cards:
                # 例文として表示しているノートの総学習回数（カードごとの合計）
                for c in cards:
                    total_reps += c.reps

            # 表示用文字列
            info_str = f" <span style='font-size: 0.8em; color: gray;'>({date_str}, {total_reps} reps)</span>"
            
            # 重複排除: 文章だけで判断するか、情報込みで判断するか
            # ここでは「文章自体」が同じなら表示しないようにする（シンプル化）
            # もし日付違いの同文を表示したい場合は full_text でチェックする
            full_text = clean_sentence + info_str
            
            # 既存のリストに同じ内容が含まれていないか確認
            if not any(ex['text'] == clean_sentence for ex in examples):
                examples.append({
                    'text': clean_sentence,
                    'date': date_str,
                    'reps': total_reps
                })
        
        if examples:
            # HTMLテーブルを作成
            list_html = "<strong>Other Examples:</strong><table class='example-table'>"
            list_html += "<tr><th>Sentence</th><th>Date</th><th>Reps</th></tr>"
            for ex in examples:
                list_html += f"<tr><td>{ex['text']}</td><td>{ex['date']}</td><td>{ex['reps']}</td></tr>"
            list_html += "</table>"
            
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

# -------------------------------------------------------------------------
# 初期化処理
# -------------------------------------------------------------------------
def init_addon():
    create_model_if_needed()
    gui_hooks.editor_did_load_note.append(setup_id)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)

# Anki起動時に実行
gui_hooks.profile_did_open.append(init_addon)
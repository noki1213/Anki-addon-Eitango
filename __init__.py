from aqt import mw
from aqt.utils import showInfo
from aqt.qt import *

def test_function():
    showInfo("まーや、Ankiアドオンのセットアップが完了しました！")

# ツールメニューにアクションを追加
action = QAction("Eitango Test", mw)
qconnect(action.triggered, test_function)
mw.form.menuTools.addAction(action)

from aqt import mw
from aqt.utils import showInfo
from aqt.qt import *

def test_function():
    showInfo("Ankiアドオンのセットアップが完了しました！")

# Add an action to the Tools menu
action = QAction("Eitango Test", mw)
qconnect(action.triggered, test_function)
mw.form.menuTools.addAction(action)

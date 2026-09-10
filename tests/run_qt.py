"""Isolated Qt smoke/visual checks; does not launch or import real Nuke."""
import os
import sys
import tempfile
import shutil
import types

if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
nuke = types.ModuleType('nuke')
nuke.GUI = False
sys.modules['nuke'] = nuke
scripts = types.ModuleType('nukescripts')
scripts.panels = None
sys.modules['nukescripts'] = scripts
try:
    from PySide6 import QtNetwork as guarded_network
except ImportError:
    from PySide2 import QtNetwork as guarded_network
original_manager = guarded_network.QNetworkAccessManager
def forbid_network_manager(*args,**kwargs):
    raise AssertionError('Unexpected network manager during import/open/offline UI checks')
guarded_network.QNetworkAccessManager = forbid_network_manager
import nukeris
QtWidgets, QtGui, QtCore = nukeris.QtWidgets, nukeris.QtGui, nukeris.QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
font_path = 'C:/Windows/Fonts/arial.ttf'
if os.path.exists(font_path):
    font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QtGui.QFont(families[0], 10))
palette = app.palette()
for role, color in [('Window','#353535'),('WindowText','#D0D0D0'),('Base','#292929'),('Text','#D0D0D0'),('Button','#444444'),('ButtonText','#DDDDDD')]:
    palette.setColor(nukeris._enum_value(QtGui.QPalette,'ColorRole',role),QtGui.QColor(color))
app.setPalette(palette)
folder = tempfile.mkdtemp(prefix='nukeris-qt-')
nukeris.user_settings_path = lambda: os.path.join(folder,'settings.json')
nukeris._settings_path = lambda: os.path.join(folder,'missing-legacy.json')
try:
    panel = nukeris.NukerisPanel()
    assert panel.network.transport.manager is None
    assert not panel.preferences['global_enabled']
    assert not panel.preferences['studio_enabled']
    for w,h,name in [(800,800,'standard'),(360,600,'compact')]:
        panel.resize(w,h)
        panel.show()
        app.processEvents()
        assert not panel.error_text, panel.error_text
        if len(sys.argv)>2:
            panel.grab().save(os.path.join(sys.argv[2],name+'.png'))
    panel._new_game()
    engine = panel.engine
    panel.resize(900,900)
    app.processEvents()
    assert panel.engine is engine
    panel._set_paused(True,True)
    assert not panel._timer.isActive()
    # A pending online start must still leave Nuke's modified keys alone and
    # release focus immediately on Esc. Its late reply must not start a game.
    original_start_run = panel.network.start_run
    replies = []
    panel.network.start_run = lambda mode, callback: replies.append(callback)
    panel.preferences['global_enabled'] = True
    panel._mode_combo.setCurrentIndex(1)
    panel.setFocus()
    app.processEvents()
    assert panel.hasFocus()
    panel._new_game()
    assert panel._starting_online
    key_press = nukeris._enum_value(QtCore.QEvent, 'Type', 'KeyPress')
    modified = QtGui.QKeyEvent(key_press, nukeris.QC.Key_S, nukeris.QC.ControlModifier)
    panel.keyPressEvent(modified)
    assert not modified.isAccepted()
    no_modifier = nukeris._enum_value(QtCore.Qt, 'KeyboardModifier', 'NoModifier')
    escaped = QtGui.QKeyEvent(key_press, nukeris.QC.Key_Escape, no_modifier)
    panel.keyPressEvent(escaped)
    assert not panel.hasFocus() and not panel.input_active
    assert not panel._starting_online and not panel._timer.isActive()
    replies[0](dict(ok=True, run_token='ignored', seed='a'*16))
    assert panel.engine is engine
    panel.network.start_run = original_start_run
    panel.preferences['global_enabled'] = False
    for dialog_class in (nukeris.SettingsDialog,nukeris.RankingDialog):
        dialog=dialog_class(panel)
        dialog.show()
        app.processEvents()
        if len(sys.argv)>2:
            dialog.grab().save(os.path.join(sys.argv[2],dialog_class.__name__+'.png'))
        dialog.close()
    assert not panel.error_text, panel.error_text
    panel.close()
    app.processEvents()
    from qt_polish_checks import run as polish_checks
    polish_checks(nukeris,app,folder,sys.argv[2] if len(sys.argv)>2 else None)
    guarded_network.QNetworkAccessManager = original_manager
    from qt_network_checks import run
    run(nukeris,app)
    print('Qt smoke passed:', nukeris.QT_BINDING, QtCore.qVersion())
finally:
    guarded_network.QNetworkAccessManager = original_manager
    shutil.rmtree(folder)

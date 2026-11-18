"""放映会话浮条：悬浮定位、频道切换文案与启用态、结束后残留修复。"""

import sys
from types import SimpleNamespace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow
from ui.sermon.player.session_bar import SessionBar


class _StubCtrl:
    def __init__(self, active=False):
        self.active = active
        self.generation = 0
        self.index = 0
        self.doc = SimpleNamespace(slides=[SimpleNamespace() for _ in range(3)])

    def stop(self):
        self.active = False


def test_reposition_centers_bottom():
    host = QWidget()
    host.resize(800, 600)
    bar = SessionBar(host)
    bar.set_channel("sermon", "1/3")
    bar.show()
    bar.reposition(host)
    assert bar.width() <= 800
    # 底部居中：距底 BOTTOM_GAP，水平居中
    assert abs((bar.x() + bar.width() / 2) - 400) <= 1
    assert bar.y() + bar.height() == 600 - SessionBar.BOTTOM_GAP
    assert bar.height() == SessionBar.BAR_HEIGHT


def test_reposition_saved_and_clamped():
    """拖动记忆位置优先；越界时夹取回主窗可视范围。"""
    host = QWidget()
    host.resize(800, 600)
    bar = SessionBar(host)
    bar.show()
    bar.reposition(host, saved=(100, 80))
    assert (bar.x(), bar.y()) == (100, 80)
    bar.reposition(host, saved=(5000, -20))
    assert bar.x() == 800 - bar.width() - 8
    assert bar.y() == 8


def test_drag_moves_and_emits():
    """按住空白拖动：位置跟随鼠标、松开发出 drag_moved；按钮上按下不拖。"""
    host = QWidget()
    host.resize(800, 600)
    bar = SessionBar(host)
    bar.show()
    bar.reposition(host, saved=(200, 100))
    app_process = None

    events = []

    def press_at(x, y, button=Qt.MouseButton.LeftButton):
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF, QEvent

        ev = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            button,
            button,
            Qt.KeyboardModifier.NoModifier,
        )
        bar.mousePressEvent(ev)

    def move_to(x, y):
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF, QEvent

        ev = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        bar.mouseMoveEvent(ev)

    seen = []
    bar.drag_moved.connect(lambda x, y: seen.append((x, y)))

    # 按住空白区（条内边距处，childAt 为空）向下拖 30px
    press_at(20, 8)
    move_to(20, 38)
    assert (bar.x(), bar.y()) == (200, 130)
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QPointF, QEvent

    rel = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(20, 38),
        QPointF(20, 38),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    bar.mouseReleaseEvent(rel)
    assert seen == [(200, 130)]

    # 在按钮上按下不触发拖动
    press_on = bar.end_btn
    ev_pos = bar.mapFromGlobal(press_on.mapToGlobal(press_on.rect().center()))
    from PyQt6.QtGui import QMouseEvent

    ev2 = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(ev_pos),
        QPointF(ev_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    bar.mousePressEvent(ev2)
    move_to(ev_pos.x() + 40, ev_pos.y())
    assert bar.x() == 200  # 未移动
    assert len(seen) == 1  # 未发信号


def test_set_channel_toggles():
    bar = SessionBar()
    bar.set_channel("sermon", "1/1")
    assert bar.status.text() == "观众：讲篇  1/1"
    # 当前观众频道禁用、另一频道可点切换
    assert not bar.sermon_btn.isEnabled()
    assert bar.scripture_btn.isEnabled()
    assert bar.prev_btn.isEnabled() and bar.next_btn.isEnabled()
    bar.set_channel("scripture")
    assert bar.status.text() == "观众：经文"
    assert not bar.scripture_btn.isEnabled()
    assert bar.sermon_btn.isEnabled()
    assert not bar.prev_btn.isEnabled() and not bar.next_btn.isEnabled()


def test_chrome_hides_bar_after_stop():
    """编辑器放映结束路径也必须刷新会话浮条（残留 bug 回归锁定）。"""
    mw = MainWindow.__new__(MainWindow)
    editor = SimpleNamespace(isVisible=lambda: True, _presenting=True)

    def _stop_editor(**k):
        # 与真实 editor.on_presentation_stopped 一致：复位 _presenting
        editor._presenting = False

    editor.on_presentation_stopped = _stop_editor
    mw._sermon_editor = editor
    mw.sermon_controller = _StubCtrl(active=False)
    mw.session_bar = SessionBar()
    mw.toolbar = None
    mw._projection_channel = "sermon"
    mw._shortcuts = []
    mw._presenter_shortcuts = []
    mw._keep_editor_after_stop = True
    mw._abort_extension_sermon_layer = lambda: None
    mw._refit_sermon_chrome = lambda: None
    mw._session_bar_pos = None
    # stub 主窗不是真 QWidget，reposition 无法用其几何定位
    mw.session_bar.reposition = lambda *a: None

    mw._update_session_chrome()
    mw.session_bar.show()
    assert mw.session_bar.isVisible()

    # 结束放映（编辑器放映分支）
    mw.stop_sermon_presentation()
    assert not mw.session_bar.isVisible()


def test_bar_hides_on_controller_stop():
    """controller 活跃路径结束放映：浮条必须一次点击即消失。

    旧代码 _on_sermon_stopped 先刷浮条后复位 editor._presenting，
    _sermon_session_active() 仍视为放映中把浮条 show 回去（需点两下）。"""
    mw = MainWindow.__new__(MainWindow)
    editor = SimpleNamespace(isVisible=lambda: True, _presenting=True)

    def _stop_editor(**k):
        editor._presenting = False

    editor.on_presentation_stopped = _stop_editor
    mw._sermon_editor = editor
    ctrl = _StubCtrl(active=True)

    def _stop():
        ctrl.active = False
        mw._on_sermon_stopped()  # 模拟 stopped 信号同步回调

    ctrl.stop = _stop
    mw.sermon_controller = ctrl
    mw.session_bar = SessionBar()
    mw.toolbar = None
    mw.extension_window = None
    mw._extension_sync_timer = SimpleNamespace(start=lambda: None, stop=lambda: None)
    mw._projection_channel = "sermon"
    mw._shortcuts = []
    mw._presenter_shortcuts = []
    mw._keep_editor_after_stop = True
    mw._abort_extension_sermon_layer = lambda: None
    mw._refit_sermon_chrome = lambda: None
    mw._session_bar_pos = None
    mw.session_bar.reposition = lambda *a: None
    mw._update_status = lambda: None

    mw._update_session_chrome()
    mw.session_bar.show()
    assert mw.session_bar.isVisible()

    # 放映中点浮条「结束放映」（controller.active=True 分支）
    mw.stop_sermon_presentation()
    assert not mw.session_bar.isVisible()

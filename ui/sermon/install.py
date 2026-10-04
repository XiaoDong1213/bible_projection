"""挂载讲篇编辑器：主窗口中央全屏叠层。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QPushButton


class _CentralResizeFilter(QObject):
    """中央区尺寸变化时同步叠层几何。"""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            ed = self._editor
            if ed is not None and ed.isVisible() and hasattr(ed, "fit_to_parent"):
                ed.fit_to_parent()
        return False


def attach_sermon_editor(window):
    """在主工具栏加入「讲篇」按钮；编辑器叠在中央区上。"""
    window._sermon_editor = None
    window._sermon_resize_filter = None

    button = QPushButton("讲篇")
    button.setObjectName("sermonToolbarButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(44)
    button.setMinimumWidth(64)
    button.setToolTip("打开讲篇编辑（叠在主界面上；再点一次可返回经文）")
    button.setCheckable(True)
    button.clicked.connect(lambda: _toggle_editor(window))

    before = getattr(window.toolbar, "_search_anchor_action", None)
    if before is not None:
        window.toolbar.insertWidget(before, button)
    else:
        window.toolbar.addWidget(button)
    window.sermon_button = button


def _ensure_editor(window):
    editor = getattr(window, "_sermon_editor", None)
    if editor is not None:
        return editor

    from core.sermon import SermonStore
    from .editor.window import SermonEditorWindow

    central = window.centralWidget()
    editor = SermonEditorWindow(SermonStore(), parent=central)
    editor._host_window = window
    if hasattr(editor, "reload_last_text_style"):
        editor.reload_last_text_style()
    window._sermon_editor = editor
    editor.closed.connect(lambda: _on_editor_closed(window))
    if hasattr(window, "theme") and hasattr(editor, "apply_theme"):
        editor.apply_theme(window.theme)

    filt = _CentralResizeFilter(editor, central)
    central.installEventFilter(filt)
    splitter = getattr(window, "main_splitter", None)
    if splitter is not None:
        splitter.installEventFilter(filt)
    window._sermon_resize_filter = filt
    editor.hide()
    return editor


def _on_editor_closed(window):
    btn = getattr(window, "sermon_button", None)
    if btn is not None:
        btn.blockSignals(True)
        btn.setChecked(False)
        btn.blockSignals(False)


def _toggle_editor(window):
    editor = getattr(window, "_sermon_editor", None)
    if editor is not None and editor.isVisible():
        editor.request_close()
        return
    _open_editor(window)


def _open_editor(window):
    """打开讲篇叠层（供工具栏与放映入口调用）。"""
    editor = _ensure_editor(window)
    editor.fit_to_parent()
    editor.show()
    editor.raise_()
    bar = getattr(window, "session_bar", None)
    if bar is not None and bar.isVisible():
        bar.raise_()
    QTimer.singleShot(0, editor.fit_to_parent)
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    # 若仍在放映，叠层回来后恢复编辑器翻页快捷键
    if getattr(editor, "_presenting", False):
        editor._set_present_shortcuts_enabled(True)
        if hasattr(window, "_update_session_chrome"):
            window._update_session_chrome()
    btn = getattr(window, "sermon_button", None)
    if btn is not None:
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)

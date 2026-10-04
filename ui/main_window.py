"""主窗口：业务逻辑（含方向键逻辑导航与扩展屏滚动同步）。"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QStatusBar,
    QLabel,
    QApplication,
    QAbstractSpinBox,
    QLineEdit,
    QAbstractItemView,
    QTextEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from core.config import AppConfig
from core.database import BibleDatabase
from core.selection import ScriptureSelection
from core.logical import normalize_selection
from core.paths import styles_dir
from ui.quick_search import SearchWidget
from ui.navigation import NavigationPanel
from ui.toolbar import ToolBarWidget
from ui.display import PreviewHost, ExtensionWindow
from ui.themes import build_stylesheet, theme_tokens
from ui.sermon.player import PresentationController
from ui.sermon.player.session_bar import SessionBar


class MainWindow(QMainWindow):
    def __init__(self, db: BibleDatabase, config: AppConfig):
        super().__init__()
        self.db = db
        self.config = config
        self.extension_window = None
        self._syncing_scroll = False
        self.current_book = None
        self.current_chapter = None
        self.current_start = None
        self.current_end = None
        self.current_selection = None
        self.verses = []
        self.settings = config.load_display_settings()
        self.theme = self.settings.get("theme", "dark")
        self._stylesheet_cache = ""
        self._last_speed = 3
        self.setWindowTitle("Bible Pro")
        self.setMinimumSize(800, 600)

        geometry = config.load_window_state()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 800)

        self.sermon_controller = PresentationController(self)
        self.sermon_controller.started.connect(self._on_sermon_started)
        self.sermon_controller.stopped.connect(self._on_sermon_stopped)
        self.sermon_controller.slide_changed.connect(self._on_sermon_slide_changed)
        self.sermon_controller.steps_requested.connect(self._on_sermon_steps)
        self.sermon_controller.resume_requested.connect(self._on_sermon_resume)
        self.sermon_controller.status_changed.connect(self._on_sermon_status)
        self._projection_channel = "scripture"
        self._keep_editor_after_stop = True

        # 先套主题，再建大量控件：避免「先造百余按钮再全局 polish」
        self._load_theme_style()
        self._create_central_widget()
        self._create_toolbar()
        self._create_shortcuts()
        self._create_statusbar()
        self._apply_settings(self.settings)

        # 历史与非当前书卷页：窗口显示后再补
        QTimer.singleShot(0, self._deferred_startup)

        # v1：16ms 定时 + scroll_changed 持续按比例同步副屏；副屏自身不滚
        self._extension_sync_timer = QTimer(self)
        self._extension_sync_timer.setInterval(16)
        self._extension_sync_timer.timeout.connect(self._sync_extension_scroll)

    def _deferred_startup(self):
        self.nav_panel.load_history(self.config.load_history())
        self.nav_panel.history_changed.connect(self._save_history)
        # 稍后再补齐其余书卷页，避免和首屏抢同一帧
        QTimer.singleShot(50, self.nav_panel.warm_book_tabs)

    def _save_history(self, h):
        self.config.save_history(h)

    def _load_theme_style(self):
        sheet = build_stylesheet(self.theme, styles_dir())
        self._stylesheet_cache = sheet
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(sheet)
        tokens = theme_tokens(self.theme)
        if hasattr(self, "preview_host"):
            self.preview_host.apply_theme(tokens)
        if hasattr(self, "search_widget") and self.search_widget is not None:
            self.search_widget.apply_theme(self.theme)
        if getattr(self, "_scripture_search_widget", None) is not None:
            self._scripture_search_widget.apply_theme(self.theme)

    def _create_toolbar(self):
        self.toolbar = ToolBarWidget()
        self.addToolBar(self.toolbar)
        self.toolbar.theme = self.theme
        self.toolbar.load_settings(self.settings)
        self.toolbar.scroll_speed_changed.connect(self._on_scroll_speed)
        self.toolbar.extend_toggled.connect(self._toggle_extension)
        self.toolbar.settings_changed.connect(self._on_settings_changed)
        self.toolbar.theme_changed.connect(self._on_theme_changed)
        self.toolbar.topmost_toggled.connect(self._toggle_extension_topmost)
        self.toolbar.scroll_up.connect(lambda: self._scroll_manual(-40))
        self.toolbar.scroll_down.connect(lambda: self._scroll_manual(40))
        self.toolbar.clear_requested.connect(self._clear_display)
        self.scripture_display.scroll_changed.connect(self._sync_extension_scroll)
        self.scripture_display.scroll_finished.connect(self._on_scroll_finished)

    def _create_central_widget(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.nav_panel = NavigationPanel(self.db)
        self.nav_panel.book_selected.connect(self._on_book_selected)
        self.nav_panel.range_selected.connect(self._on_range_selected)
        self.nav_panel.history_opened.connect(self._on_history_opened)
        self.nav_panel.verse_segmentation_changed.connect(self._on_verse_segmentation_changed)
        splitter.addWidget(self.nav_panel)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.preview_host = PreviewHost()
        self.scripture_display = self.preview_host.display
        self.preview_host.apply_theme(theme_tokens(self.theme))
        right_layout.addWidget(self.preview_host, 1)

        splitter.addWidget(right)
        splitter.setSizes([360, 840])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        self.main_splitter = splitter
        outer.addWidget(splitter, 1)

        self.session_bar = SessionBar()
        self.session_bar.to_scripture.connect(self.show_scripture_channel)
        self.session_bar.to_sermon.connect(self.show_sermon_channel)
        self.session_bar.prev_page.connect(self._presenter_prev)
        self.session_bar.next_page.connect(self._presenter_next)
        self.session_bar.end_session.connect(self.stop_sermon_presentation)
        outer.addWidget(self.session_bar)
        self.setCentralWidget(central)
        self._build_presenter_shortcuts()

    def _build_presenter_shortcuts(self):
        self._presenter_shortcuts = []
        for key, slot in (
            (Qt.Key.Key_Space, self._presenter_next),
            (Qt.Key.Key_Right, self._presenter_next),
            (Qt.Key.Key_Left, self._presenter_prev),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.setEnabled(False)
            sc.activated.connect(slot)
            self._presenter_shortcuts.append(sc)

    def _set_presenter_shortcuts(self, enabled: bool):
        for sc in getattr(self, "_presenter_shortcuts", []):
            sc.setEnabled(bool(enabled))

    def _set_scripture_nav_shortcuts(self, enabled: bool):
        """放映讲篇时关掉经文左右/空格，避免抢翻页。"""
        for s in getattr(self, "_shortcuts", []):
            try:
                seq = s.key().toString()
            except Exception:
                continue
            if seq in (
                "Left",
                "Right",
                "Up",
                "Down",
                "Space",
                "Ctrl+Left",
                "Ctrl+Right",
            ):
                s.setEnabled(bool(enabled))

    def _update_session_chrome(self, *, sync_editor: bool = True):
        """放映中：主屏用编辑器叠层看讲篇；底栏控制翻页/切频道。"""
        active = self.sermon_controller.active
        if not hasattr(self, "session_bar"):
            return
        if not active:
            self.session_bar.hide()
            self._refit_sermon_chrome()
            QTimer.singleShot(0, self._refit_sermon_chrome)
            self._set_scripture_nav_shortcuts(True)
            self._set_presenter_shortcuts(False)
            return

        page = self._sermon_session_status_text()

        self.session_bar.show()
        self.session_bar.set_channel(self._projection_channel, page)
        self._refit_sermon_chrome()
        QTimer.singleShot(0, self._refit_sermon_chrome)
        # 讲篇频道：空格/方向键翻页；经文频道：恢复经文导航键
        on_sermon = self._projection_channel == "sermon"
        self._set_scripture_nav_shortcuts(not on_sermon)
        editor = getattr(self, "_sermon_editor", None)
        editor_presenting = bool(
            editor is not None
            and editor.isVisible()
            and getattr(editor, "_presenting", False)
        )
        # 编辑器叠层可见时用编辑器快捷键；否则用主窗口
        self._set_presenter_shortcuts(on_sermon and not editor_presenting)
        if (
            sync_editor
            and editor is not None
            and editor.isVisible()
            and hasattr(editor, "sync_from_controller")
        ):
            editor.sync_from_controller()

    def _refit_sermon_chrome(self):
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and editor.isVisible() and hasattr(editor, "fit_to_parent"):
            editor.fit_to_parent()
        if hasattr(self, "session_bar") and self.session_bar.isVisible():
            self.session_bar.raise_()

    def _sermon_session_status_text(self) -> str:
        """底栏附加：讲篇频道只写页码。"""
        if self._projection_channel != "sermon":
            return ""
        ctrl = self.sermon_controller
        if not ctrl.active or ctrl.doc is None or not ctrl.doc.slides:
            return ""
        n = len(ctrl.doc.slides)
        idx = max(0, min(ctrl.index, n - 1))
        return f"{idx + 1}/{n}"

    def _presenter_next(self):
        if not self.sermon_controller.active:
            return
        if self._focus_blocks_nav_shortcuts():
            return
        if self._projection_channel != "sermon":
            self.show_sermon_channel()
            return
        self.sermon_controller.advance()

    def _presenter_prev(self):
        if not self.sermon_controller.active:
            return
        if self._focus_blocks_nav_shortcuts():
            return
        if self._projection_channel != "sermon":
            self.show_sermon_channel()
            return
        self.sermon_controller.prev_slide()

    def _focus_blocks_nav_shortcuts(self):
        w = QApplication.focusWidget()
        if w is None:
            return False
        if isinstance(w, (QAbstractSpinBox, QLineEdit, QTextEdit, QAbstractItemView)):
            return True
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and editor.isVisible() and hasattr(editor, "_focus_is_text_field"):
            if editor._focus_is_text_field():
                return True
        return False

    def _sermon_alive(self, gen: int) -> bool:
        ctrl = self.sermon_controller
        return bool(ctrl.active and int(ctrl.generation) == int(gen))

    def _after_sermon(self, gen: int, fn):
        def _go():
            if self._sermon_alive(gen):
                fn()

        return _go

    def _set_extension_scroll_sync(self, on: bool):
        if (
            on
            and self.extension_window
            and self.extension_window.isVisible()
            and getattr(self.extension_window, "display_mode", None) != "sermon"
        ):
            self._extension_sync_timer.start()
            return
        self._extension_sync_timer.stop()

    def _abort_extension_sermon_layer(self):
        ext = self.extension_window
        if ext is None:
            return
        try:
            ext.slide_stage.abort_playback()
        except Exception:
            pass
        if ext.isVisible() and getattr(ext, "display_mode", None) == "sermon":
            ext.set_display_mode("scripture", animate=False)
        try:
            ext.slide_stage.clear_stage()
        except Exception:
            pass

    def _on_escape(self):
        if self.sermon_controller.active:
            self.stop_sermon_presentation()
            return
        self._close_extension()

    def _wrap_nav(self, fn):
        def handler():
            if self._focus_blocks_nav_shortcuts():
                return
            fn()

        return handler

    def _create_shortcuts(self):
        bindings = [
            (Qt.Key.Key_Return, self._show_search, False),
            (Qt.Key.Key_Enter, self._show_search, False),
            (Qt.Key.Key_Escape, self._on_escape, False),
            (Qt.Key.Key_F12, self._toggle_extension, False),
            (Qt.Key.Key_F1, self.toolbar._open_help, False),
            (Qt.Key.Key_Right, self._add_verse_end, True),
            (Qt.Key.Key_Left, self._remove_verse_end, True),
            # 前面一节：Ctrl+← 增加，Ctrl+→ 减少
            ("Ctrl+Left", self._add_verse_start, True),
            ("Ctrl+Right", self._remove_verse_start, True),
            (Qt.Key.Key_Up, lambda: self._scroll_manual(-30), True),
            (Qt.Key.Key_Down, lambda: self._scroll_manual(30), True),
            (Qt.Key.Key_Space, self._toggle_scroll_pause, True),
        ]
        for i in range(1, 10):
            bindings.append((getattr(Qt.Key, f"Key_{i}"), lambda i=i: self._set_speed_hotkey(i), True))

        self._shortcuts = []
        for key, fn, guard in bindings:
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(self._wrap_nav(fn) if guard else fn)
            self._shortcuts.append(s)

    def _set_speed_hotkey(self, speed):
        self.toolbar._set_speed(speed)

    def _on_scroll_finished(self):
        self.toolbar._set_speed(0)

    def _create_statusbar(self):
        self.status_label = QLabel("按回车键打开搜索")
        status = QStatusBar()
        status.addWidget(self.status_label)
        self.setStatusBar(status)

    def _on_settings_changed(self, s):
        self.settings.update(s)
        self._apply_settings(s)
        self.config.save_display_settings(s)

    def _apply_settings(self, s):
        enabled = bool(s.get("verse_segmentation", self.settings.get("verse_segmentation", False)))
        self.scripture_display.apply_settings(s)
        self.nav_panel.set_verse_segmentation(enabled)
        if self.extension_window:
            self.extension_window.apply_settings(s)
            self._sync_extension_scroll()

    def _on_theme_changed(self, t):
        self.theme = t
        self.settings["theme"] = t
        self._load_theme_style()
        self.config.save_display_settings({"theme": t})
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and hasattr(editor, "apply_theme"):
            editor.apply_theme(t)

    def _show_search(self):
        existing = getattr(self, "search_widget", None)
        if existing is not None and existing.isVisible():
            # 搜索已打开：Enter 交给搜索面板确认，不要和「关搜索」抢键
            if hasattr(existing, "confirm_from_enter"):
                existing.confirm_from_enter()
            return
        if existing is None:
            self.search_widget = SearchWidget(self.db, self, theme=self.theme)
            self.search_widget.search_triggered.connect(self._on_search_result)
            self.search_widget.close_requested.connect(self._close_search)
        else:
            self.search_widget.apply_theme(self.theme)
        self.search_widget.move(self.mapToGlobal(QPoint(self.width() // 2 - 330, 72)))
        self.search_widget.show()
        self.search_widget.search_input.setFocus()

    def _close_search(self):
        widget = getattr(self, "search_widget", None)
        if widget is not None:
            widget.hide()

    def _on_search_result(self, selection):
        selection = self._coerce_selection(selection)
        if selection is None:
            return
        # Enter 确认搜索：若讲篇叠层开着，静默暂存并回到经文
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and editor.isVisible():
            if hasattr(editor, "stash_and_hide"):
                editor.stash_and_hide()
            elif hasattr(editor, "request_close"):
                editor.request_close()
        self._load_selection(selection)
        self.nav_panel.add_selection_to_history(selection)
        self.nav_panel.sync_from_selection(selection)
        self._close_search()

    def _on_book_selected(self, b, c):
        max_v = self.db.get_verse_count(b, c)
        selection = ScriptureSelection.single_chapter(b, c, 1, max_v, max_verse=max_v)
        self._load_selection(selection)
        self.nav_panel.add_selection_to_history(selection)
        self.nav_panel.sync_from_selection(selection)

    def _on_verse_segmentation_changed(self, e):
        enabled = bool(e)
        self.settings["verse_segmentation"] = enabled
        self.scripture_display.set_verse_segmentation(enabled)
        if self.extension_window:
            self.extension_window.scripture_display.set_verse_segmentation(enabled)
        self._sync_extension_scroll()
        self.config.save_display_settings({"verse_segmentation": enabled})

    def _on_range_selected(self, selection):
        selection = self._coerce_selection(selection)
        if selection is None:
            return
        self._load_selection(selection)
        self.nav_panel.add_selection_to_history(selection)

    def _on_history_opened(self, selection):
        selection = self._coerce_selection(selection)
        if selection is None:
            return
        self._load_selection(selection)

    @staticmethod
    def _coerce_selection(value):
        if isinstance(value, ScriptureSelection):
            return value
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return ScriptureSelection.from_legacy(*value)
        if isinstance(value, dict):
            return ScriptureSelection.from_history_entry(value)
        return None

    def _load_scripture(self, b, c, s, e):
        max_v = self.db.get_verse_count(b, c)
        if s is None:
            selection = ScriptureSelection.single_chapter(b, c, 1, max_v, max_verse=max_v)
        else:
            end = max_v if e is None else e
            selection = ScriptureSelection.single_chapter(b, c, s, end, max_verse=max_v)
        self._load_selection(selection)

    def _load_selection(self, selection: ScriptureSelection, reset_scroll=True, restore_scroll_y=None):
        selection = normalize_selection(self.db, selection)
        self.current_selection = selection
        self.current_book = selection.book
        self.current_chapter = selection.primary_chapter
        self.current_start = selection.primary_start
        self.current_end = selection.primary_end
        self.verses = self.db.get_selection_verses(selection)
        self.scripture_display.set_from_selection(
            selection, self.verses, reset_scroll=reset_scroll
        )
        if restore_scroll_y is not None:
            self.scripture_display.text_display.set_scroll_y(restore_scroll_y, emit=False)
            self.scripture_display.update()
        if self.extension_window and self.extension_window.isVisible():
            if reset_scroll:
                QApplication.processEvents()
            self.extension_window.update_from_selection(
                selection, self.verses, reset_scroll=reset_scroll
            )
            self._sync_extension_scroll()
            # 选了经文就切到经文频道，讲篇页码保留
            if self.extension_window.display_mode == "sermon" or self.sermon_controller.active:
                self.show_scripture_channel(ensure_extension=False)
        self._update_status()

    def _update_status(self):
        if self.sermon_controller.active:
            return
        if self.current_selection is not None:
            self.status_label.setText(self.current_selection.label())
        elif self.current_book:
            self.status_label.setText(
                f"{self.current_book} {self.current_chapter}:{self.current_start}-{self.current_end}"
            )
        else:
            self.status_label.setText("按回车键打开搜索")

    def _clear_display(self):
        self.toolbar._set_speed(0)
        self.current_selection = None
        self.current_book = None
        self.current_chapter = 1
        self.current_start = 1
        self.current_end = 1
        self.verses = []
        self.scripture_display.clear_scripture()
        if self.extension_window:
            self.extension_window.scripture_display.clear_scripture()
        self.status_label.setText("已清屏")

    def _toggle_extension(self):
        if self.extension_window and self.extension_window.isVisible():
            self._close_extension()
            return
        self._show_extension()

    def _close_extension(self):
        ext = self.extension_window
        presenting = self.sermon_controller.active
        editor = getattr(self, "_sermon_editor", None)
        self._keep_editor_after_stop = bool(editor is not None and editor.isVisible())
        self._abort_extension_sermon_layer()
        if ext is not None and ext.isVisible():
            ext.hide()
        self._extension_sync_timer.stop()
        self.toolbar.set_extend_active(False)
        if presenting:
            self.sermon_controller.stop()
        else:
            self._update_session_chrome()
        self.status_label.setText("扩展显示已关闭")

    def _bind_extension_signals(self, ext: ExtensionWindow):
        ext.close_requested.connect(self._close_extension)
        ext.sermon_next_requested.connect(self._presenter_next)
        ext.sermon_prev_requested.connect(self._presenter_prev)
        ext.sermon_stop_requested.connect(self.stop_sermon_presentation)
        ext.scripture_channel_requested.connect(self.show_scripture_channel)

    def ensure_extension_visible(self, *, allow_single_screen: bool = False) -> bool:
        """确保副屏可见；讲篇放映时可在单屏下落到主屏窗口。"""
        if self.extension_window and self.extension_window.isVisible():
            return True
        return self._show_extension(allow_single_screen=allow_single_screen)

    def _show_extension(self, *, allow_single_screen: bool = False) -> bool:
        screens = QApplication.screens()
        single = len(screens) < 2
        if single and not allow_single_screen:
            self.status_label.setText("未检测到第二块屏幕")
            return False

        topmost = bool(self.settings.get("extension_topmost", True))
        if not self.extension_window:
            self.extension_window = ExtensionWindow(topmost=topmost)
            self._bind_extension_signals(self.extension_window)
            self.extension_window.apply_settings(self.settings)
        else:
            self.extension_window.apply_topmost(topmost)

        primary = QApplication.primaryScreen()
        if single:
            target = primary or screens[0]
            geom = target.availableGeometry()
            # 单屏：以接近全屏的窗口放映，便于开发/测试
            self.extension_window.setGeometry(geom)
            stage_w, stage_h = geom.width(), geom.height()
            self.preview_host.set_stage_size(stage_w, stage_h)
            self.extension_window.scripture_display.set_stage_size(stage_w, stage_h)
            self.extension_window.showMaximized()
            status = f"扩展显示(单屏): {target.name()} ({stage_w}x{stage_h})"
        else:
            target = None
            for s in screens:
                if s is not primary:
                    target = s
                    break
            if target is None:
                target = screens[1]
            geom = target.geometry()
            stage_w, stage_h = geom.width(), geom.height()
            self.preview_host.set_stage_size(stage_w, stage_h)
            self.extension_window.scripture_display.set_stage_size(stage_w, stage_h)
            self.extension_window.setGeometry(geom)
            self.extension_window.showFullScreen()
            status = f"扩展显示: {target.name()} ({stage_w}x{stage_h})，预览已按副屏等比缩放"

        if self.verses and self.current_selection is not None:
            self.extension_window.update_from_selection(self.current_selection, self.verses)
        elif self.verses:
            self.extension_window.update_scripture(
                self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
            )
        self.extension_window.set_scroll_speed(0)
        self.preview_host._fit_view()
        self._sync_extension_scroll()
        self.toolbar.set_extend_active(True)
        if self.sermon_controller.active and self._projection_channel == "sermon":
            self.sermon_controller.resume_display()
            self.extension_window.set_display_mode("sermon", animate=True)
            self._set_extension_scroll_sync(False)
        else:
            self._projection_channel = "scripture"
            self._set_extension_scroll_sync(True)
        self._update_session_chrome()
        self.status_label.setText(status)
        return True

    def show_scripture_channel(self, ensure_extension: bool = True):
        """扩展屏切到经文；主屏收起讲篇叠层，露出经文预览。"""
        if ensure_extension:
            if not self.ensure_extension_visible(allow_single_screen=True):
                return
        if not self.extension_window:
            return
        self._projection_channel = "scripture"
        if self.extension_window.display_mode != "scripture":
            self.extension_window.set_display_mode("scripture", animate=True)
        QTimer.singleShot(0, self._after_scripture_channel_chrome)

    def _after_scripture_channel_chrome(self):
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and editor.isVisible():
            if hasattr(editor, "_set_present_shortcuts_enabled"):
                editor._set_present_shortcuts_enabled(False)
            editor.hide()
            from ui.sermon.install import _on_editor_closed

            _on_editor_closed(self)
        self._set_extension_scroll_sync(True)
        self._sync_extension_scroll()
        self._update_session_chrome(sync_editor=False)
        if not self.sermon_controller.active:
            if self.current_selection is not None:
                self.status_label.setText(f"扩展屏：经文 · {self.current_selection.label()}")
            else:
                self.status_label.setText("扩展屏：经文")

    def show_sermon_channel(self):
        """扩展屏显示讲篇；主屏打开讲篇叠层，不再留在经文页。"""
        if self.sermon_controller.active:
            if not self.ensure_extension_visible(allow_single_screen=True):
                return
            self._projection_channel = "sermon"
            self.sermon_controller.resume_display()
            self.extension_window.set_display_mode("sermon", animate=True)
            self._set_extension_scroll_sync(False)
            QTimer.singleShot(0, lambda: self._update_session_chrome(sync_editor=False))
            QTimer.singleShot(self._channel_fade_wait_ms(), self._restore_sermon_editor_chrome)
            return

        editor = getattr(self, "_sermon_editor", None)
        if editor is None:
            from ui.sermon.install import _open_editor

            _open_editor(self)
            editor = getattr(self, "_sermon_editor", None)
        if editor is None:
            QMessageBox.information(self, "讲篇放映", "请先打开讲篇并编辑内容。")
            return
        editor.start_presentation()

    def _restore_sermon_editor_chrome(self):
        if not self.sermon_controller.active or self._projection_channel != "sermon":
            return
        from ui.sermon.install import _open_editor

        _open_editor(self)
        editor = getattr(self, "_sermon_editor", None)
        if editor is None:
            return
        editor._presenting = True
        editor._set_present_shortcuts_enabled(True)
        editor.play_btn.setEnabled(False)
        editor.stop_btn.setEnabled(True)
        if hasattr(editor, "_enter_present_preview"):
            editor._enter_present_preview()
        elif hasattr(editor, "sync_from_controller"):
            editor.sync_from_controller()

    # —— 讲篇放映 ——

    def start_sermon_presentation(self, doc, slide_index: int, assets_root) -> bool:
        if not self.ensure_extension_visible(allow_single_screen=True):
            return False
        if self.sermon_controller.active:
            self.sermon_controller.hot_update(doc, index=slide_index, assets_root=assets_root)
            self._projection_channel = "sermon"
            self.extension_window.set_display_mode("sermon", animate=True)
            self._set_extension_scroll_sync(False)
            self._update_session_chrome()
            return True
        ok = bool(self.sermon_controller.start(doc, slide_index, assets_root))
        if ok:
            self._projection_channel = "sermon"
            self._update_session_chrome()
        return ok

    def stop_sermon_presentation(self):
        editor = getattr(self, "_sermon_editor", None)
        self._keep_editor_after_stop = bool(editor is not None and editor.isVisible())
        self._abort_extension_sermon_layer()
        if not self.sermon_controller.active:
            self._projection_channel = "scripture"
            self._set_extension_scroll_sync(True)
            self._update_session_chrome()
            return
        self.sermon_controller.stop()

    def sermon_presentation_hot_update(self, doc, slide_index: int, assets_root=None):
        if not self.sermon_controller.active:
            return
        self.sermon_controller.hot_update(doc, index=slide_index, assets_root=assets_root)

    def sermon_presentation_go_to(self, slide_index: int):
        if self.sermon_controller.active:
            self.sermon_controller.go_to(slide_index)

    def _on_sermon_started(self, doc, index, assets_root):
        ext = self.extension_window
        if ext is None:
            return
        slide = doc.slides[index]
        ext.show_sermon_slide(doc, slide, assets_root, prepare_anims=True)
        ext.set_display_mode("sermon", animate=True)
        self._set_extension_scroll_sync(False)
        self._last_sermon_index = index
        self._projection_channel = "sermon"
        gen = self.sermon_controller.generation
        wait = self._channel_fade_wait_ms()
        QTimer.singleShot(
            wait,
            self._after_sermon(
                gen,
                lambda: self._cache_current_and_prefetch(doc, index, slide),
            ),
        )
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and hasattr(editor, "mirror_present_slide"):
            if getattr(editor, "_presenting", False):
                QTimer.singleShot(
                    self._channel_fade_wait_ms(),
                    lambda: editor.mirror_present_slide(
                        doc, index, assets_root, prepare_anims=True, anim_cursor=0
                    ),
                )
        QTimer.singleShot(0, self._update_session_chrome)

    def _on_sermon_stopped(self):
        self._abort_extension_sermon_layer()
        self._projection_channel = "scripture"
        self._set_extension_scroll_sync(True)
        self._update_session_chrome()
        editor = getattr(self, "_sermon_editor", None)
        keep = bool(getattr(self, "_keep_editor_after_stop", True))
        self._keep_editor_after_stop = True
        if editor is not None:
            editor.on_presentation_stopped(reshow=keep)
        self._update_status()

    def _on_sermon_slide_changed(self, doc, index, assets_root):
        if not self.extension_window:
            return
        if index < 0 or index >= len(doc.slides):
            return
        ctrl = self.sermon_controller
        gen = int(ctrl.generation)
        hot = bool(getattr(ctrl, "_hot_refresh", False))
        ctrl._hot_refresh = False
        pending_reveal = bool(getattr(ctrl, "_pending_reveal", False))
        ctrl._pending_reveal = False
        slide = doc.slides[index]
        stage = self.extension_window.slide_stage

        if self._projection_channel != "sermon":
            self._update_session_chrome()
            return

        editor = getattr(self, "_sermon_editor", None)

        if hot:
            self.extension_window.show_sermon_slide(
                doc, slide, assets_root, prepare_anims=True
            )
            played = slide.sorted_animations()[: max(0, int(ctrl.anim_cursor))]
            if played:
                stage.apply_played_steps(played)
            if editor is not None and hasattr(editor, "mirror_present_slide"):
                editor.mirror_present_slide(
                    doc,
                    index,
                    assets_root,
                    prepare_anims=True,
                    anim_cursor=int(ctrl.anim_cursor),
                )
            self._prefetch_next_sermon_slide(doc, index)
            self._update_session_chrome()
            return

        tr = getattr(slide, "transition", None)
        kind = getattr(tr, "kind", "none") if tr is not None else "none"
        dur = int(getattr(tr, "duration_ms", 0) or 0) if tr is not None else 0
        use_transition = kind not in ("", "none") and dur >= 40
        last = getattr(self, "_last_sermon_index", -1)
        forward = index >= last
        self._last_sermon_index = index
        prepare = not pending_reveal

        old_pix = stage.take_old_snapshot()
        new_pix = stage.cached_slide_pixmap(doc, slide, prepare_anims=prepare)
        if new_pix.isNull():
            new_pix = stage.render_slide_pixmap(doc, slide, prepare_anims=prepare)

        def _mirror_editor():
            if not self._sermon_alive(gen):
                return
            ed = getattr(self, "_sermon_editor", None)
            if ed is not None and hasattr(ed, "mirror_present_slide"):
                ed.mirror_present_slide(
                    doc,
                    index,
                    assets_root,
                    prepare_anims=prepare,
                    anim_cursor=(
                        0 if prepare else len(slide.sorted_animations())
                    ),
                    pending_reveal=pending_reveal,
                )

        def _rebuild_live():
            if not self._sermon_alive(gen) or self.extension_window is None:
                return
            self.extension_window.show_sermon_slide(
                doc, slide, assets_root, prepare_anims=prepare
            )
            if pending_reveal:
                stage.reveal_all()
                if editor is not None and hasattr(editor, "mirror_present_reveal"):
                    editor.mirror_present_reveal()
            stage.release_hold()
            if not pending_reveal and hasattr(ctrl, "maybe_auto_start"):
                QTimer.singleShot(50, self._after_sermon(gen, ctrl.maybe_auto_start))
            QTimer.singleShot(400, self._after_sermon(gen, _mirror_editor))
            QTimer.singleShot(
                450,
                self._after_sermon(gen, lambda: self._prefetch_next_sermon_slide(doc, index)),
            )
            QTimer.singleShot(50, self._after_sermon(gen, self._update_session_chrome))

        def _commit_scene():
            if not self._sermon_alive(gen) or self.extension_window is None:
                return
            if not new_pix.isNull():
                stage.hold_pixmap(new_pix)
                stage.set_old_snapshot(new_pix)
            QTimer.singleShot(0, self._after_sermon(gen, _rebuild_live))

        if (
            use_transition
            and old_pix is not None
            and not old_pix.isNull()
            and new_pix is not None
            and not new_pix.isNull()
        ):
            stage.play_dual_pixmap_transition(
                kind, dur, old_pix, new_pix, forward=forward, on_done=_commit_scene
            )
        else:
            _commit_scene()

    def _channel_fade_wait_ms(self) -> int:
        try:
            ms = int(self.settings.get("channel_fade_ms", 400) or 400)
        except (TypeError, ValueError):
            ms = 400
        if ms < 40:
            return 80
        return ms + 50

    def _cache_current_and_prefetch(self, doc, index: int, slide):
        ext = self.extension_window
        if ext is None or not self.sermon_controller.active:
            return
        pix = ext.slide_stage.render_slide_pixmap(doc, slide, prepare_anims=True)
        if pix is not None and not pix.isNull():
            ext.slide_stage.set_old_snapshot(pix)
        self._prefetch_next_sermon_slide(doc, index)

    def _prefetch_next_sermon_slide(self, doc, index: int):
        if not self.sermon_controller.active or doc is None:
            return
        ext = self.extension_window
        if ext is None:
            return
        nxt = index + 1
        if nxt < 0 or nxt >= len(doc.slides):
            return
        ext.slide_stage.prefetch_slide(doc, doc.slides[nxt], prepare_anims=True)

    def _on_sermon_steps(self, steps):
        """同批入场：副屏立刻播；主屏预览与底栏延后，减轻卡顿。"""
        batch = list(steps or [])
        if not batch:
            return
        gen = self.sermon_controller.generation
        if self.extension_window and self._projection_channel == "sermon":
            self.extension_window.slide_stage.play_steps(batch)
        cursor = int(self.sermon_controller.anim_cursor)
        QTimer.singleShot(
            160,
            self._after_sermon(
                gen, lambda b=list(batch), c=cursor: self._deferred_step_chrome(b, c)
            ),
        )

    def _deferred_step_chrome(self, batch, anim_cursor: int):
        if not self.sermon_controller.active:
            return
        if hasattr(self, "session_bar"):
            self.session_bar.set_channel(
                self._projection_channel, self._sermon_session_status_text()
            )
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None and hasattr(editor, "mirror_present_steps"):
            editor.mirror_present_steps(batch, anim_cursor=int(anim_cursor))
        elif (
            editor is not None
            and editor.isVisible()
            and hasattr(editor, "sync_from_controller")
        ):
            editor.sync_from_controller(rebuild_canvas=False)

    def _on_sermon_resume(self, doc, index, assets_root, anim_cursor):
        if not self.extension_window:
            return
        if index < 0 or index >= len(doc.slides):
            return
        slide = doc.slides[index]
        ext = self.extension_window
        same = ext.showing_sermon_slide_id() == getattr(slide, "id", None)
        if not same:
            ext.show_sermon_slide(doc, slide, assets_root, prepare_anims=True)
            played = slide.sorted_animations()[: max(0, int(anim_cursor))]
            if played:
                ext.slide_stage.apply_played_steps(played)
        ext.slide_stage.show()
        ext.slide_stage.lower()

    def _on_sermon_status(self, text: str):
        if self.sermon_controller.active:
            return
        self.status_label.setText(text or "")

    def _toggle_extension_topmost(self, on):
        self.settings["extension_topmost"] = bool(on)
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.apply_topmost(on)
            self.extension_window.showFullScreen()
        self.config.save_display_settings({"extension_topmost": bool(on)})

    def _on_scroll_speed(self, speed):
        self.scripture_display.set_scroll_speed(speed)
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.set_scroll_speed(0)

    def _scroll_manual(self, delta):
        self.scripture_display.scroll_by(delta)

    def _toggle_scroll_pause(self):
        current = self.toolbar.current_speed()
        if current > 0:
            self._last_speed = current
            self.toolbar._set_speed(0)
        else:
            self.toolbar._set_speed(getattr(self, "_last_speed", 3))

    # --- 方向键：逻辑连续节导航（内联原 arrow_navigation_patch） ---

    def _logical_range(self, book, chapter, verse):
        label, _text = self.db.get_verse_display_info(book, chapter, verse)
        text = str(label or "").strip()
        if "-" in text:
            start_text, end_text = text.split("-", 1)
            try:
                return int(start_text), int(end_text)
            except ValueError:
                pass
        try:
            value = int(text)
        except ValueError:
            value = int(verse)
        return value, value

    def _next_logical_start(self, book, chapter, verse):
        _start, end = self._logical_range(book, chapter, verse)
        candidate = end + 1
        max_v = self.db.get_verse_count(book, chapter)
        if candidate > max_v:
            return None
        start, _end = self._logical_range(book, chapter, candidate)
        return start

    def _previous_logical_range(self, book, chapter, verse):
        start, _end = self._logical_range(book, chapter, verse)
        candidate = start - 1
        if candidate < 1:
            return None
        return self._logical_range(book, chapter, candidate)

    def _current_scroll_y(self):
        try:
            return float(self.scripture_display.text_display.scroll_y())
        except (AttributeError, TypeError, ValueError):
            return 0.0

    def _replace_history_selection(self, old_selection, new_selection):
        history = getattr(self.nav_panel, "history", None)
        if not history:
            return
        for index, item in enumerate(history):
            if item == old_selection:
                history[index] = new_selection
                self.nav_panel._update_history_list(selected_index=index)
                self.nav_panel.history_changed.emit(
                    [entry.to_history_entry() for entry in history]
                )
                return

    def _load_and_restore(self, selection, scroll_y):
        old_selection = getattr(self, "current_selection", None)
        self._load_selection(
            selection, reset_scroll=False, restore_scroll_y=scroll_y
        )
        if old_selection is not None:
            self._replace_history_selection(old_selection, self.current_selection)
        self.nav_panel.sync_from_selection(self.current_selection)

    def _add_verse_end(self):
        selection = self._simple_selection_or_none()
        if selection is None:
            return
        scroll_y = self._current_scroll_y()
        span = selection.spans[0]
        next_start = self._next_logical_start(selection.book, span.chapter, span.end)
        if next_start is None:
            return
        self._load_and_restore(
            ScriptureSelection.single_chapter(
                selection.book, span.chapter, span.start, next_start
            ),
            scroll_y,
        )

    def _remove_verse_end(self):
        selection = self._simple_selection_or_none()
        if selection is None:
            return
        scroll_y = self._current_scroll_y()
        span = selection.spans[0]
        current_start, _current_end = self._logical_range(
            selection.book, span.chapter, span.end
        )

        if current_start > span.start:
            new_end = current_start - 1
            _prev_start, prev_end = self._logical_range(
                selection.book, span.chapter, new_end
            )
            new_end = prev_end
            if new_end < span.start:
                return
            target_start = span.start
        else:
            previous = self._previous_logical_range(
                selection.book, span.chapter, current_start
            )
            if previous is None:
                return
            target_start, new_end = previous

        self._load_and_restore(
            ScriptureSelection.single_chapter(
                selection.book, span.chapter, target_start, new_end
            ),
            scroll_y,
        )

    def _add_verse_start(self):
        selection = self._simple_selection_or_none()
        if selection is None:
            return
        scroll_y = self._current_scroll_y()
        span = selection.spans[0]
        previous = self._previous_logical_range(
            selection.book, span.chapter, span.start
        )
        if previous is None:
            return
        prev_start, _prev_end = previous
        self._load_and_restore(
            ScriptureSelection.single_chapter(
                selection.book, span.chapter, prev_start, span.end
            ),
            scroll_y,
        )

    def _remove_verse_start(self):
        selection = self._simple_selection_or_none()
        if selection is None:
            return
        scroll_y = self._current_scroll_y()
        span = selection.spans[0]
        start, end = self._logical_range(
            selection.book, span.chapter, span.start
        )
        if end >= span.end:
            return
        new_start = end + 1
        new_start, _new_end = self._logical_range(
            selection.book, span.chapter, new_start
        )
        if new_start > span.end:
            return
        self._load_and_restore(
            ScriptureSelection.single_chapter(
                selection.book, span.chapter, new_start, span.end
            ),
            scroll_y,
        )

    def _simple_selection_or_none(self):
        if self.current_selection is None or not self.verses:
            return None
        if not self.current_selection.is_simple:
            self.status_label.setText("跨章或跳节选择请用搜索调整范围")
            return None
        return self.current_selection

    def _refresh_display(self):
        if self.current_selection is not None:
            self.scripture_display.set_from_selection(self.current_selection, self.verses)
            if self.extension_window and self.extension_window.isVisible():
                self.extension_window.update_from_selection(
                    self.current_selection, self.verses
                )
                self._sync_extension_scroll()
        else:
            self.scripture_display.set_scripture(
                self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
            )
            if self.extension_window and self.extension_window.isVisible():
                self.extension_window.update_scripture(
                    self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
                )
                self._sync_extension_scroll()
        self._update_status()

    def _sync_extension_scroll(self, value=None):
        if self._syncing_scroll or not self.extension_window or not self.extension_window.isVisible():
            return
        if getattr(self.extension_window, "display_mode", None) == "sermon":
            return
        self._syncing_scroll = True
        try:
            self.extension_window.sync_from_main(self.scripture_display)
        finally:
            self._syncing_scroll = False

    def closeEvent(self, event):
        editor = getattr(self, "_sermon_editor", None)
        if editor is not None:
            # 彻底关程序才问保存；叠层本身回经文不弹窗
            if hasattr(editor, "confirm_close_app"):
                if not editor.confirm_close_app():
                    event.ignore()
                    return
            elif editor.isVisible() and hasattr(editor, "request_close"):
                if not editor.request_close():
                    event.ignore()
                    return
            if editor.isVisible():
                editor.hide()
        try:
            self.config.save_window_state(self.saveGeometry())
        except Exception:
            pass
        if self.extension_window:
            self.extension_window.hide()
        try:
            self.db.close()
        except Exception:
            pass
        super().closeEvent(event)

"""主窗口：业务逻辑（含方向键逻辑导航与扩展屏滚动同步）。"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QSplitter,
    QStatusBar,
    QLabel,
    QApplication,
    QAbstractSpinBox,
    QLineEdit,
    QAbstractItemView,
    QTextEdit,
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

        self._create_central_widget()
        self._create_toolbar()
        self._create_shortcuts()
        self._create_statusbar()
        self._load_theme_style()
        self.nav_panel.load_history(config.load_history())
        self.nav_panel.history_changed.connect(self._save_history)
        self._apply_settings(self.settings)

        # v1：16ms 定时 + scroll_changed 持续按比例同步副屏；副屏自身不滚
        self._extension_sync_timer = QTimer(self)
        self._extension_sync_timer.setInterval(16)
        self._extension_sync_timer.timeout.connect(self._sync_extension_scroll)

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
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.nav_panel = NavigationPanel(self.db)
        self.nav_panel.book_selected.connect(self._on_book_selected)
        self.nav_panel.range_selected.connect(self._on_range_selected)
        self.nav_panel.history_opened.connect(self._on_history_opened)
        self.nav_panel.verse_segmentation_changed.connect(self._on_verse_segmentation_changed)
        splitter.addWidget(self.nav_panel)
        self.preview_host = PreviewHost()
        self.scripture_display = self.preview_host.display
        splitter.addWidget(self.preview_host)
        splitter.setSizes([360, 840])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)
        layout.addWidget(splitter)
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _focus_blocks_nav_shortcuts(self):
        w = QApplication.focusWidget()
        if w is None:
            return False
        if isinstance(w, (QAbstractSpinBox, QLineEdit, QTextEdit, QAbstractItemView)):
            return True
        return False

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
            (Qt.Key.Key_Escape, self._close_extension, False),
            (Qt.Key.Key_F12, self._toggle_extension, False),
            (Qt.Key.Key_F1, self.toolbar._open_help, False),
            (Qt.Key.Key_Right, self._add_verse_end, True),
            (Qt.Key.Key_Left, self._remove_verse_end, True),
            ("Ctrl+Right", self._add_verse_start, True),
            ("Ctrl+Left", self._remove_verse_start, True),
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

    def _show_search(self):
        if hasattr(self, "search_widget") and self.search_widget.isVisible():
            self.search_widget.close()
            return
        self.search_widget = SearchWidget(self.db, self, theme=self.theme)
        self.search_widget.search_triggered.connect(self._on_search_result)
        self.search_widget.close_requested.connect(self._close_search)
        self.search_widget.move(self.mapToGlobal(QPoint(self.width() // 2 - 330, 72)))
        self.search_widget.show()
        self.search_widget.search_input.setFocus()

    def _close_search(self):
        if hasattr(self, "search_widget"):
            self.search_widget.close()

    def _on_search_result(self, selection):
        selection = self._coerce_selection(selection)
        if selection is None:
            return
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
            if reset_scroll:
                QApplication.processEvents()
            self._sync_extension_scroll()
        self._update_status()

    def _update_status(self):
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
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.hide()
            self._extension_sync_timer.stop()
            self.toolbar.set_extend_active(False)
            self.status_label.setText("扩展显示已关闭（预览仍按副屏分辨率缩放）")

    def _show_extension(self):
        screens = QApplication.screens()
        if len(screens) < 2:
            self.status_label.setText("未检测到第二块屏幕")
            return
        topmost = bool(self.settings.get("extension_topmost", True))
        if not self.extension_window:
            self.extension_window = ExtensionWindow(topmost=topmost)
            self.extension_window.close_requested.connect(self._close_extension)
            self.extension_window.apply_settings(self.settings)
        else:
            self.extension_window.apply_topmost(topmost)

        primary = QApplication.primaryScreen()
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
        if self.verses and self.current_selection is not None:
            self.extension_window.update_from_selection(self.current_selection, self.verses)
        elif self.verses:
            self.extension_window.update_scripture(
                self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
            )
        self.extension_window.set_scroll_speed(0)
        QApplication.processEvents()
        self.preview_host._fit_view()
        QApplication.processEvents()
        self._sync_extension_scroll()
        self._extension_sync_timer.start()
        self.toolbar.set_extend_active(True)
        self.status_label.setText(
            f"扩展显示: {target.name()} ({stage_w}x{stage_h})，预览已按副屏等比缩放"
        )

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
                QApplication.processEvents()
                self._sync_extension_scroll()
        else:
            self.scripture_display.set_scripture(
                self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
            )
            if self.extension_window and self.extension_window.isVisible():
                self.extension_window.update_scripture(
                    self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
                )
                QApplication.processEvents()
                self._sync_extension_scroll()
        self._update_status()

    def _sync_extension_scroll(self, value=None):
        if self._syncing_scroll or not self.extension_window or not self.extension_window.isVisible():
            return
        self._syncing_scroll = True
        try:
            self.extension_window.sync_from_main(self.scripture_display)
        finally:
            self._syncing_scroll = False

    def closeEvent(self, event):
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

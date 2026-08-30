# 主窗口 - 业务逻辑层
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar, QLabel, QApplication,
    QAbstractSpinBox, QLineEdit, QAbstractItemView, QTextEdit,
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from config import AppConfig
from bible_database import BibleDatabase
from ui import SearchWidget, NavigationPanel, ToolBarWidget, ExtensionWindow, PreviewHost
from ui.themes import THEMES


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
        self.verses = []
        self.settings = config.load_display_settings()
        self.theme = self.settings.get("theme", "dark")
        self._last_speed = 3
        self.setWindowTitle("圣经投影系统")
        self.setMinimumSize(800, 600)

        geometry = config.load_window_state()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 800)

        self._load_theme_style()
        self._create_central_widget()
        self._create_toolbar()
        self._create_shortcuts()
        self._create_statusbar()
        self.nav_panel.load_history(config.load_history())
        self.nav_panel.history_changed.connect(self._save_history)
        self._apply_settings(self.settings)

        self._extension_sync_timer = QTimer(self)
        self._extension_sync_timer.setInterval(16)
        self._extension_sync_timer.timeout.connect(self._sync_extension_scroll)

    def _save_history(self, h):
        self.config.save_history(h)

    def _load_theme_style(self):
        # 按源码目录定位 QSS，不依赖启动时的 cwd
        p = Path(__file__).resolve().parent / "styles" / f"{self.theme}.qss"
        app = QApplication.instance()
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            return
        # QSS 缺失时用 themes.py 兜底，保证 THEMES 真正参与渲染
        t = THEMES.get(self.theme, THEMES["dark"])
        app.setStyleSheet(
            f"""
            QMainWindow {{ background: {t.get('window_bg', t['panel_bg'])}; color: {t['text_primary']}; }}
            QStatusBar {{ background: {t['toolbar_bg']}; color: {t['text_secondary']}; }}
            QToolBar {{ background: {t['toolbar_bg']}; border: none; spacing: 8px; padding: 8px 12px; }}
            QToolBar QPushButton {{ background: {t['item_bg']}; color: {t['text_primary']}; border-radius: 6px; padding: 7px 12px; }}
            #extendBtn {{ background: {t['accent']}; color: white; }}
            QLabel {{ color: {t['text_secondary']}; font-size: 12px; }}
            QListWidget {{ background: {t['panel_bg']}; color: {t['text_primary']}; border: none; }}
            QListWidget::item:selected {{ background: {t['accent']}; color: white; }}
            QTabWidget::pane {{ background: {t['panel_bg']}; border: none; }}
            """
        )

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
        """焦点在输入控件/列表时，不抢方向键、数字键、空格等。"""
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
        # Enter/Esc/F12 全局可用；方向键/空格/数字在导航面板输入时让出
        bindings = [
            (Qt.Key.Key_Return, self._show_search, False),
            (Qt.Key.Key_Enter, self._show_search, False),
            (Qt.Key.Key_Escape, self._close_extension, False),
            (Qt.Key.Key_F12, self._toggle_extension, False),
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
        # 自动滚到底后，工具栏同步为暂停
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
            QApplication.processEvents()
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
        self.search_widget = SearchWidget(self.db, self)
        self.search_widget.search_triggered.connect(self._on_search_result)
        self.search_widget.close_requested.connect(self._close_search)
        self.search_widget.move(self.mapToGlobal(QPoint(self.width() // 2 - 180, 80)))
        self.search_widget.show()
        self.search_widget.search_input.setFocus()

    def _close_search(self):
        if hasattr(self, "search_widget"):
            self.search_widget.close()

    def _on_search_result(self, p):
        b, c, s, e = p
        self._load_scripture(b, c, s, e)
        self.nav_panel.add_to_history(b, c, self.current_start, self.current_end)
        self.nav_panel.sync_selection(b, c, self.current_start, self.current_end)
        self._close_search()

    def _on_book_selected(self, b, c):
        self._load_scripture(b, c, None, None)
        # 历史与投影一致：整章
        self.nav_panel.add_to_history(b, c, self.current_start, self.current_end)
        self.nav_panel.sync_selection(b, c, self.current_start, self.current_end)

    def _on_verse_segmentation_changed(self, e):
        enabled = bool(e)
        self.settings["verse_segmentation"] = enabled
        self.scripture_display.set_verse_segmentation(enabled)
        # 扩展屏同步分段状态
        if self.extension_window:
            self.extension_window.scripture_display.set_verse_segmentation(enabled)
        QApplication.processEvents()
        self._sync_extension_scroll()
        self.config.save_display_settings({"verse_segmentation": enabled})

    def _on_range_selected(self, b, c, s, e):
        self._load_scripture(b, c, s, e)
        self.nav_panel.add_to_history(b, c, self.current_start, self.current_end)

    def _on_history_opened(self, b, c, s, e):
        # 从历史点开：只投影，不重排历史
        self._load_scripture(b, c, s, e)

    def _load_scripture(self, b, c, s, e):
        self.current_book = b
        self.current_chapter = c
        if s is None:
            v = self.db.get_verse_range(b, c, 1)
            self.current_start = 1
            self.current_end = v[-1][0] if v else 0
        else:
            v = self.db.get_verse_range(b, c, s, e)
            self.current_start = s
            self.current_end = (v[-1][0] if v else 0) if e is None else e
        self.verses = v
        self.scripture_display.set_scripture(b, c, self.current_start, self.current_end, v)
        if self.extension_window and self.extension_window.isVisible():
            QApplication.processEvents()
            self.extension_window.update_scripture(b, c, self.current_start, self.current_end, v)
            QApplication.processEvents()
            self._sync_extension_scroll()
        self._update_status()

    def _update_status(self):
        if self.current_book:
            self.status_label.setText(
                f"{self.current_book} {self.current_chapter}:{self.current_start}-{self.current_end}"
            )
        else:
            self.status_label.setText("按回车键打开搜索")

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
            # 保留最后一次副屏舞台尺寸，预览继续按该分辨率 letterbox，避免排版跳变
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

        # 优先选非主屏作为投影屏
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

        # 预览与副屏使用同一舞台分辨率排版
        self.preview_host.set_stage_size(stage_w, stage_h)
        self.extension_window.scripture_display.set_stage_size(stage_w, stage_h)
        self.extension_window.setGeometry(geom)
        self.extension_window.showFullScreen()
        if self.verses:
            self.extension_window.update_scripture(
                self.current_book, self.current_chapter, self.current_start, self.current_end, self.verses
            )
        self.extension_window.set_scroll_speed(0)
        QApplication.processEvents()
        # 舞台尺寸变化后预览文档高度会变，再同步一次滚动
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

    def _add_verse_end(self):
        if not self.verses:
            return
        max_v = self.db.get_verse_count(self.current_book, self.current_chapter)
        if self.current_end < max_v:
            self.current_end += 1
            self.verses = self.db.get_verse_range(
                self.current_book, self.current_chapter, self.current_start, self.current_end
            )
            self._refresh_display()

    def _remove_verse_end(self):
        if not self.verses or self.current_end <= self.current_start:
            return
        self.current_end -= 1
        self.verses = self.db.get_verse_range(
            self.current_book, self.current_chapter, self.current_start, self.current_end
        )
        self._refresh_display()

    def _add_verse_start(self):
        if not self.verses or self.current_start <= 1:
            return
        self.current_start -= 1
        self.verses = self.db.get_verse_range(
            self.current_book, self.current_chapter, self.current_start, self.current_end
        )
        self._refresh_display()

    def _remove_verse_start(self):
        if not self.verses or self.current_start >= self.current_end:
            return
        self.current_start += 1
        self.verses = self.db.get_verse_range(
            self.current_book, self.current_chapter, self.current_start, self.current_end
        )
        self._refresh_display()

    def _refresh_display(self):
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
        # 退出时保存窗口几何并关闭数据库
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

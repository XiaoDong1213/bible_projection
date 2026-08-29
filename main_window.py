# main_window.py
# 主窗口 - 业务逻辑层
# 功能：协调各UI组件，处理快捷键、双屏同步、事件响应

import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar, QLabel, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from config import AppConfig
from bible_database import BibleDatabase
from ui import ScriptureDisplay, SearchWidget, NavigationPanel, ToolBarWidget, ExtensionWindow


class MainWindow(QMainWindow):
    def __init__(self, db: BibleDatabase, config: AppConfig):
        super().__init__()
        self.db = db
        self.config = config
        self.extension_window = None
        self.current_book = None
        self.current_chapter = None
        self.current_start = None
        self.current_end = None
        self.verses = []
        self.settings = config.load_display_settings()
        self.theme = self.settings.get("theme", "dark")
        self.setWindowTitle("圣经投影系统")
        self.setMinimumSize(800, 600)
        geometry = config.load_window_state()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 800)
        self._load_theme_style()

        # 必须先创建中心区域，再创建依赖 scripture_display/nav_panel 的工具栏
        self._create_central_widget()
        self._create_toolbar()
        self._create_shortcuts()
        self._create_statusbar()

        history = config.load_history()
        self.nav_panel.load_history(history)
        self._apply_settings(self.settings)

    def _load_theme_style(self):
        style_path = os.path.join("styles", f"{self.theme}.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())

    def _create_toolbar(self):
        self.toolbar = ToolBarWidget()
        self.addToolBar(self.toolbar)
        self.toolbar.theme = self.theme
        if self.theme == "light":
            self.toolbar.theme_btn.setText("🌙 暗色")
        self.toolbar.load_settings(self.settings)
        self.toolbar.scroll_speed_changed.connect(self._on_scroll_speed)
        self.toolbar.extend_toggled.connect(self._toggle_extension)
        self.toolbar.settings_changed.connect(self._on_settings_changed)
        self.toolbar.footer_triggered.connect(self._set_footer_text)
        self.toolbar.theme_changed.connect(self._on_theme_changed)
        self.toolbar.topmost_toggled.connect(self._toggle_extension_topmost)
        self.toolbar.scroll_up.connect(lambda: self._scroll_manual(-40))
        self.toolbar.scroll_down.connect(lambda: self._scroll_manual(40))
        self.scripture_display.scroll_changed.connect(self._sync_extension_scroll)

    def _create_central_widget(self):
        central = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.nav_panel = NavigationPanel(self.db)
        self.nav_panel.book_selected.connect(self._on_book_selected)
        splitter.addWidget(self.nav_panel)
        self.scripture_display = ScriptureDisplay()
        splitter.addWidget(self.scripture_display)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 990])
        main_layout.addWidget(splitter)
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    def _create_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._show_search)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._show_search)
        QShortcut(QKeySequence(Qt.Key.Key_F12), self, self._toggle_extension)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._add_verse_end)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._remove_verse_end)
        QShortcut(QKeySequence("Ctrl+Right"), self, self._add_verse_start)
        QShortcut(QKeySequence("Ctrl+Left"), self, self._remove_verse_start)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, lambda: self._scroll_manual(-30))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, lambda: self._scroll_manual(30))
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_scroll_pause)

    def _create_statusbar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("按回车键打开搜索")
        status.addWidget(self.status_label)

    def _on_settings_changed(self, settings):
        self.settings.update(settings)
        self._apply_settings(settings)
        self.config.save_display_settings(settings)

    def _apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)
        if self.extension_window:
            self.extension_window.apply_settings(settings)

    def _on_theme_changed(self, theme):
        self.theme = theme
        self.settings["theme"] = theme
        self._load_theme_style()
        self.config.save_display_settings(self.settings)

    # 以下业务方法保持原项目接口；若项目已有实现，请继续保留其余代码

# main_window.py
# 主窗口 - 业务逻辑层
# 功能：协调各UI组件，处理快捷键、双屏同步、事件响应

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar,
    QLabel, QInputDialog, QApplication
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QKeySequence

from PyQt6.QtGui import QShortcut

from config import AppConfig
from bible_database import BibleDatabase
from ui import (
    ScriptureDisplay, SearchWidget, NavigationPanel,
    ToolBarWidget, ExtensionWindow
)


class MainWindow(QMainWindow):
    def __init__(self, db: BibleDatabase, config: AppConfig):
        super().__init__()
        self.db = db
        self.config = config
        self.extension_window = None  # 扩展窗口对象

        # 当前经文状态
        self.current_book = None
        self.current_chapter = None
        self.current_start = None
        self.current_end = None
        self.verses = []

        # 加载配置
        self.settings = config.load_display_settings()
        self.theme = self.settings.get("theme", "dark")

        # 窗口初始化
        self.setWindowTitle("圣经投影系统")
        self.setMinimumSize(800, 600)

        # 恢复上次窗口大小位置
        geometry = config.load_window_state()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 800)

        # 加载主题样式
        self._load_theme_style()

        # 创建界面各部分
        self._create_toolbar()
        self._create_central_widget()
        self._create_shortcuts()
        self._create_statusbar()

        # 加载历史记录
        history = config.load_history()
        self.nav_panel.load_history(history)

        # 应用初始显示设置
        self._apply_settings(self.settings)

    # ============== 主题加载 ==============
    def _load_theme_style(self):
        """加载QSS主题样式文件到全局"""
        style_path = os.path.join("styles", f"{self.theme}.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                qApp = QApplication.instance()
                qApp.setStyleSheet(f.read())

    # ============== 工具栏 ==============
    def _create_toolbar(self):
        """创建顶部工具栏并连接信号"""
        self.toolbar = ToolBarWidget()
        self.addToolBar(self.toolbar)

        # 同步主题按钮文字
        self.toolbar.theme = self.theme
        if self.theme == "light":
            self.toolbar.theme_btn.setText("🌙 暗色")

        # 加载配置到工具栏
        self.toolbar.load_settings(self.settings)

        # 连接所有信号
        self.toolbar.scroll_speed_changed.connect(self._on_scroll_speed)
        self.toolbar.extend_toggled.connect(self._toggle_extension)
        self.toolbar.settings_changed.connect(self._on_settings_changed)
        self.toolbar.footer_triggered.connect(self._set_footer_text)
        self.toolbar.theme_changed.connect(self._on_theme_changed)
        self.toolbar.topmost_toggled.connect(self._toggle_extension_topmost)
        self.toolbar.scroll_up.connect(lambda: self._scroll_manual(-40))
        self.toolbar.scroll_down.connect(lambda: self._scroll_manual(40))

    # ============== 中心区域 ==============
    def _create_central_widget(self):
        """创建中心布局：左侧导航 + 经文显示"""
        central = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 分割器，可拖拽调整宽度
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧导航面板
        self.nav_panel = NavigationPanel(self.db)
        self.nav_panel.book_selected.connect(self._on_book_selected)
        splitter.addWidget(self.nav_panel)

        # 经文显示区域
        self.scripture_display = ScriptureDisplay()
        splitter.addWidget(self.scripture_display)

        # 设置伸缩比例：导航固定宽，经文占满剩余
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 990])

        main_layout.addWidget(splitter)
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    # ============== 快捷键 ==============
    def _create_shortcuts(self):
        """注册全局快捷键"""
        # 回车呼出搜索
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._show_search)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._show_search)

        # F12 切换扩展
        QShortcut(QKeySequence(Qt.Key.Key_F12), self, self._toggle_extension)

        # 左右箭头：尾部加减一节
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._add_verse_end)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._remove_verse_end)

        # Ctrl+左右箭头：头部加减一节
        QShortcut(QKeySequence("Ctrl+Right"), self, self._add_verse_start)
        QShortcut(QKeySequence("Ctrl+Left"), self, self._remove_verse_start)

        # 上下键：手动滚动
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, lambda: self._scroll_manual(-30))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, lambda: self._scroll_manual(30))

        # 空格：暂停/继续滚动
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_scroll_pause)

    # ============== 状态栏 ==============
    def _create_statusbar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("按回车键打开搜索")
        status.addWidget(self.status_label)

    # ============== 设置处理 ==============
    def _on_settings_changed(self, settings):
        """设置变化时：应用 + 保存"""
        self.settings.update(settings)
        self._apply_settings(settings)
        self.config.save_display_settings(settings)

    def _apply_settings(self, settings):
        """应用设置到主界面和扩展屏"""
        self.scripture_display.apply_settings(settings)
        if self.extension_window:
            self.extension_window.apply_settings(settings)

    def _on_theme_changed(self, theme):
        """主题切换：重新加载QSS + 保存"""
        self.theme = theme
        self.settings["theme"] = theme
        self._load_theme_style()
        self.config.save_display_settings({"theme": theme})

    # ============== 搜索功能 ==============
    def _show_search(self):
        """显示搜索弹窗"""
        # 已打开则关闭
        if hasattr(self, "search_widget") and self.search_widget.isVisible():
            self.search_widget.close()
            return

        self.search_widget = SearchWidget(self.db, self)
        self.search_widget.search_triggered.connect(self._on_search_result)
        self.search_widget.close_requested.connect(self._close_search)

        # 定位到窗口中上位置
        pos = self.mapToGlobal(QPoint(self.width() // 2 - 180, 80))
        self.search_widget.move(pos)
        self.search_widget.show()
        self.search_widget.search_input.setFocus()

    def _close_search(self):
        if hasattr(self, "search_widget"):
            self.search_widget.close()

    def _on_search_result(self, parsed):
        """搜索结果处理：加载经文 + 加历史"""
        book_name, chapter, start_verse, end_verse = parsed
        self._load_scripture(book_name, chapter, start_verse, end_verse)
        self.nav_panel.add_to_history(book_name, chapter, start_verse, end_verse)

    def _on_book_selected(self, book_name, chapter):
        """左侧导航点击书卷"""
        self._load_scripture(book_name, chapter, None, None)

    # ============== 经文加载 ==============
    def _load_scripture(self, book_name, chapter, start_verse, end_verse):
        """加载并显示指定范围经文"""
        self.current_book = book_name
        self.current_chapter = chapter
        self.current_start = start_verse
        self.current_end = end_verse

        # 获取经文数据
        if start_verse is None:
            # 整章
            verses = self.db.get_verse_range(book_name, chapter, 1)
            self.current_start = 1
            self.current_end = len(verses)
        else:
            verses = self.db.get_verse_range(book_name, chapter, start_verse, end_verse)
            # 结束节为空时，计算实际结束节号
            if end_verse is None:
                self.current_end = len(verses) + start_verse - 1

        self.verses = verses

        # 主界面显示
        self.scripture_display.set_scripture(
            book_name, chapter, start_verse,
            self.current_end if end_verse is None else end_verse,
            verses
        )

        # 同步扩展屏
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.update_scripture(
                book_name, chapter, start_verse,
                self.current_end if end_verse is None else end_verse,
                verses
            )

        self._update_status()

    def _update_status(self):
        """更新状态栏提示"""
        if self.current_start is None:
            status = f"{self.current_book} 第{self.current_chapter}章（整章）"
        elif self.current_end is None:
            status = f"{self.current_book} {self.current_chapter}:{self.current_start}-末"
        elif self.current_start == self.current_end:
            status = f"{self.current_book} {self.current_chapter}:{self.current_start}"
        else:
            status = f"{self.current_book} {self.current_chapter}:{self.current_start}-{self.current_end}"
        self.status_label.setText(status)

    # ============== 扩展显示 ==============
    def _toggle_extension(self):
        """切换扩展显示开关"""
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.hide()
            self.toolbar.set_extend_active(False)
            self.status_label.setText("已关闭扩展显示")
        else:
            self._show_extension()

    def _show_extension(self):
        """在第二屏显示扩展窗口"""
        screens = QApplication.screens()
        if len(screens) < 2:
            self.status_label.setText("未检测到第二块屏幕")
            return

        # 创建窗口
        if not self.extension_window:
            self.extension_window = ExtensionWindow()
            self.extension_window.apply_settings(self.settings)

        # 设置置顶状态
        is_topmost = self.toolbar.topmost_btn.isChecked()
        self.extension_window.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint, is_topmost
        )

        # 移动到第二屏并全屏
        second_screen = screens[1]
        geom = second_screen.geometry()
        self.extension_window.setGeometry(geom)
        self.extension_window.showFullScreen()

        # 同步当前经文
        if self.verses:
            self.extension_window.update_scripture(
                self.current_book, self.current_chapter,
                self.current_start, self.current_end, self.verses
            )

        # 同步滚动速度
        self.extension_window.set_scroll_speed(self.toolbar.scroll_slider.value())

        self.toolbar.set_extend_active(True)
        self.status_label.setText(f"扩展显示: 屏幕2 ({geom.width()}x{geom.height()})")

    def _toggle_extension_topmost(self, on):
        """切换扩展窗口置顶状态"""
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.setWindowFlag(
                Qt.WindowType.WindowStaysOnTopHint, on
            )
            self.extension_window.show()
            self.status_label.setText(f"扩展屏已{'开启' if on else '关闭'}置顶")
            self.config.save_display_settings({"extension_topmost": on})

    # ============== 滚动控制 ==============
    def _on_scroll_speed(self, speed):
        """滚动速度变化，双屏同步"""
        self.scripture_display.set_scroll_speed(speed)
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.set_scroll_speed(speed)

    def _scroll_manual(self, delta):
        """手动滚动，双屏同步"""
        self.scripture_display.scroll_by(delta)
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.scroll_by(delta)

    def _toggle_scroll_pause(self):
        """空格暂停/继续滚动"""
        slider = self.toolbar.scroll_slider
        if slider.value() > 0:
            self._last_speed = slider.value()
            slider.setValue(0)
        else:
            slider.setValue(getattr(self, "_last_speed", 3))

    # ============== 经文加减 ==============
    def _add_verse_end(self):
        """尾部增加一节"""
        if not self.verses:
            return
        max_verse = self.db.get_verse_count(self.current_book, self.current_chapter)
        if self.current_end < max_verse:
            new_end = self.current_end + 1
            new_verse = self.db.get_verse_range(
                self.current_book, self.current_chapter, new_end, new_end
            )
            self.verses.extend(new_verse)
            self.current_end = new_end
            self._refresh_display()

    def _remove_verse_end(self):
        """尾部减少一节"""
        if len(self.verses) > 1:
            self.verses.pop()
            self.current_end -= 1
            self._refresh_display()

    def _add_verse_start(self):
        """头部增加一节"""
        if not self.verses:
            return
        if self.current_start > 1:
            new_start = self.current_start - 1
            new_verse = self.db.get_verse_range(
                self.current_book, self.current_chapter, new_start, new_start
            )
            self.verses = new_verse + self.verses
            self.current_start = new_start
            self._refresh_display()

    def _remove_verse_start(self):
        """头部减少一节"""
        if len(self.verses) > 1:
            self.verses.pop(0)
            self.current_start += 1
            self._refresh_display()

    def _refresh_display(self):
        """刷新双屏显示"""
        self.scripture_display.set_scripture(
            self.current_book, self.current_chapter,
            self.current_start, self.current_end, self.verses
        )
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.update_scripture(
                self.current_book, self.current_chapter,
                self.current_start, self.current_end, self.verses
            )
        self._update_status()

    # ============== 底注 ==============
    def _set_footer_text(self):
        """设置底注文字"""
        text, ok = QInputDialog.getText(
            self, "底注设置",
            "请输入底注文字（留空则不显示文字）:",
            text=self.scripture_display.footer_text
        )
        if ok:
            self.settings["footer_text"] = text
            self.scripture_display.apply_settings(self.settings)
            if self.extension_window:
                self.extension_window.apply_settings(self.settings)
            self.config.save_display_settings({"footer_text": text})

    # ============== 键盘事件 ==============
    def keyPressEvent(self, event):
        """搜索框打开时，优先处理搜索框按键"""
        if hasattr(self, "search_widget") and self.search_widget.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                self._close_search()
            return
        super().keyPressEvent(event)

    # ============== 关闭事件 ==============
    def closeEvent(self, event):
        """关闭窗口时保存状态"""
        # 保存窗口大小位置
        self.config.save_window_state(self.saveGeometry())
        # 保存历史记录
        self.config.save_history(self.nav_panel.get_history())

        # 关闭扩展窗口
        if self.extension_window:
            self.extension_window.close()

        # 关闭数据库
        self.db.close()
        event.accept()

# ui/toolbar.py
# 顶部工具栏：分组布局 + 速度下拉（冷蓝控制台）

from PyQt6.QtWidgets import (
    QToolBar, QPushButton, QLabel, QDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QVBoxLayout, QSpinBox, QFontComboBox, QColorDialog,
    QFileDialog, QLineEdit, QDialogButtonBox, QWidget, QSizePolicy,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class DisplaySettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("显示设置")
        self.setObjectName("settingsDialog")
        self.setMinimumSize(680, 560)
        self.resize(760, 620)
        self.settings = dict(settings)
        self._build_ui()
        self._load_settings()

        # 根据当前屏幕自动适配大小，但不强行压缩到很小
        screen = self.screen()
        if screen:
            available = screen.availableGeometry()
            width = min(760, max(680, available.width() - 80))
            height = min(620, max(560, available.height() - 80))
            self.resize(width, height)
            self.move(
                available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
            )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        # =====================================================
        # 一级标签页
        # =====================================================
        tabs = QTabWidget()
        tabs.setObjectName("settingsTabs")
        tabs.setDocumentMode(True)

        # =====================================================
        # 文字设置：二级标签页
        # =====================================================
        text_page = QWidget()
        text_root = QVBoxLayout(text_page)
        text_root.setContentsMargins(8, 8, 8, 8)
        text_root.setSpacing(8)

        text_tabs = QTabWidget()
        text_tabs.setObjectName("settingsSubTabs")
        text_tabs.setDocumentMode(True)

        # ---------- 正文 ----------
        body_page = QWidget()
        body_form = QFormLayout(body_page)
        body_form.setContentsMargins(20, 20, 20, 20)
        body_form.setHorizontalSpacing(18)
        body_form.setVerticalSpacing(12)

        self.font_combo = QFontComboBox()
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 300)
        self.font_size.setSuffix(" px")
        self.font_color_btn = QPushButton("正文颜色")

        body_form.addRow("正文字体", self.font_combo)
        body_form.addRow("正文字号", self.font_size)
        body_form.addRow("正文颜色", self.font_color_btn)
        text_tabs.addTab(body_page, "正文")

        # ---------- 标题 ----------
        title_page = QWidget()
        title_form = QFormLayout(title_page)
        title_form.setContentsMargins(20, 20, 20, 20)
        title_form.setHorizontalSpacing(18)
        title_form.setVerticalSpacing(12)

        self.title_font_combo = QFontComboBox()
        self.title_size = QSpinBox()
        self.title_size.setRange(12, 300)
        self.title_size.setSuffix(" px")
        self.title_color_btn = QPushButton("标题颜色")

        title_form.addRow("标题字体", self.title_font_combo)
        title_form.addRow("标题字号", self.title_size)
        title_form.addRow("标题颜色", self.title_color_btn)
        text_tabs.addTab(title_page, "标题")

        # ---------- 节号 ----------
        verse_page = QWidget()
        verse_form = QFormLayout(verse_page)
        verse_form.setContentsMargins(20, 20, 20, 20)
        verse_form.setHorizontalSpacing(18)
        verse_form.setVerticalSpacing(12)

        self.verse_font_combo = QFontComboBox()
        self.verse_size = QSpinBox()
        self.verse_size.setRange(10, 200)
        self.verse_size.setSuffix(" px")
        self.verse_color_btn = QPushButton("节号颜色")

        verse_form.addRow("节号字体", self.verse_font_combo)
        verse_form.addRow("节号字号", self.verse_size)
        verse_form.addRow("节号颜色", self.verse_color_btn)
        text_tabs.addTab(verse_page, "节号")

        # ---------- 底注 ----------
        footer_page = QWidget()
        footer_form = QFormLayout(footer_page)
        footer_form.setContentsMargins(20, 20, 20, 20)
        footer_form.setHorizontalSpacing(18)
        footer_form.setVerticalSpacing(12)

        self.footer_font_combo = QFontComboBox()
        self.footer_size = QSpinBox()
        self.footer_size.setRange(10, 100)
        self.footer_size.setSuffix(" px")
        self.footer_color_btn = QPushButton("底注颜色")

        footer_form.addRow("底注字体", self.footer_font_combo)
        footer_form.addRow("底注字号", self.footer_size)
        footer_form.addRow("底注颜色", self.footer_color_btn)
        text_tabs.addTab(footer_page, "底注")

        text_root.addWidget(text_tabs)
        tabs.addTab(text_page, "文字设置")

        # =====================================================
        # 布局与底注
        # =====================================================
        layout_page = QWidget()
        lf = QFormLayout(layout_page)
        lf.setContentsMargins(20, 20, 20, 20)
        lf.setHorizontalSpacing(18)
        lf.setVerticalSpacing(14)

        self.line_spacing = QSpinBox()
        self.line_spacing.setRange(100, 300)
        self.line_spacing.setSuffix("%")
        self.margin = QSpinBox()
        self.margin.setRange(0, 300)
        self.margin.setSuffix(" px")
        self.footer_height = QSpinBox()
        self.footer_height.setRange(20, 300)
        self.footer_height.setSuffix(" px")
        self.footer_text = QLineEdit()
        self.footer_text.setPlaceholderText("留空则不显示底注")

        lf.addRow("行距", self.line_spacing)
        lf.addRow("左右边距", self.margin)
        lf.addRow("底注区域高度", self.footer_height)
        lf.addRow("底注文字", self.footer_text)
        tabs.addTab(layout_page, "布局与底注")

        # =====================================================
        # 背景
        # =====================================================
        bg_page = QWidget()
        bg_layout = QFormLayout(bg_page)
        bg_layout.setContentsMargins(20, 20, 20, 20)
        bg_layout.setHorizontalSpacing(18)
        bg_layout.setVerticalSpacing(14)

        self.bg_color_btn = QPushButton("背景颜色")
        self.bg_image = QLineEdit()
        self.bg_image.setReadOnly(True)
        self.bg_image.setPlaceholderText("未选择背景图片")
        bg_choose = QPushButton("选择图片")
        bg_clear = QPushButton("清除")
        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)
        bg_row.addWidget(self.bg_image, 1)
        bg_row.addWidget(bg_choose)
        bg_row.addWidget(bg_clear)

        bg_layout.addRow("背景颜色", self.bg_color_btn)
        bg_layout.addRow("背景图片", bg_row)
        tabs.addTab(bg_page, "背景")

        root.addWidget(tabs, 1)

        # =====================================================
        # 信号
        # =====================================================
        bg_choose.clicked.connect(self._choose_bg)
        bg_clear.clicked.connect(self._clear_bg)

        for key, attr in [
            ("font_color", "font_color_btn"),
            ("title_color", "title_color_btn"),
            ("verse_num_color", "verse_color_btn"),
            ("footer_color", "footer_color_btn"),
            ("bg_color", "bg_color_btn"),
        ]:
            getattr(self, attr).clicked.connect(
                lambda checked=False, k=key: self._choose_color(k)
            )

        # =====================================================
        # 确认 / 取消
        # =====================================================
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("确认")
        buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _set_color_button(self, button, color):
        color = QColor(color)
        button.setText(color.name())
        text = "black" if color.lightness() > 128 else "white"
        button.setStyleSheet(
            f"background:{color.name()};color:{text};padding:8px 12px;"
            f"border-radius:6px;border:1px solid rgba(127,127,127,0.35);font-weight:600;"
        )

    def _choose_color(self, key):
        color = QColorDialog.getColor(
            QColor(self.settings.get(key, "#FFFFFF")), self
        )
        if color.isValid():
            self.settings[key] = color
            mapping = {
                "font_color": "font_color_btn",
                "title_color": "title_color_btn",
                "verse_num_color": "verse_color_btn",
                "footer_color": "footer_color_btn",
                "bg_color": "bg_color_btn",
            }
            self._set_color_button(getattr(self, mapping[key]), color)

    def _choose_bg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.settings["bg_image"] = path
            self.bg_image.setText(path)

    def _clear_bg(self):
        self.settings["bg_image"] = ""
        self.bg_image.clear()

    def _load_settings(self):
        s = self.settings
        self.font_combo.setCurrentFont(
            QFont(s.get("font_family", "微软雅黑"))
        )
        self.font_size.setValue(int(s.get("font_size", 24)))
        self.title_font_combo.setCurrentFont(
            QFont(s.get("title_font_family", "微软雅黑"))
        )
        self.title_size.setValue(int(s.get("title_size", 36)))
        self.verse_font_combo.setCurrentFont(
            QFont(s.get("verse_num_font_family", "微软雅黑"))
        )
        self.verse_size.setValue(int(s.get("verse_num_size", 24)))
        self.footer_font_combo.setCurrentFont(
            QFont(s.get("footer_font_family", "微软雅黑"))
        )
        self.footer_size.setValue(int(s.get("footer_size", 14)))
        self.line_spacing.setValue(int(s.get("line_spacing", 160)))
        self.margin.setValue(int(s.get("margin", 60)))
        self.footer_height.setValue(int(s.get("footer_height", 45)))
        self.footer_text.setText(s.get("footer_text", ""))
        self.bg_image.setText(s.get("bg_image", ""))
        for key, attr in [
            ("font_color", "font_color_btn"),
            ("title_color", "title_color_btn"),
            ("verse_num_color", "verse_color_btn"),
            ("footer_color", "footer_color_btn"),
            ("bg_color", "bg_color_btn"),
        ]:
            self._set_color_button(
                getattr(self, attr), s.get(key, "#FFFFFF")
            )

    def get_settings(self):
        s = dict(self.settings)
        s.update(
            {
                "font_family": self.font_combo.currentFont().family(),
                "font_size": self.font_size.value(),
                "title_font_family": self.title_font_combo.currentFont().family(),
                "title_size": self.title_size.value(),
                "verse_num_font_family": self.verse_font_combo.currentFont().family(),
                "verse_num_size": self.verse_size.value(),
                "footer_font_family": self.footer_font_combo.currentFont().family(),
                "footer_size": self.footer_size.value(),
                "line_spacing": self.line_spacing.value(),
                "margin": self.margin.value(),
                "footer_height": self.footer_height.value(),
                "footer_text": self.footer_text.text(),
                "bg_image": self.bg_image.text(),
            }
        )
        return s


class ToolBarWidget(QToolBar):
    settings_changed = pyqtSignal(dict)
    scroll_speed_changed = pyqtSignal(int)
    extend_toggled = pyqtSignal()
    footer_triggered = pyqtSignal()
    theme_changed = pyqtSignal(str)
    topmost_toggled = pyqtSignal(bool)
    scroll_up = pyqtSignal()
    scroll_down = pyqtSignal()
    clear_requested = pyqtSignal()

    SPEED_LABELS = ["暂停"] + [f"{i}档" for i in range(1, 10)]

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        self.setFloatable(False)
        self.theme = "dark"
        self.settings = {}
        self._speed = 0

        self.extend_btn = QPushButton("扩展显示  F12")
        self.extend_btn.setObjectName("extendBtn")
        self.extend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.extend_btn.clicked.connect(self.extend_toggled)
        self.addWidget(self.extend_btn)

        self.topmost_btn = QPushButton("置顶")
        self.topmost_btn.setObjectName("topmostBtn")
        self.topmost_btn.setCheckable(True)
        self.topmost_btn.setChecked(True)
        self.topmost_btn.setEnabled(False)
        self.topmost_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.topmost_btn.setToolTip("扩展窗口始终置顶")
        self.topmost_btn.toggled.connect(self.topmost_toggled)
        self.addWidget(self.topmost_btn)

        self.clear_btn = QPushButton("清屏")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("清空预览与扩展屏经文")
        self.clear_btn.clicked.connect(self.clear_requested)
        self.addWidget(self.clear_btn)

        self.addSeparator()

        scroll_wrap = QWidget()
        scroll_layout = QHBoxLayout(scroll_wrap)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)
        scroll_layout.addWidget(QLabel("滚动"))
        up = QPushButton("↑")
        up.setMinimumWidth(36)
        up.setCursor(Qt.CursorShape.PointingHandCursor)
        up.setToolTip("向上滚动")
        up.clicked.connect(self.scroll_up)
        scroll_layout.addWidget(up)
        up.hide()
        down = QPushButton("↓")
        down.setMinimumWidth(36)
        down.setCursor(Qt.CursorShape.PointingHandCursor)
        down.setToolTip("向下滚动")
        down.clicked.connect(self.scroll_down)
        scroll_layout.addWidget(down)
        down.hide()
        scroll_layout.addSpacing(4)
        scroll_layout.addWidget(QLabel("速度"))

        self.speed_buttons = []
        for speed, text in [(0, "暂停")] + [(i, f"{i}档") for i in range(1, 10)]:
            btn = QPushButton(text)
            btn.setObjectName("speedBtn")
            btn.setCheckable(True)
            btn.setAutoExclusive(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.setToolTip("暂停自动滚动" if speed == 0 else f"自动滚动 {speed} 档")
            btn.setProperty("speedValue", speed)
            btn.clicked.connect(lambda checked=False, s=speed: self._set_speed(s))
            self.speed_buttons.append(btn)
            scroll_layout.addWidget(btn)
        self.addWidget(scroll_wrap)
        self._set_speed(0)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.addSeparator()

        self.settings_btn = QPushButton("显示设置")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self._open_settings)
        self.addWidget(self.settings_btn)

        self.theme_btn = QPushButton("亮色")
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("切换亮色 / 暗色主题")
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.addWidget(self.theme_btn)

    def load_settings(self, settings):
        self.settings = dict(settings)
        self.theme = settings.get("theme", "dark")
        blocked = self.topmost_btn.blockSignals(True)
        self.topmost_btn.setChecked(settings.get("extension_topmost", True))
        self.topmost_btn.blockSignals(blocked)
        self._update_theme_button()

    def _open_settings(self):
        dialog = DisplaySettingsDialog(self.settings, self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.get_settings()
            self.settings_changed.emit(self.settings)

    def _set_speed(self, speed):
        speed = max(0, min(9, int(speed)))
        self._speed = speed
        for i, btn in enumerate(self.speed_buttons):
            btn.setChecked(i == speed)
        self.scroll_speed_changed.emit(speed)

    def current_speed(self):
        return self._speed

    def _toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self._update_theme_button()
        self.theme_changed.emit(self.theme)

    def _update_theme_button(self):
        self.theme_btn.setText("暗色" if self.theme == "light" else "亮色")

    def set_extend_active(self, active):
        if active:
            self.extend_btn.setText("关闭扩展  Esc")
            self.topmost_btn.setEnabled(True)
        else:
            self.extend_btn.setText("扩展显示  F12")
            self.topmost_btn.setEnabled(False)

# ui/toolbar.py
# 顶部工具栏：分组布局 + 速度下拉（冷蓝控制台）

from PyQt6.QtWidgets import (
    QToolBar, QPushButton, QLabel, QDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QVBoxLayout, QSpinBox, QFontComboBox, QColorDialog,
    QFileDialog, QLineEdit, QDialogButtonBox, QWidget, QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class DisplaySettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("显示设置")
        self.setMinimumWidth(560)
        self.settings = dict(settings)
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        # 根据当前屏幕自动限制对话框高度
        screen = self.screen() or self.parentWidget().screen()
        if screen:
            available = screen.availableGeometry()
            self.setMaximumHeight(int(available.height() * 0.9))

        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)
        text_group = QGroupBox("文字设置")
        form = QFormLayout(text_group)
        form.setSpacing(8)
        self.font_combo = QFontComboBox()
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 300)
        self.font_size.setSuffix(" px")
        self.font_color_btn = QPushButton("正文颜色")
        self.title_font_combo = QFontComboBox()
        self.title_size = QSpinBox()
        self.title_size.setRange(12, 300)
        self.title_size.setSuffix(" px")
        self.title_color_btn = QPushButton("标题颜色")
        self.verse_font_combo = QFontComboBox()
        self.verse_size = QSpinBox()
        self.verse_size.setRange(10, 200)
        self.verse_size.setSuffix(" px")
        self.verse_color_btn = QPushButton("节号颜色")
        self.footer_font_combo = QFontComboBox()
        self.footer_size = QSpinBox()
        self.footer_size.setRange(10, 100)
        self.footer_size.setSuffix(" px")
        self.footer_color_btn = QPushButton("底注颜色")
        for label, w in [
            ("正文字体", self.font_combo),
            ("正文字号", self.font_size),
            ("正文字色", self.font_color_btn),
            ("标题字体", self.title_font_combo),
            ("标题字号", self.title_size),
            ("标题颜色", self.title_color_btn),
            ("节号字体", self.verse_font_combo),
            ("节号字号", self.verse_size),
            ("节号颜色", self.verse_color_btn),
            ("底注字体", self.footer_font_combo),
            ("底注字号", self.footer_size),
            ("底注颜色", self.footer_color_btn),
        ]:
            form.addRow(label, w)


        layout_group = QGroupBox("布局与底注")
        lf = QFormLayout(layout_group)
        lf.setSpacing(8)
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
        for label, w in [
            ("行距", self.line_spacing),
            ("左右边距", self.margin),
            ("底注区域高度", self.footer_height),
            ("底注文字", self.footer_text),
        ]:
            lf.addRow(label, w)


        bg_group = QGroupBox("背景")
        bg_layout = QFormLayout(bg_group)
        bg_layout.setSpacing(8)
        self.bg_color_btn = QPushButton("背景颜色")
        self.bg_image = QLineEdit()
        self.bg_image.setReadOnly(True)
        bg_choose = QPushButton("选择图片")
        bg_clear = QPushButton("清除")
        bg_row = QHBoxLayout()
        bg_row.setSpacing(6)
        bg_row.addWidget(self.bg_image, 1)
        bg_row.addWidget(bg_choose)
        bg_row.addWidget(bg_clear)
        bg_layout.addRow("背景颜色", self.bg_color_btn)
        bg_layout.addRow("背景图片", bg_row)

        # =========================
        # 中间设置内容：自适应滚动区域
        # =========================
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(text_group)
        content_layout.addWidget(layout_group)
        content_layout.addWidget(bg_group)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(content)

        root.addWidget(scroll, 1)

        
        bg_choose.clicked.connect(self._choose_bg)
        bg_clear.clicked.connect(self._clear_bg)
        for key, attr in [
            ("font_color", "font_color_btn"),
            ("title_color", "title_color_btn"),
            ("verse_num_color", "verse_color_btn"),
            ("footer_color", "footer_color_btn"),
            ("bg_color", "bg_color_btn"),
        ]:
            getattr(self, attr).clicked.connect(lambda checked=False, k=key: self._choose_color(k))

        # 确认 / 取消按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        # 修改按钮文字
        buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).setText("确认")

        buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("取消")

        # 确认：保存设置
        buttons.accepted.connect(self.accept)

        # 取消：关闭窗口，不保存本次修改
        buttons.rejected.connect(self.reject)

        root.addWidget(buttons)

    def _set_color_button(self, button, color):
        color = QColor(color)
        button.setText(color.name())
        text = "black" if color.lightness() > 128 else "white"
        button.setStyleSheet(
            f"background:{color.name()};color:{text};padding:6px 12px;border-radius:6px;border:1px solid rgba(0,0,0,0.15);"
        )

    def _choose_color(self, key):
        color = QColorDialog.getColor(QColor(self.settings.get(key, "#FFFFFF")), self)
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
            self, "选择背景图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.settings["bg_image"] = path
            self.bg_image.setText(path)

    def _clear_bg(self):
        self.settings["bg_image"] = ""
        self.bg_image.clear()

    def _load_settings(self):
        s = self.settings
        self.font_combo.setCurrentFont(QFont(s.get("font_family", "微软雅黑")))
        self.font_size.setValue(int(s.get("font_size", 24)))
        self.title_font_combo.setCurrentFont(QFont(s.get("title_font_family", "微软雅黑")))
        self.title_size.setValue(int(s.get("title_size", 36)))
        self.verse_font_combo.setCurrentFont(QFont(s.get("verse_num_font_family", "微软雅黑")))
        self.verse_size.setValue(int(s.get("verse_num_size", 24)))
        self.footer_font_combo.setCurrentFont(QFont(s.get("footer_font_family", "微软雅黑")))
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
            self._set_color_button(getattr(self, attr), s.get(key, "#FFFFFF"))

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

    SPEED_LABELS = ["暂停"] + [f"{i}档" for i in range(1, 10)]

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        self.setFloatable(False)
        self.theme = "dark"
        self.settings = {}
        self._speed = 0

        # —— 投影 ——
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

        self.addSeparator()

        # —— 滚动 ——
        scroll_wrap = QWidget()
        scroll_layout = QHBoxLayout(scroll_wrap)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)
        scroll_layout.addWidget(QLabel("滚动"))
        up = QPushButton("↑")
        up.setMinimumWidth(36)
        up.setToolTip("向上滚动")
        up.clicked.connect(self.scroll_up)
        scroll_layout.addWidget(up)
        down = QPushButton("↓")
        down.setMinimumWidth(36)
        down.setToolTip("向下滚动")
        down.clicked.connect(self.scroll_down)
        scroll_layout.addWidget(down)
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

        # —— 设置 ——
        self.settings_btn = QPushButton("显示设置")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.clicked.connect(self._open_settings)
        self.addWidget(self.settings_btn)

        self.theme_btn = QPushButton("亮色")
        self.theme_btn.setObjectName("themeBtn")
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
        """供主窗口快捷键 / 滚到底同步调用。"""
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

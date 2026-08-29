# ui/toolbar.py
# 顶部工具栏
# 功能：扩展显示、滚动控制、字体颜色、布局、背景、底注、主题切换
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel, QSlider, QSpinBox, QFontComboBox, QColorDialog, QFileDialog
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class ToolBarWidget(QToolBar):
    # 信号
    settings_changed = pyqtSignal(dict)       # 设置变化
    scroll_speed_changed = pyqtSignal(int)    # 滚动速度变化
    extend_toggled = pyqtSignal()             # 扩展显示切换
    footer_triggered = pyqtSignal()          # 底注设置触发
    theme_changed = pyqtSignal(str)          # 主题切换
    topmost_toggled = pyqtSignal(bool)       # 置顶切换
    scroll_up = pyqtSignal()                 # 手动上滚
    scroll_down = pyqtSignal()               # 手动下滚

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        # 初始化主题变量（修复原代码缺失导致报错）
        self.theme = "dark"

        # 按功能分区创建按钮
        self._create_extend_section()    # 扩展显示区
        self.addSeparator()
        self._create_scroll_section()    # 滚动控制区
        self.addSeparator()
        self._create_font_section()      # 字体设置区
        self.addSeparator()
        self._create_color_section()     # 颜色设置区
        self.addSeparator()
        self._create_layout_section()    # 布局设置区
        self.addSeparator()
        self._create_bg_section()        # 背景设置区
        self.addSeparator()
        self._create_footer_section()    # 底注设置区
        self.addSeparator()
        self._create_theme_section()     # 主题切换区

    def load_settings(self, settings):
        """加载配置到工具栏控件"""
        # 正文字体
        self.font_combo.setCurrentFont(QFont(settings.get("font_family", "微软雅黑")))
        self.font_size_spin.setValue(settings.get("font_size", 24))
        # 标题字体+字号
        self.title_font_combo.setCurrentFont(QFont(settings.get("title_font_family", "微软雅黑")))
        self.title_size_spin.setValue(settings.get("title_size", 36))
        # 节号字体+字号
        self.verse_font_combo.setCurrentFont(QFont(settings.get("verse_num_font_family", "微软雅黑")))
        self.verse_num_size_spin.setValue(settings.get("verse_num_size", 24))

        self.footer_font_family = settings.get("footer_font_family", "微软雅黑")
        # 颜色
        self.font_color = settings.get("font_color", QColor("#FFFFFF"))
        self.verse_color = settings.get("verse_num_color", QColor("#FFD700"))
        self.title_color = settings.get("title_color", QColor("#87CEEB"))
        self.bg_color = settings.get("bg_color", QColor("#000000"))
        self.footer_color = settings.get("footer_color", QColor("#AAAAAA"))
        self._update_color_btn(self.font_color_btn, self.font_color)
        self._update_color_btn(self.verse_color_btn, self.verse_color)
        self._update_color_btn(self.title_color_btn, self.title_color)
        self._update_color_btn(self.bg_color_btn, self.bg_color)
        self._update_color_btn(self.footer_color_btn, self.footer_color)
        # 布局
        self.line_spacing_spin.setValue(settings.get("line_spacing", 160))
        self.margin_spin.setValue(settings.get("margin", 60))
        self.footer_height_spin.setValue(settings.get("footer_height", 45))
        self.footer_size_spin.setValue(settings.get("footer_size", 14))
        # 背景图
        self.bg_image_path = settings.get("bg_image", "")
        # 置顶状态
        self.topmost_btn.setChecked(settings.get("extension_topmost", True))

    # ============== 扩展显示区 ==============
    def _create_extend_section(self):
        # 扩展显示按钮
        self.extend_btn = QPushButton("扩展显示 (F12)")
        self.extend_btn.setObjectName("extendBtn")
        self.extend_btn.clicked.connect(self.extend_toggled)
        self.addWidget(self.extend_btn)
        # 置顶切换按钮
        self.topmost_btn = QPushButton("🔝 置顶")
        self.topmost_btn.setObjectName("topmostBtn")
        self.topmost_btn.setCheckable(True)
        self.topmost_btn.setChecked(True)
        self.topmost_btn.setEnabled(False)  # 没开扩展时禁用
        self.topmost_btn.toggled.connect(self.topmost_toggled)
        self.addWidget(self.topmost_btn)

    # ============== 滚动控制区 ==============
    def _create_scroll_section(self):
        self.addWidget(QLabel(" 滚动:"))
        up_btn = QPushButton("↑")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(self.scroll_up)
        self.addWidget(up_btn)
        down_btn = QPushButton("↓")
        down_btn.setFixedWidth(30)
        down_btn.clicked.connect(self.scroll_down)
        self.addWidget(down_btn)
        self.addWidget(QLabel(" 速度:"))
        self.scroll_slider = QSlider(Qt.Orientation.Horizontal)
        self.scroll_slider.setRange(0, 6)
        self.scroll_slider.setValue(0)
        self.scroll_slider.setFixedWidth(100)
        self.scroll_slider.valueChanged.connect(self._on_scroll_changed)
        self.addWidget(self.scroll_slider)
        self.speed_label = QLabel("暂停")
        self.speed_label.setFixedWidth(35)
        self.addWidget(self.speed_label)

    def _on_scroll_changed(self, speed):
        """滚动速度变化，更新标签并发信号"""
        speed_names = ["暂停", "1档", "2档", "3档", "4档", "5档", "6档"]
        self.speed_label.setText(speed_names[speed])
        self.scroll_speed_changed.emit(speed)

    # ============== 字体设置区【重点新增标题字号、节号字号控件】 ==============
    def _create_font_section(self):
        self.addWidget(QLabel(" 正文字体:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setFixedWidth(120)
        self.font_combo.currentFontChanged.connect(self._emit_settings)
        self.addWidget(self.font_combo)

        self.addWidget(QLabel(" 正文字号:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 160)
        self.font_size_spin.setValue(24)
        self.font_size_spin.setFixedWidth(55)
        self.font_size_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.font_size_spin)

        self.addWidget(QLabel(" 标题字体:"))
        self.title_font_combo = QFontComboBox()
        self.title_font_combo.setFixedWidth(120)
        self.title_font_combo.currentFontChanged.connect(self._emit_settings)
        self.addWidget(self.title_font_combo)

        self.addWidget(QLabel(" 标题字号:"))
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(12, 160)
        self.title_size_spin.setValue(36)
        self.title_size_spin.setFixedWidth(55)
        self.title_size_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.title_size_spin)

        self.addWidget(QLabel(" 节号字体:"))
        self.verse_font_combo = QFontComboBox()
        self.verse_font_combo.setFixedWidth(120)
        self.verse_font_combo.currentFontChanged.connect(self._emit_settings)
        self.addWidget(self.verse_font_combo)

        self.addWidget(QLabel(" 节号字号:"))
        self.verse_num_size_spin = QSpinBox()
        self.verse_num_size_spin.setRange(12, 160)
        self.verse_num_size_spin.setValue(24)
        self.verse_num_size_spin.setFixedWidth(55)
        self.verse_num_size_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.verse_num_size_spin)

    # ============== 颜色设置区 ==============
    def _create_color_section(self):
        # 正文字色
        self.font_color_btn = QPushButton("字色")
        self.font_color_btn.setProperty("class", "colorBtn")
        self.font_color = QColor("#FFFFFF")
        self._update_color_btn(self.font_color_btn, self.font_color)
        self.font_color_btn.clicked.connect(lambda: self._choose_color("font"))
        self.addWidget(self.font_color_btn)

        # 节号颜色
        self.verse_color_btn = QPushButton("节号")
        self.verse_color = QColor("#FFD700")
        self._update_color_btn(self.verse_color_btn, self.verse_color)
        self.verse_color_btn.clicked.connect(lambda: self._choose_color("verse"))
        self.addWidget(self.verse_color_btn)

        # 标题颜色
        self.title_color_btn = QPushButton("标题")
        self.title_color = QColor("#87CEEB")
        self._update_color_btn(self.title_color_btn, self.title_color)
        self.title_color_btn.clicked.connect(lambda: self._choose_color("title"))
        self.addWidget(self.title_color_btn)

    def _update_color_btn(self, btn, color):
        """更新颜色按钮的背景色"""
        text_color = "black" if color.lightness() > 128 else "white"
        btn.setStyleSheet(f"""
            background: {color.name()}; color: {text_color};
            border: none; padding: 4px 10px;
            border-radius: 4px; font-size: 11px; min-width: 35px;
        """)

    def _choose_color(self, color_type):
        """打开颜色选择器"""
        color = QColorDialog.getColor()
        if color.isValid():
            if color_type == "font":
                self.font_color = color
                self._update_color_btn(self.font_color_btn, color)
            elif color_type == "verse":
                self.verse_color = color
                self._update_color_btn(self.verse_color_btn, color)
            elif color_type == "title":
                self.title_color = color
                self._update_color_btn(self.title_color_btn, color)
            elif color_type == "bg":
                self.bg_color = color
                self._update_color_btn(self.bg_color_btn, color)
            elif color_type == "footer":
                self.footer_color = color
                self._update_color_btn(self.footer_color_btn, color)
            self._emit_settings()

    # ============== 布局设置区 ==============
    def _create_layout_section(self):
        self.addWidget(QLabel(" 行距:"))
        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(100, 300)
        self.line_spacing_spin.setValue(160)
        self.line_spacing_spin.setFixedWidth(55)
        self.line_spacing_spin.setSuffix("%")
        self.line_spacing_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.line_spacing_spin)

        self.addWidget(QLabel(" 边距:"))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(10, 200)
        self.margin_spin.setValue(60)
        self.margin_spin.setFixedWidth(55)
        self.margin_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.margin_spin)

    # ============== 背景设置区 ==============
    def _create_bg_section(self):
        # 背景色
        self.bg_color_btn = QPushButton("背景色")
        self.bg_color = QColor("#000000")
        self._update_color_btn(self.bg_color_btn, self.bg_color)
        self.bg_color_btn.clicked.connect(lambda: self._choose_color("bg"))
        self.addWidget(self.bg_color_btn)
        # 背景图
        self.bg_image_btn = QPushButton("背景图")
        self.bg_image_btn.clicked.connect(self._choose_bg_image)
        self.addWidget(self.bg_image_btn)

    def _choose_bg_image(self):
        """选择背景图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.bg_image_path = file_path
            self._emit_settings()

    # ============== 底注设置区 ==============
    def _create_footer_section(self):
        # 底注文字按钮
        footer_btn = QPushButton("底注文字")
        footer_btn.clicked.connect(self.footer_triggered)
        self.addWidget(footer_btn)
        self.addWidget(QLabel(" 高:"))
        self.footer_height_spin = QSpinBox()
        self.footer_height_spin.setRange(20, 100)
        self.footer_height_spin.setValue(45)
        self.footer_height_spin.setFixedWidth(45)
        self.footer_height_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.footer_height_spin)
        self.addWidget(QLabel(" 号:"))
        self.footer_size_spin = QSpinBox()
        self.footer_size_spin.setRange(10, 30)
        self.footer_size_spin.setValue(14)
        self.footer_size_spin.setFixedWidth(45)
        self.footer_size_spin.valueChanged.connect(self._emit_settings)
        self.addWidget(self.footer_size_spin)
        # 底注颜色
        self.footer_color_btn = QPushButton("底色")
        self.footer_color = QColor("#AAAAAA")
        self._update_color_btn(self.footer_color_btn, self.footer_color)
        self.footer_color_btn.clicked.connect(lambda: self._choose_color("footer"))
        self.addWidget(self.footer_color_btn)

    # ============== 主题切换区 ==============
    def _create_theme_section(self):
        self.theme_btn = QPushButton("☀ 亮色")
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.addWidget(self.theme_btn)

    def _toggle_theme(self):
        """切换亮/暗主题"""
        if self.theme == "dark":
            self.theme = "light"
            self.theme_btn.setText("🌙 暗色")
        else:
            self.theme = "dark"
            self.theme_btn.setText("☀ 亮色")
        self.theme_changed.emit(self.theme)

    # ============== 发出设置信号【重点：输出标题字号、节号字号】 ==============
    def _emit_settings(self):
        """收集所有设置，发出变化信号"""
        settings = {
            "font_family": self.font_combo.currentFont().family(),
            "font_size": self.font_size_spin.value(),
            "font_color": self.font_color,
            "verse_num_color": self.verse_color,
            "verse_num_size": self.verse_num_size_spin.value(),
            "verse_num_font_family": self.verse_font_combo.currentFont().family(),
            "title_color": self.title_color,
            "title_size": self.title_size_spin.value(),
            "title_font_family": self.title_font_combo.currentFont().family(),
            "bg_color": self.bg_color,
            "bg_image": getattr(self, "bg_image_path", ""),
            "line_spacing": self.line_spacing_spin.value(),
            "margin": self.margin_spin.value(),
            "footer_height": self.footer_height_spin.value(),
            "footer_size": self.footer_size_spin.value(),
            "footer_color": self.footer_color,
            "footer_font_family": getattr(self, "footer_font_family", "微软雅黑"),
            "extension_topmost": self.topmost_btn.isChecked()
        }
        self.settings_changed.emit(settings)

    # ============== 扩展按钮状态 ==============
    def set_extend_active(self, active):
        """设置扩展按钮状态，同步启用/禁用置顶按钮"""
        if active:
            self.extend_btn.setText("关闭扩展 (F12)")
            self.topmost_btn.setEnabled(True)
        else:
            self.extend_btn.setText("扩展显示 (F12)")
            self.topmost_btn.setEnabled(False)

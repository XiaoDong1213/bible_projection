# ui/scripture_display.py
# 经文显示核心控件
# 功能：顶部固定标题栏（自适应字号）、经文滚动、背景全覆盖、底注显示、平滑滚动
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QFrame
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPixmap, QFontMetrics, QPainter


class ScriptureDisplay(QWidget):
    # 新增信号：手动滚动，用来同步扩展屏
    scroll_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ===== 正文字体样式 =====
        self.font_family = "微软雅黑"
        self.font_size = 24
        self.font_color = QColor("#FFFFFF")

        # ===== 背景 =====
        self.bg_color = QColor("#000000")
        self.bg_image = None

        # ===== 布局 =====
        self.line_spacing = 160  # 行距百分比
        self.margin_left = 60  # 左边距
        self.margin_right = 60  # 右边距

        # ===== 标题样式【新增独立标题字体】 =====
        self.title_font_family = "微软雅黑"
        self.title_color = QColor("#87CEEB")
        self.title_size = 20
        self.title_min_size = 12  # 标题最小字号，防止缩太小

        # ===== 节号样式【新增独立节号字体】 =====
        self.verse_num_color = QColor("#FFD700")
        self.verse_num_size = 16
        self.verse_num_font_family = "微软雅黑"

        # ===== 底注样式 =====
        self.footer_text = ""
        self.footer_height = 45
        self.footer_size = 14
        self.footer_color = QColor("#AAAAAA")
        self.footer_font_family = "微软雅黑"

        # ===== 滚动控制 =====
        self.scroll_speed = 0  # 0-6档，0暂停
        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self._auto_scroll)
        self.scroll_timer.setInterval(50)  # 20fps滚动

        self.verses = []  # 当前显示的经文列表 [(节号, 内容), ...]
        self._init_ui()

    def _init_ui(self):
        """初始化界面布局"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部固定标题栏（透明背景，显示在背景图之上）
        self.title_bar = QLabel("")
        self.title_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_bar.setFixedHeight(42)
        self.title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout.addWidget(self.title_bar)

        # 经文显示区域（只读，无滚动条）
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_display.setFrameShape(QFrame.Shape.NoFrame)
        self.text_display.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 【关键】强制文档底色透明，解决QTextEdit遮挡背景图
        doc = self.text_display.document()
        doc.setDefaultStyleSheet("body {background: transparent;}")
        # 安装事件过滤器捕获滚轮
        self.text_display.viewport().installEventFilter(self)
        layout.addWidget(self.text_display, 1)

        self.setLayout(layout)

    # ============== 设置经文 ==============
    def set_scripture(self, book_name, chapter, start_verse, end_verse, verses):
        """
        设置并显示经文
        :param book_name: 书卷名
        :param chapter: 章节
        :param start_verse: 起始节
        :param end_verse: 结束节
        :param verses: 经文列表 [(节号, 内容), ...]
        """
        self.verses = verses

        # 格式化标题文本
        if start_verse is None:
            title_text = f"{book_name} 第 {chapter} 章"
        elif end_verse is None:
            title_text = f"{book_name} 第 {chapter} 章第 {start_verse}-末 节"
        elif start_verse == end_verse:
            title_text = f"{book_name} 第 {chapter} 章第 {start_verse} 节"
        else:
            title_text = f"{book_name} 第 {chapter} 章第 {start_verse}-{end_verse} 节"

        # 设置自适应标题
        self._set_adaptive_title(title_text)
        # 渲染经文内容
        self._render_scripture()
        # 滚动到顶部
        self.text_display.verticalScrollBar().setValue(0)

    def _set_adaptive_title(self, text):
        """
        标题自适应字号
        逻辑：文字太宽就自动缩小字号，始终保持单行
        """
        available_width = self.title_bar.width() - 40  # 左右各留20px边距
        font_size = self.title_size

        font = QFont(self.title_font_family, font_size)
        font.setBold(True)
        fm = QFontMetrics(font)

        # 文字宽度超过可用宽度时，逐号缩小
        while fm.horizontalAdvance(text) > available_width and font_size > self.title_min_size:
            font_size -= 1
            font = QFont(self.title_font_family, font_size)
            font.setBold(True)
            fm = QFontMetrics(font)

        self.title_bar.setFont(font)
        self.title_bar.setStyleSheet(f"""
            color: {self.title_color.name()};
            font-size: {font_size}px;
            font-family: "{self.title_font_family}";
            font-weight: bold;
            background: transparent;
        """)
        self.title_bar.setText(text)

    def clear(self):
        """清空显示"""
        self.title_bar.setText("")
        self.text_display.clear()
        self.verses = []

    def _render_scripture(self):
        """用HTML渲染经文内容，支持富文本样式，统一行距"""
        # 开头容器，设置内边距和行距，清除p默认margin
        html = f"""
        <div style='padding: 10px {self.margin_left}px 10px {self.margin_right}px;
                     line-height: {self.line_spacing}%;'>
        """

        # 逐节渲染
        for verse_num, verse_text in self.verses:
            html += f"""
            <p style='margin: 0 0 8px 0; padding:0; text-align: justify;'>
                <!-- 节号 -->
                <span style='color: {self.verse_num_color.name()};
                             font-size: {self.verse_num_size}px;
                             font-family: "{self.verse_num_font_family}";
                             font-weight: bold; margin-right: 6px;
                             vertical-align: super;'>
                    {verse_num}
                </span>
                <!-- 经文内容 -->
                <span style='color: {self.font_color.name()};
                             font-size: {self.font_size}px;
                             font-family: "{self.font_family}";'>
                    {verse_text}
                </span>
            </p>
            """

        html += "</div>"
        # 底部预留底注高度占位
        html += f"<div style='height: {self.footer_height}px;'></div>"

        self.text_display.setHtml(html)

    # ============== 背景绘制【已修复：全覆盖标题+经文+底注】 ==============
    def paintEvent(self, event):
        """
        重绘背景，覆盖整个控件区域
        包括：标题栏、经文区、底注区
        """
        painter = QPainter(self)

        # 1. 绘制背景色
        painter.fillRect(self.rect(), self.bg_color)

        # 2. 绘制背景图片（居中裁剪填充）
        if self.bg_image and os.path.exists(self.bg_image):
            pixmap = QPixmap(self.bg_image)
            # 按比例放大到填满控件
            scaled = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # 居中显示
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        # 3. 绘制底注文字（有文字才画）
        if self.footer_text.strip():
            footer_rect = QRect(
                0, self.height() - self.footer_height,
                self.width(), self.footer_height
            )
            painter.setPen(self.footer_color)
            font = QFont(self.footer_font_family, self.footer_size)
            painter.setFont(font)
            painter.drawText(
                footer_rect,
                Qt.AlignmentFlag.AlignCenter,
                self.footer_text
            )
        super().paintEvent(event)

    # ============== 滚动控制 ==============
    def set_scroll_speed(self, speed):
        """设置滚动速度 0-6档，0为暂停"""
        self.scroll_speed = speed
        if speed == 0:
            self.scroll_timer.stop()
        else:
            self.scroll_timer.start()

    def _auto_scroll(self):
        """自动滚动定时器回调"""
        scrollbar = self.text_display.verticalScrollBar()
        if scrollbar.value() < scrollbar.maximum():
            scrollbar.setValue(scrollbar.value() + self.scroll_speed)
            self.scroll_changed.emit(self.scroll_speed)
        else:
            # 滚到底停止
            self.scroll_timer.stop()

    def scroll_by(self, delta):
        """手动滚动指定像素"""
        scrollbar = self.text_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + delta)
        # 发出信号同步扩展屏
        self.scroll_changed.emit(delta)

    def eventFilter(self, obj, event):
        """事件过滤器，捕获经文区的滚轮事件"""
        if obj == self.text_display.viewport():
            if event.type() == event.Type.Wheel:
                if self.scroll_speed == 0:
                    # 暂停状态下，滚轮手动滚动
                    delta = -event.angleDelta().y() // 8
                    self.scroll_by(delta)
                return True
        return super().eventFilter(obj, event)

    # ============== 批量应用设置【新增标题/节号字体配置】 ==============
    def apply_settings(self, settings):
        """批量应用显示设置"""
        self.font_family = settings.get("font_family", self.font_family)
        self.font_size = settings.get("font_size", self.font_size)
        self.font_color = settings.get("font_color", self.font_color)

        self.verse_num_color = settings.get("verse_num_color", self.verse_num_color)
        self.verse_num_size = settings.get("verse_num_size", self.verse_num_size)
        self.verse_num_font_family = settings.get("verse_num_font_family", self.verse_num_font_family)

        self.title_color = settings.get("title_color", self.title_color)
        self.title_size = settings.get("title_size", self.title_size)
        self.title_font_family = settings.get("title_font_family", self.title_font_family)

        self.bg_color = settings.get("bg_color", self.bg_color)
        self.bg_image = settings.get("bg_image", self.bg_image) or None
        self.line_spacing = settings.get("line_spacing", self.line_spacing)

        margin = settings.get("margin", None)
        if margin is not None:
            self.margin_left = margin
            self.margin_right = margin

        self.footer_height = settings.get("footer_height", self.footer_height)
        self.footer_size = settings.get("footer_size", self.footer_size)
        self.footer_color = settings.get("footer_color", self.footer_color)
        self.footer_text = settings.get("footer_text", self.footer_text)
        self.footer_font_family = settings.get("footer_font_family", self.footer_font_family)

        # 有经文就重新渲染
        if self.verses:
            self._set_adaptive_title(self.title_bar.text())
            self._render_scripture()
        # 【关键】底注、背景修改强制重绘
        self.update()

    def resizeEvent(self, event):
        """窗口大小变化时，重新计算标题字号"""
        super().resizeEvent(event)
        if self.title_bar.text():
            self._set_adaptive_title(self.title_bar.text())

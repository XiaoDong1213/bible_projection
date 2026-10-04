"""右侧属性：背景页 + 元素属性页（无勾选框，用切换按钮）。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import Background, Element, Slide
from ui.sermon.styles import SermonComboBox

_TYPE_LABELS = {
    "text": "文本",
    "image": "图片",
    "shape": "形状",
}


def _section(title: str) -> QLabel:
    lab = QLabel(title)
    lab.setObjectName("sermonSectionLabel")
    return lab


def _toggle(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("sermonToggleBtn")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(30)
    return btn


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName("sermonPropertyScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(scroll.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    return scroll


class BackgroundPanel(QWidget):
    """幻灯片背景（独立 Tab）。"""

    background_changed = pyqtSignal()
    pick_bg_image = pyqtSignal()
    clear_bg_image = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonBackgroundPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(_section("幻灯片背景"))
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.bg_color_btn = QPushButton("颜色")
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        form.addRow("纯色", self.bg_color_btn)

        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        self.bg_image_btn = QPushButton("选图…")
        self.bg_image_btn.clicked.connect(self.pick_bg_image.emit)
        self.bg_clear_btn = QPushButton("清除")
        self.bg_clear_btn.clicked.connect(self.clear_bg_image.emit)
        img_row.addWidget(self.bg_image_btn, 1)
        img_row.addWidget(self.bg_clear_btn)
        form.addRow("图片", img_row)

        self.bg_fit = SermonComboBox()
        self.bg_fit.setMaxVisibleItems(8)
        self.bg_fit.addItem("铺满", "cover")
        self.bg_fit.addItem("完整", "contain")
        self.bg_fit.currentIndexChanged.connect(self._on_bg_fit)
        form.addRow("适应", self.bg_fit)
        layout.addLayout(form)

        hint = QLabel("背景作用于当前页。选图后可用「适应」控制铺满或完整显示。")
        hint.setWordWrap(True)
        hint.setObjectName("sermonHint")
        layout.addWidget(hint)
        layout.addStretch(1)

        outer.addWidget(_scroll_wrap(body))

        self._slide: Slide | None = None
        self._block = False
        self._bg_color = "#1A1A2E"
        self._update_color_btn(self.bg_color_btn, self._bg_color)

    def set_slide(self, slide: Slide | None):
        self._slide = slide
        self._block = True
        if slide is not None:
            bg = slide.background
            self._bg_color = bg.value if bg.type == "color" else self._bg_color
            self._update_color_btn(self.bg_color_btn, self._bg_color)
            fit = bg.fit or "cover"
            idx = self.bg_fit.findData(fit)
            if idx >= 0:
                self.bg_fit.setCurrentIndex(idx)
        self._block = False

    def _update_color_btn(self, btn: QPushButton, color: str):
        c = QColor(color)
        if not c.isValid():
            c = QColor("#FFFFFF")
        fg = "#0F172A" if c.lightness() > 140 else "#FFFFFF"
        btn.setStyleSheet(
            "QPushButton {"
            f" background: {c.name()}; color: {fg};"
            " border: 1px solid rgba(0,0,0,40);"
            " border-radius: 6px; min-height: 30px;"
            "}"
        )
        btn.setText(c.name().upper())

    def _pick_bg_color(self):
        if self._slide is None:
            return
        color = QColorDialog.getColor(QColor(self._bg_color), self, "背景颜色")
        if not color.isValid():
            return
        self._bg_color = color.name().upper()
        self._update_color_btn(self.bg_color_btn, self._bg_color)
        self._slide.background = Background(
            type="color", value=self._bg_color, fit=self._slide.background.fit
        )
        self.background_changed.emit()

    def _on_bg_fit(self):
        if self._block or self._slide is None:
            return
        fit = self.bg_fit.currentData()
        self._slide.background.fit = str(fit or "cover")
        self.background_changed.emit()


class PropertyPanel(QWidget):
    """选中元素属性（文本 / 形状 / 位置 / 图层）。"""

    element_changed = pyqtSignal(object)
    layer_reorder = pyqtSignal(str)
    align_requested = pyqtSignal(str)
    distribute_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonPropertyPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # —— 文本 ——
        self.text_section = QWidget()
        text_col = QVBoxLayout(self.text_section)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(8)
        text_col.addWidget(_section("文本"))
        text_form = QFormLayout()
        text_form.setContentsMargins(0, 0, 0, 0)
        text_form.setHorizontalSpacing(12)
        text_form.setVerticalSpacing(10)
        text_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.font_family = SermonComboBox(searchable=True)
        self._populate_fonts()
        self.font_family.currentTextChanged.connect(self._emit_element)
        text_form.addRow("字体", self.font_family)

        self.font_size = QSpinBox()
        self.font_size.setRange(12, 400)
        self.font_size.setValue(48)
        self.font_size.setToolTip("逻辑画布像素字号（与导入 PPT 磅值已换算）")
        self.font_size.valueChanged.connect(self._emit_element)
        text_form.addRow("字号", self.font_size)

        self.font_color_btn = QPushButton("颜色")
        self.font_color_btn.clicked.connect(self._pick_font_color)
        text_form.addRow("颜色", self.font_color_btn)

        style_row = QHBoxLayout()
        style_row.setSpacing(8)
        self.bold_btn = _toggle("粗体")
        self.italic_btn = _toggle("斜体")
        self.wrap_btn = _toggle("自动换行")
        self.wrap_btn.setChecked(True)
        for b in (self.bold_btn, self.italic_btn, self.wrap_btn):
            b.toggled.connect(self._emit_element)
            style_row.addWidget(b)
        style_row.addStretch(1)
        text_form.addRow("样式", style_row)

        self.align = SermonComboBox()
        self.align.setMaxVisibleItems(8)
        self.align.addItem("左对齐", "left")
        self.align.addItem("居中", "center")
        self.align.addItem("右对齐", "right")
        self.align.currentIndexChanged.connect(self._emit_element)
        text_form.addRow("对齐", self.align)
        text_col.addLayout(text_form)
        layout.addWidget(self.text_section)

        # —— 形状 ——
        self.shape_section = QWidget()
        shape_col = QVBoxLayout(self.shape_section)
        shape_col.setContentsMargins(0, 0, 0, 0)
        shape_col.setSpacing(8)
        shape_col.addWidget(_section("形状"))
        shape_form = QFormLayout()
        shape_form.setContentsMargins(0, 0, 0, 0)
        shape_form.setHorizontalSpacing(12)
        shape_form.setVerticalSpacing(10)
        shape_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.shape_kind = SermonComboBox()
        self.shape_kind.setMaxVisibleItems(8)
        self.shape_kind.addItem("矩形", "rect")
        self.shape_kind.addItem("椭圆", "ellipse")
        self.shape_kind.currentIndexChanged.connect(self._emit_element)
        shape_form.addRow("种类", self.shape_kind)
        self.fill_color_btn = QPushButton("填充色")
        self.fill_color_btn.clicked.connect(self._pick_fill_color)
        shape_form.addRow("填充", self.fill_color_btn)
        self.opacity = QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setValue(100)
        self.opacity.valueChanged.connect(self._emit_element)
        shape_form.addRow("透明度", self.opacity)
        shape_col.addLayout(shape_form)
        layout.addWidget(self.shape_section)

        # —— 位置 ——
        self.geom_section = QWidget()
        geom_col = QVBoxLayout(self.geom_section)
        geom_col.setContentsMargins(0, 0, 0, 0)
        geom_col.setSpacing(8)
        geom_col.addWidget(_section("位置 / 尺寸"))
        geom_grid = QGridLayout()
        geom_grid.setHorizontalSpacing(8)
        geom_grid.setVerticalSpacing(8)
        self.spin_x = QSpinBox()
        self.spin_y = QSpinBox()
        self.spin_w = QSpinBox()
        self.spin_h = QSpinBox()
        for spin, mx in (
            (self.spin_x, 4000),
            (self.spin_y, 4000),
            (self.spin_w, 4000),
            (self.spin_h, 4000),
        ):
            spin.setRange(0, mx)
            spin.setMinimumWidth(72)
            spin.valueChanged.connect(self._emit_element)
        geom_grid.addWidget(QLabel("X"), 0, 0)
        geom_grid.addWidget(self.spin_x, 0, 1)
        geom_grid.addWidget(QLabel("Y"), 0, 2)
        geom_grid.addWidget(self.spin_y, 0, 3)
        geom_grid.addWidget(QLabel("宽"), 1, 0)
        geom_grid.addWidget(self.spin_w, 1, 1)
        geom_grid.addWidget(QLabel("高"), 1, 2)
        geom_grid.addWidget(self.spin_h, 1, 3)
        geom_col.addLayout(geom_grid)
        layout.addWidget(self.geom_section)

        # —— 图层 ——
        self.layer_section = QWidget()
        layer_col = QVBoxLayout(self.layer_section)
        layer_col.setContentsMargins(0, 0, 0, 0)
        layer_col.setSpacing(8)
        layer_col.addWidget(_section("图层顺序"))
        layer_row = QHBoxLayout()
        layer_row.setSpacing(8)
        self.front_btn = QPushButton("置顶")
        self.up_btn = QPushButton("↑")
        self.down_btn = QPushButton("↓")
        self.back_btn = QPushButton("置底")
        for b, act in (
            (self.front_btn, "front"),
            (self.up_btn, "up"),
            (self.down_btn, "down"),
            (self.back_btn, "back"),
        ):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(
                {
                    "front": "移到最上层",
                    "up": "上移一层",
                    "down": "下移一层",
                    "back": "移到最下层",
                }[act]
            )
            b.clicked.connect(lambda _=False, a=act: self.layer_reorder.emit(a))
            layer_row.addWidget(b)
        layer_col.addLayout(layer_row)
        layout.addWidget(self.layer_section)

        # —— 图层对齐 / 分布（单选相对幻灯片也可） ——
        self.multi_section = QWidget()
        multi_col = QVBoxLayout(self.multi_section)
        multi_col.setContentsMargins(0, 0, 0, 0)
        multi_col.setSpacing(8)
        multi_col.addWidget(_section("图层对齐"))
        rel_form = QFormLayout()
        rel_form.setContentsMargins(0, 0, 0, 0)
        rel_form.setHorizontalSpacing(12)
        rel_form.setVerticalSpacing(8)
        self.align_relative = SermonComboBox()
        self.align_relative.setMaxVisibleItems(8)
        self.align_relative.addItem("相对于幻灯片", "slide")
        self.align_relative.addItem("相对于对象", "selection")
        self.align_relative.setCurrentIndex(0)
        self.align_relative.currentIndexChanged.connect(self._refresh_align_enabled)
        rel_form.addRow("对齐方式", self.align_relative)
        multi_col.addLayout(rel_form)
        h_row = QHBoxLayout()
        h_row.setSpacing(6)
        self._align_btns: list[QPushButton] = []
        for text, mode in (
            ("左", "left"),
            ("水平居中", "hcenter"),
            ("右", "right"),
        ):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: self.align_requested.emit(m))
            h_row.addWidget(b)
            self._align_btns.append(b)
        self.h_dist_btn = QPushButton("横向分布")
        self.h_dist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.h_dist_btn.clicked.connect(lambda: self.distribute_requested.emit("h"))
        h_row.addWidget(self.h_dist_btn)
        multi_col.addLayout(h_row)
        v_row = QHBoxLayout()
        v_row.setSpacing(6)
        for text, mode in (
            ("顶", "top"),
            ("垂直居中", "vcenter"),
            ("底", "bottom"),
        ):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: self.align_requested.emit(m))
            v_row.addWidget(b)
            self._align_btns.append(b)
        self.v_dist_btn = QPushButton("纵向分布")
        self.v_dist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.v_dist_btn.clicked.connect(lambda: self.distribute_requested.emit("v"))
        v_row.addWidget(self.v_dist_btn)
        multi_col.addLayout(v_row)
        layout.addWidget(self.multi_section)

        self.hint = QLabel("选中画布上的元素以编辑属性。")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("sermonHint")
        layout.addWidget(self.hint)
        layout.addStretch(1)

        outer.addWidget(_scroll_wrap(body))

        self._element: Element | None = None
        self._selection: list[Element] = []
        self._block = False
        self._font_color = "#FFFFFF"
        self._fill_color = "#000000"
        self._show_element_ui(False)
        self.multi_section.hide()

    def _populate_fonts(self):
        preferred = ("微软雅黑", "宋体", "黑体", "楷体", "仿宋", "Arial", "Times New Roman")
        families = list(QFontDatabase.families())
        seen: set[str] = set()
        self.font_family.clear()
        for name in preferred:
            if name in families and name not in seen:
                self.font_family.addItem(name)
                seen.add(name)
        for name in sorted(families, key=lambda s: s.casefold()):
            if name not in seen:
                self.font_family.addItem(name)
                seen.add(name)

    def set_selection(self, elements: list[Element]):
        """0 个：空提示；≥1：可对齐（相对幻灯片）；≥2：可相对对象；≥3：可分布。"""
        self._selection = list(elements)
        n = len(elements)
        if n >= 1:
            self.multi_section.show()
            self._refresh_align_enabled()
            if n == 1:
                self.set_element(elements[0])
                self.multi_section.show()
                self.hint.setText("已选 1 个图层。可相对幻灯片对齐。")
            else:
                self._element = None
                self._show_element_ui(False)
                rel = self.align_relative_mode()
                tip = "相对幻灯片" if rel == "slide" else "相对对象"
                self.hint.setText(f"已选 {n} 个图层。对齐{tip}；分布需 ≥3。")
            return
        self.multi_section.hide()
        self.set_element(None)

    def align_relative_mode(self) -> str:
        data = self.align_relative.currentData()
        return str(data or "slide")

    def _refresh_align_enabled(self):
        n = len(getattr(self, "_selection", []) or [])
        rel = self.align_relative_mode()
        can_align = n >= 1 if rel == "slide" else n >= 2
        for b in self._align_btns:
            b.setEnabled(can_align)
        self.h_dist_btn.setEnabled(n >= 3)
        self.v_dist_btn.setEnabled(n >= 3)
        if n == 1:
            if rel == "slide":
                self.hint.setText("已选 1 个图层。可相对幻灯片对齐。")
            else:
                self.hint.setText("已选 1 个图层。「相对于对象」需再选至少 1 个。")
        elif n >= 2:
            tip = "相对幻灯片" if rel == "slide" else "相对对象"
            self.hint.setText(f"已选 {n} 个图层。对齐{tip}；分布需 ≥3。")

    def set_element(self, element: Element | None):
        self._element = element
        self._block = True
        if element is None:
            self._show_element_ui(False)
            if not self._selection:
                self.multi_section.hide()
            self.hint.setText("选中画布上的元素以编辑属性。")
        else:
            self._show_element_ui(True)
            type_zh = _TYPE_LABELS.get(element.type, element.type)
            self.hint.setText(f"元素：{type_zh}")
            self.spin_x.setValue(int(element.x))
            self.spin_y.setValue(int(element.y))
            self.spin_w.setValue(int(max(1, element.w)))
            self.spin_h.setValue(int(max(1, element.h)))
            is_text = element.type == "text"
            is_shape = element.type == "shape"
            self.text_section.setVisible(is_text)
            self.shape_section.setVisible(is_shape)
            if is_text:
                style = element.style
                self.font_family.setCurrentText(style.font_family)
                self.font_size.setValue(style.font_size)
                self._font_color = style.color
                self._update_color_btn(self.font_color_btn, self._font_color)
                self.bold_btn.setChecked(style.bold)
                self.italic_btn.setChecked(style.italic)
                idx = self.align.findData(style.align)
                if idx >= 0:
                    self.align.setCurrentIndex(idx)
                self.wrap_btn.setChecked(bool(getattr(style, "wrap", True)))
            if is_shape:
                sk = self.shape_kind.findData(element.shape or "rect")
                if sk >= 0:
                    self.shape_kind.setCurrentIndex(sk)
                self._fill_color = element.style.color or "#000000"
                self._update_color_btn(self.fill_color_btn, self._fill_color)
                self.opacity.setValue(int(round(float(element.style.opacity) * 100)))
        self._block = False

    def _show_element_ui(self, visible: bool):
        is_text = visible and self._element is not None and self._element.type == "text"
        is_shape = visible and self._element is not None and self._element.type == "shape"
        self.text_section.setVisible(is_text)
        self.shape_section.setVisible(is_shape)
        self.geom_section.setVisible(visible)
        self.layer_section.setVisible(visible)

    def _update_color_btn(self, btn: QPushButton, color: str):
        c = QColor(color)
        if not c.isValid():
            c = QColor("#FFFFFF")
        fg = "#0F172A" if c.lightness() > 140 else "#FFFFFF"
        btn.setStyleSheet(
            "QPushButton {"
            f" background: {c.name()}; color: {fg};"
            " border: 1px solid rgba(0,0,0,40);"
            " border-radius: 6px; min-height: 30px;"
            "}"
        )
        btn.setText(c.name().upper())

    def _pick_font_color(self):
        if self._element is None:
            return
        color = QColorDialog.getColor(QColor(self._font_color), self, "文字颜色")
        if not color.isValid():
            return
        self._font_color = color.name().upper()
        self._update_color_btn(self.font_color_btn, self._font_color)
        self._emit_element()

    def _pick_fill_color(self):
        if self._element is None:
            return
        color = QColorDialog.getColor(QColor(self._fill_color), self, "填充颜色")
        if not color.isValid():
            return
        self._fill_color = color.name().upper()
        self._update_color_btn(self.fill_color_btn, self._fill_color)
        self._emit_element()

    def _emit_element(self, *_args):
        if self._block or self._element is None:
            return
        el = self._element
        el.x = float(self.spin_x.value())
        el.y = float(self.spin_y.value())
        el.w = float(self.spin_w.value())
        el.h = float(self.spin_h.value())
        if el.type == "text":
            el.style.font_family = self.font_family.currentText().strip() or "微软雅黑"
            el.style.font_size = int(self.font_size.value())
            el.style.color = self._font_color
            el.style.bold = self.bold_btn.isChecked()
            el.style.italic = self.italic_btn.isChecked()
            el.style.align = str(self.align.currentData() or "left")
            el.style.wrap = self.wrap_btn.isChecked()
        elif el.type == "shape":
            el.shape = str(self.shape_kind.currentData() or "rect")
            el.style.color = self._fill_color
            el.style.opacity = max(0.0, min(1.0, self.opacity.value() / 100.0))
        self.element_changed.emit(el)

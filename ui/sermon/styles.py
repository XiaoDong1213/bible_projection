"""讲篇模块样式：沿用主应用令牌与蓝系 accent。"""

from __future__ import annotations

from core.paths import styles_dir as default_styles_dir
from ui.themes.stylesheet import RADIUS, SPACE, FONT_FAMILY, theme_tokens


def sermon_accent(theme: str = "dark") -> dict[str, str]:
    """讲篇强调色：与主界面蓝系 accent 一致，避免暖金跳色。"""
    t = theme_tokens(theme)
    return {
        "sermon": t["accent"],
        "sermon_hover": t["accent_hover"],
        "sermon_pressed": t["accent_pressed"],
        "sermon_soft": t["accent_soft"],
        "sermon_text": t["accent_text"],
        "sermon_on": "#FFFFFF",
    }


def _arrow_down(theme: str) -> str:
    suffix = "dark" if theme == "dark" else "light"
    return (default_styles_dir() / f"arrow-down-{suffix}.svg").as_posix()


def build_sermon_stylesheet(theme: str = "dark", arrow_down: str | None = None) -> str:
    """讲篇编辑器 / 演讲者视图 / 会话底栏 QSS。"""
    t = theme_tokens(theme)
    a = sermon_accent(theme)
    r = RADIUS
    s = SPACE
    arrow = arrow_down or _arrow_down(theme)
    return f"""
/* —— 讲篇编辑器 —— */
QWidget#sermonEditorWindow {{
    background: {t['canvas']};
    color: {t['text']};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QWidget#sermonEditorWindow QMenuBar {{
    background: {t['surface']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
    padding: 2px 8px;
}}
QWidget#sermonEditorWindow QMenuBar::item {{
    background: transparent;
    color: {t['text']};
    padding: 6px 10px;
    border-radius: {r['sm']}px;
}}
QWidget#sermonEditorWindow QMenuBar::item:selected {{
    background: {t['control_hover']};
    color: {t['text']};
}}
QWidget#sermonEditorWindow QMenuBar::item:pressed {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
}}
QWidget#sermonEditorWindow QMenu {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 4px;
}}
QWidget#sermonEditorWindow QMenu::item {{
    background: transparent;
    color: {t['text']};
    padding: 7px 22px 7px 14px;
    border-radius: {r['sm']}px;
    min-height: 28px;
}}
QWidget#sermonEditorWindow QMenu::item:selected {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
}}
QWidget#sermonEditorWindow QMenu::item:disabled {{
    color: {t['text_faint']};
}}
QWidget#sermonEditorWindow QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 4px 8px;
}}
QWidget#sermonEditorWindow QStatusBar {{
    background: {t['surface']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
}}
QTabWidget#sermonSideTabs {{
    background: transparent;
    border: none;
}}
QTabWidget#sermonSideTabs::pane {{
    background: transparent;
    border: none;
    top: 0;
    margin: 0;
    padding: 0;
}}
QTabWidget#sermonSideTabs QTabBar {{
    background: transparent;
    border: none;
    alignment: center;
}}
QTabWidget#sermonSideTabs QTabBar::tab {{
    background: transparent;
    color: {t['text_muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 6px 8px 6px;
    margin: 0;
    min-width: 56px;
    font-size: 13px;
    font-weight: 500;
}}
QTabWidget#sermonSideTabs QTabBar::tab:selected {{
    background: transparent;
    color: {a['sermon_text']};
    font-weight: 600;
    border-bottom: 2px solid {a['sermon']};
}}
QTabWidget#sermonSideTabs QTabBar::tab:hover:!selected {{
    color: {t['text']};
    background: transparent;
}}
QPushButton#sermonBackBtn {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
}}
QPushButton#sermonBackBtn:hover {{
    background: {t['control_hover']};
}}
QLabel#sermonSectionLabel {{
    color: {t['text']};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 2px 0 4px 0;
}}
QPushButton#sermonToggleBtn {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 2px 10px;
    min-height: 26px;
    max-height: 28px;
    font-size: 12px;
}}
QPushButton#sermonToggleBtn:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
QPushButton#sermonToggleBtn:checked {{
    background: {a['sermon_soft']};
    color: {a['sermon_text']};
    border: 1px solid {a['sermon']};
    font-weight: 600;
}}
QPushButton#sermonToggleBtn:checked:hover {{
    background: {a['sermon']};
    color: {a['sermon_on']};
}}
QWidget#sermonBackgroundPanel,
QWidget#sermonPropertyPanel,
QWidget#sermonAnimPanel,
QWidget#sermonTransitionPanel {{
    background: transparent;
}}
QScrollArea#sermonPropertyScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#sermonPropertyScroll > QWidget > QWidget {{
    background: transparent;
}}
QLabel#sermonHint {{
    color: {t['text_faint']};
    font-size: 11px;
    line-height: 1.35;
}}
QPushButton#sermonTransitionBtn {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 4px 6px;
    min-height: 36px;
    max-height: 42px;
    font-size: 12px;
}}
QPushButton#sermonTransitionBtn:hover {{
    background: {t['control_hover']};
}}
QPushButton#sermonTransitionBtn:checked {{
    background: {a['sermon']};
    color: {a['sermon_on']};
    border-color: {a['sermon']};
}}
QWidget#sermonBackgroundPanel QPushButton,
QWidget#sermonPropertyPanel QPushButton,
QWidget#sermonAnimPanel QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 2px 8px;
    min-height: 26px;
    max-height: 28px;
}}
QWidget#sermonBackgroundPanel QPushButton:hover,
QWidget#sermonPropertyPanel QPushButton:hover,
QWidget#sermonAnimPanel QPushButton:hover {{
    background: {t['control_hover']};
}}
QWidget#sermonPropertyPanel QPushButton#sermonToggleBtn {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 2px 10px;
    min-height: 26px;
    max-height: 28px;
    font-size: 12px;
    font-weight: 400;
}}
QWidget#sermonPropertyPanel QPushButton#sermonToggleBtn:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
QWidget#sermonPropertyPanel QPushButton#sermonToggleBtn:checked {{
    background: {a['sermon_soft']};
    color: {a['sermon_text']};
    border: 1px solid {a['sermon']};
    font-weight: 600;
}}
QWidget#sermonPropertyPanel QPushButton#sermonToggleBtn:checked:hover {{
    background: {a['sermon']};
    color: {a['sermon_on']};
}}
QWidget#sermonBackgroundPanel QComboBox,
QWidget#sermonBackgroundPanel QSpinBox,
QWidget#sermonPropertyPanel QComboBox,
QWidget#sermonPropertyPanel QSpinBox,
QWidget#sermonAnimPanel QComboBox,
QWidget#sermonAnimPanel QSpinBox {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 4px 28px 4px 10px;
    min-height: 28px;
}}
QWidget#sermonBackgroundPanel QComboBox QLineEdit,
QWidget#sermonPropertyPanel QComboBox QLineEdit,
QWidget#sermonAnimPanel QComboBox QLineEdit,
QToolBar#sermonToolBar QComboBox QLineEdit {{
    background: transparent;
    color: {t['text']};
    border: none;
    padding: 0;
    margin: 0;
    selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
}}
QWidget#sermonBackgroundPanel QComboBox:hover,
QWidget#sermonPropertyPanel QComboBox:hover,
QWidget#sermonAnimPanel QComboBox:hover,
QWidget#sermonBackgroundPanel QSpinBox:hover,
QWidget#sermonPropertyPanel QSpinBox:hover,
QWidget#sermonAnimPanel QSpinBox:hover {{
    border-color: {t['border_strong']};
}}
QWidget#sermonBackgroundPanel QComboBox:focus,
QWidget#sermonPropertyPanel QComboBox:focus,
QWidget#sermonAnimPanel QComboBox:focus,
QWidget#sermonBackgroundPanel QSpinBox:focus,
QWidget#sermonPropertyPanel QSpinBox:focus,
QWidget#sermonAnimPanel QSpinBox:focus {{
    border: 2px solid {t['focus_ring']};
}}
QWidget#sermonBackgroundPanel QComboBox::drop-down,
QWidget#sermonPropertyPanel QComboBox::drop-down,
QWidget#sermonAnimPanel QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
}}
QWidget#sermonBackgroundPanel QComboBox::down-arrow,
QWidget#sermonPropertyPanel QComboBox::down-arrow,
QWidget#sermonAnimPanel QComboBox::down-arrow {{
    image: url({arrow});
    width: 12px;
    height: 8px;
}}
QWidget#sermonBackgroundPanel QComboBox QAbstractItemView,
QWidget#sermonPropertyPanel QComboBox QAbstractItemView,
QWidget#sermonAnimPanel QComboBox QAbstractItemView {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}}
QWidget#sermonBackgroundPanel QComboBox QAbstractItemView::item,
QWidget#sermonPropertyPanel QComboBox QAbstractItemView::item,
QWidget#sermonAnimPanel QComboBox QAbstractItemView::item,
QToolBar#sermonToolBar QComboBox QAbstractItemView::item {{
    min-height: 30px;
    padding: 6px 12px;
}}
QWidget#sermonBackgroundPanel QComboBox QAbstractItemView::item:hover,
QWidget#sermonPropertyPanel QComboBox QAbstractItemView::item:hover,
QWidget#sermonAnimPanel QComboBox QAbstractItemView::item:hover,
QToolBar#sermonToolBar QComboBox QAbstractItemView::item:hover {{
    background: {t['control_hover']};
    color: {t['text']};
}}
QWidget#sermonBackgroundPanel QComboBox QAbstractItemView::item:selected,
QWidget#sermonPropertyPanel QComboBox QAbstractItemView::item:selected,
QWidget#sermonAnimPanel QComboBox QAbstractItemView::item:selected,
QToolBar#sermonToolBar QComboBox QAbstractItemView::item:selected {{
    background: {t['accent']};
    color: #FFFFFF;
}}
QWidget#sermonBackgroundPanel QLabel,
QWidget#sermonPropertyPanel QLabel {{
    color: {t['text_muted']};
    font-size: 12px;
}}
QWidget#sermonBackgroundPanel QLabel#sermonSectionLabel,
QWidget#sermonPropertyPanel QLabel#sermonSectionLabel {{
    color: {t['text']};
    font-size: 12px;
    font-weight: 600;
}}
QWidget#sermonBackgroundPanel QLabel#sermonHint,
QWidget#sermonPropertyPanel QLabel#sermonHint,
QWidget#sermonAnimPanel QLabel#sermonHint {{
    color: {t['text_faint']};
    font-size: 11px;
}}
QWidget#sermonAnimPanel QListWidget {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 4px;
    outline: none;
}}
QWidget#sermonAnimPanel QListWidget::item {{
    color: {t['text']};
    padding: 6px 8px;
    border-radius: {r['sm']}px;
}}
QWidget#sermonAnimPanel QListWidget::item:hover {{
    background: {t['control_hover']};
}}
QWidget#sermonAnimPanel QListWidget::item:selected {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
}}

/* 工具栏 */
QToolBar#sermonToolBar {{
    background: {t['surface']};
    border-bottom: 1px solid {t['border']};
    spacing: {s['sm']}px;
    padding: {s['sm']}px {s['md']}px;
    min-height: 52px;
}}
QToolBar#sermonToolBar::separator {{
    background: {t['border']};
    width: 1px;
    margin: 8px 6px;
}}
QLabel#sermonTitleLabel {{
    color: {t['text']};
    font-size: 15px;
    font-weight: 600;
    padding: 0 8px 0 2px;
    min-width: 120px;
}}
QLabel#sermonToolSection {{
    color: {t['text_faint']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0 4px;
}}
QToolBar#sermonToolBar QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 6px 12px;
    min-height: 32px;
    font-size: 13px;
}}
QToolBar#sermonToolBar QPushButton:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
QToolBar#sermonToolBar QPushButton:pressed {{
    background: {t['control_pressed']};
}}
QToolBar#sermonToolBar QPushButton:disabled {{
    color: {t['text_faint']};
    background: {t['surface_sunken']};
}}
QToolBar#sermonToolBar QPushButton:focus {{
    border: 2px solid {t['focus_ring']};
}}
QPushButton#sermonPlayBtn {{
    background: {a['sermon']};
    color: {a['sermon_on']};
    border: 1px solid {a['sermon']};
    font-weight: 600;
}}
QPushButton#sermonPlayBtn:hover {{
    background: {a['sermon_hover']};
    border-color: {a['sermon_hover']};
}}
QPushButton#sermonPlayBtn:pressed {{
    background: {a['sermon_pressed']};
}}
QPushButton#sermonStopBtn {{
    background: {t['danger_soft']};
    color: {t['danger_text']};
    border: 1px solid {t['danger']};
}}
QPushButton#sermonStopBtn:hover {{
    background: {t['danger']};
    color: #FFFFFF;
}}
QToolBar#sermonToolBar QComboBox {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 4px 28px 4px 10px;
    min-height: 32px;
    min-width: 80px;
}}
QToolBar#sermonToolBar QComboBox:hover {{
    border-color: {t['border_strong']};
}}
QToolBar#sermonToolBar QComboBox:focus {{
    border: 2px solid {t['focus_ring']};
}}
QToolBar#sermonToolBar QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
}}
QToolBar#sermonToolBar QComboBox::down-arrow {{
    image: url({arrow});
    width: 12px;
    height: 8px;
}}
QToolBar#sermonToolBar QComboBox QAbstractItemView {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
    outline: none;
    padding: 4px;
}}

/* 左侧幻灯片列 */
QWidget#sermonSlideList {{
    background: {t['surface']};
    border-right: 1px solid {t['border']};
}}
QLabel#sermonPanelTitle {{
    color: {t['text']};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 0 6px 0;
}}
QListWidget#sermonSlideListView {{
    background: transparent;
    border: none;
    outline: none;
    padding: 2px;
}}
QListWidget#sermonSlideListView::item {{
    background: {t['control']};
    color: {t['text_muted']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    padding: 6px 4px 4px 4px;
    margin: 0 0 6px 0;
}}
QListWidget#sermonSlideListView::item:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}
QListWidget#sermonSlideListView::item:selected {{
    background: {a['sermon_soft']};
    border: 2px solid {a['sermon']};
    color: {a['sermon_text']};
}}
QWidget#sermonSlideList QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
}}
QWidget#sermonSlideList QPushButton:hover {{
    background: {t['control_hover']};
}}
QLabel#sermonSlideListMeta {{
    color: {t['text_faint']};
    font-size: 11px;
    padding: 4px 0 0 0;
}}

/* 画布舞台 */
QWidget#sermonCanvasHost {{
    background: {t['canvas']};
}}
QGraphicsView#sermonCanvas {{
    background: {t['preview_bg']};
    border: none;
    border-radius: 0;
}}
QLabel#sermonCanvasCaption {{
    color: {t['text_faint']};
    font-size: 11px;
    padding: 6px 12px 0 12px;
}}

/* 右侧属性轨 */
QWidget#sermonSideRail {{
    background: {t['surface']};
    border-left: 1px solid {t['border']};
}}

/* 演讲者视图 */
QWidget#sermonPresenterView {{
    background: {t['canvas']};
}}
QWidget#sermonPresenterView QLabel#sermonPanelTitle {{
    font-size: 14px;
    letter-spacing: 0.02em;
    text-transform: none;
    font-weight: 600;
    color: {t['text']};
}}
QLabel#sermonStageCaption {{
    color: {t['text_muted']};
    font-size: 12px;
    font-weight: 600;
}}
QGraphicsView#sermonSlideStage {{
    background: {t['preview_bg']};
    border: none;
    border-radius: 0;
}}

/* 会话底栏 */
QWidget#sermonSessionBar {{
    background: {t['surface']};
    border-top: 1px solid {t['border']};
    min-height: 56px;
}}
QWidget#sermonSessionBar QLabel#sermonSessionStatus {{
    color: {t['text']};
    font-size: 13px;
    font-weight: 600;
}}
QWidget#sermonSessionBar QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 6px 14px;
    min-width: 92px;
    min-height: 36px;
    font-size: 13px;
}}
QWidget#sermonSessionBar QPushButton:hover {{
    background: {t['control_hover']};
}}
QWidget#sermonSessionBar QPushButton:disabled {{
    color: {t['text_faint']};
    background: {t['surface_sunken']};
}}
QWidget#sermonSessionBar QPushButton:focus {{
    border: 2px solid {t['focus_ring']};
}}
QPushButton#sermonChannelActive {{
    background: {a['sermon_soft']};
    color: {a['sermon_text']};
    border: 1px solid {a['sermon']};
    font-weight: 600;
}}
QPushButton#sermonSessionNext {{
    background: {a['sermon']};
    color: {a['sermon_on']};
    border: 1px solid {a['sermon']};
    font-weight: 600;
}}
QPushButton#sermonSessionNext:hover {{
    background: {a['sermon_hover']};
}}
QPushButton#sermonSessionEnd {{
    background: {t['danger_soft']};
    color: {t['danger_text']};
    border: 1px solid {t['danger']};
}}

/* 主工具栏「讲篇」入口：与「经文搜索」等同权 */
QPushButton#sermonToolbarButton {{
    min-width: 56px;
    max-height: 40px;
    min-height: 40px;
    padding: 0 12px;
    font-size: 13px;
    font-weight: 400;
}}
"""


from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QListView,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


_ITEM_ROW_MIN = 44  # 可视行高，避免末项被裁切
_POPUP_MAX_ROWS = 8  # 显示不全时最多 8 项；不足则全显
_POPUP_PAD = 12  # view 上下 padding + 边框余量


class _SermonComboItemDelegate(QStyledItemDelegate):
    """固定行高，避免 Windows 原生委托把条目画成薄条。"""

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), _ITEM_ROW_MIN))


class _SermonComboListView(QListView):
    """下拉列表：无滚动条；滚轮只换高亮；到顶/底不再空滑。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerItem)
        self.setAutoScroll(False)

    def wheelEvent(self, event):
        model = self.model()
        if model is None or model.rowCount() <= 0:
            event.accept()
            return
        idx = self.currentIndex()
        row = idx.row() if idx.isValid() else 0
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        if delta > 0:
            row = max(0, row - 1)
        elif delta < 0:
            row = min(model.rowCount() - 1, row + 1)
        else:
            event.accept()
            return
        new_idx = model.index(row, 0)
        self.setCurrentIndex(new_idx)
        # EnsureVisible：到顶/底不再往空处滑
        self.scrollTo(new_idx, QListView.ScrollHint.EnsureVisible)
        event.accept()

    def scrollContentsBy(self, dx: int, dy: int):
        # 钳制：内容不足一屏时禁止纵向位移，避免空滑
        bar = self.verticalScrollBar()
        if bar is not None and bar.maximum() <= 0 and dy != 0:
            super().scrollContentsBy(dx, 0)
            return
        super().scrollContentsBy(dx, dy)


def combo_popup_qss(theme: str = "dark") -> str:
    t = theme_tokens(theme)
    r = RADIUS
    return f"""
QAbstractItemView, QListView {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    outline: none;
    padding: 4px;
}}
QAbstractItemView::item, QListView::item {{
    min-height: {_ITEM_ROW_MIN}px;
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    color: {t['text']};
}}
QAbstractItemView::item:hover, QListView::item:hover {{
    background: {t['control_hover']};
    color: {t['text']};
}}
QAbstractItemView::item:selected, QListView::item:selected {{
    background: {t['accent']};
    color: #FFFFFF;
}}
QAbstractItemView::item:selected:hover, QListView::item:selected:hover {{
    background: {t['accent_hover']};
    color: #FFFFFF;
}}
"""


def combo_frame_qss(theme: str = "dark") -> str:
    t = theme_tokens(theme)
    return f"QFrame {{ background: {t['surface_raised']}; border: none; }}"


class SermonComboBox(QComboBox):
    """讲篇下拉：与「显示设置 / 字体」同一弹出路径。

    一律 editable（Windows 上不可编辑框走另一套原生弹出，QSS 常失效）。
    searchable=False 时输入框只读，点击即弹出，外观仍与字体框一致。
    """

    def __init__(self, parent=None, *, searchable: bool = False):
        super().__init__(parent)
        self._sermon_theme = "dark"
        self._searchable = bool(searchable)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMaxVisibleItems(_POPUP_MAX_ROWS)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(6)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # 关键：与字体框同一弹出路径
        self.setEditable(True)
        self._apply_edit_mode()
        polish_sermon_combo(self, self._sermon_theme)

    def set_searchable(self, searchable: bool):
        self._searchable = bool(searchable)
        self._apply_edit_mode()

    def _apply_edit_mode(self):
        edit = self.lineEdit()
        if edit is None:
            return
        edit.setReadOnly(not self._searchable)
        edit.setCursor(
            Qt.CursorShape.IBeamCursor
            if self._searchable
            else Qt.CursorShape.PointingHandCursor
        )
        if not self._searchable and not getattr(edit, "_sermon_popup_click", False):
            # 只读：点击即弹出（与字体框同路径，但不允许打字）
            def _press(_ev, box=self):
                box.showPopup()

            edit.mousePressEvent = _press  # type: ignore[method-assign]
            edit._sermon_popup_click = True

    def set_sermon_theme(self, theme: str):
        self._sermon_theme = theme or "dark"
        polish_sermon_combo(self, self._sermon_theme)
        self._apply_edit_mode()

    def _target_width(self) -> int:
        w = int(self.width())
        if self.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed:
            return max(w, 72)
        return max(w, 1)

    def _visible_rows(self) -> int:
        return min(_POPUP_MAX_ROWS, max(1, self.count()))

    def _row_height(self) -> int:
        view = self.view()
        hint = 0
        if view is not None and self.count() > 0:
            hint = int(view.sizeHintForRow(0) or 0)
        # 取实测与下限较大者，防止裁切末项
        return max(hint, _ITEM_ROW_MIN)

    def _popup_height(self) -> int:
        return self._row_height() * self._visible_rows() + _POPUP_PAD

    def _prepare_popup_geometry(self):
        """弹出前锁宽高：项数 ≤8 全显；>8 只开 8 行。"""
        visible = self._visible_rows()
        self.setMaxVisibleItems(visible)
        width = self._target_width()
        # 先设样式再量行高
        height = self._popup_height()
        view = self.view()
        view.setMinimumSize(width, height)
        view.setMaximumSize(width, height)
        view.setFixedSize(width, height)
        container = view.parentWidget()
        if container is not None:
            container.setMinimumSize(width, height)
            container.setMaximumSize(width, height)
            container.setFixedSize(width, height)

    def showPopup(self):
        completer = self.completer()
        if completer is not None and completer.popup() is not None:
            completer.popup().hide()

        theme = getattr(self, "_sermon_theme", "dark")
        polish_sermon_combo(self, theme)
        self._prepare_popup_geometry()

        view = self.view()
        view.setAutoFillBackground(True)
        super().showPopup()

        # 弹出后再钉一次：短列表禁止 Qt 撑出空洞
        self._prepare_popup_geometry()
        popup = view.window()
        if popup is not None and popup is not self.window():
            popup.setAutoFillBackground(True)
            popup.setStyleSheet(combo_frame_qss(theme))
            popup.setFixedSize(self._target_width(), self._popup_height())
            popup.raise_()

    def hidePopup(self):
        super().hidePopup()
        self.setMaxVisibleItems(_POPUP_MAX_ROWS)


def polish_sermon_combo(combo: QComboBox, theme: str = "dark") -> None:
    """统一 view 样式 / 行高委托 / 选中色（含非 SermonComboBox 兜底）。"""
    if not isinstance(combo, QComboBox):
        return
    theme = theme or "dark"
    setattr(combo, "_sermon_theme", theme)
    t = theme_tokens(theme)

    if combo.maxVisibleItems() > _POPUP_MAX_ROWS or combo.maxVisibleItems() < 1:
        combo.setMaxVisibleItems(_POPUP_MAX_ROWS)

    # 凡讲篇下拉，强制 editable 路径（否则 Windows 原生弹出吃不到蓝选中）
    if not combo.isEditable():
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        edit = combo.lineEdit()
        if edit is not None and not isinstance(combo, SermonComboBox):
            edit.setReadOnly(True)

    view = combo.view()
    if not isinstance(view, _SermonComboListView):
        view = _SermonComboListView(combo)
        combo.setView(view)
    view.setUniformItemSizes(True)
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
    view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setAutoScroll(False)
    view.setSpacing(0)
    view.setItemDelegate(_SermonComboItemDelegate(view))
    view.setStyleSheet(combo_popup_qss(theme))

    # Palette：Windows 样式经常只认这个，不认 QSS selected
    pal = view.palette()
    accent = QColor(t["accent"])
    pal.setColor(QPalette.ColorRole.Base, QColor(t["surface_raised"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    view.setPalette(pal)
    view.setAutoFillBackground(True)

    if "QComboBox QAbstractItemView" in (combo.styleSheet() or ""):
        combo.setStyleSheet("")

    if isinstance(combo, SermonComboBox):
        return

    if getattr(combo, "_sermon_popup_hooked", False):
        return

    def show_popup_wrapped():
        th = getattr(combo, "_sermon_theme", theme)
        polish_sermon_combo(combo, th)
        n = max(1, combo.count())
        visible = min(_POPUP_MAX_ROWS, n)
        combo.setMaxVisibleItems(visible)
        width = max(int(combo.width()), 1)
        height = _ITEM_ROW_MIN * visible + _POPUP_PAD
        hint = int(view.sizeHintForRow(0) or 0)
        if hint > _ITEM_ROW_MIN:
            height = hint * visible + _POPUP_PAD
        view.setMinimumSize(width, height)
        view.setMaximumSize(width, height)
        view.setFixedSize(width, height)
        container = view.parentWidget()
        if container is not None:
            container.setMinimumSize(width, height)
            container.setMaximumSize(width, height)
            container.setFixedSize(width, height)
        view.setAutoFillBackground(True)
        QComboBox.showPopup(combo)
        view.setFixedSize(width, height)
        if container is not None:
            container.setFixedSize(width, height)
        popup = view.window()
        if popup is not None and popup is not combo.window():
            popup.setAutoFillBackground(True)
            popup.setStyleSheet(combo_frame_qss(th))
            popup.setFixedSize(width, height)
            popup.raise_()
        combo.setMaxVisibleItems(_POPUP_MAX_ROWS)

    combo.showPopup = show_popup_wrapped  # type: ignore[method-assign]
    combo._sermon_popup_hooked = True


def apply_sermon_theme(widget, theme: str = "dark") -> None:
    """同步讲篇编辑器主题（与主应用 QSS 一致，含讲篇专属规则）。"""
    from ui.themes.stylesheet import build_stylesheet

    theme = theme or "dark"
    widget.setStyleSheet(build_stylesheet(theme))
    for combo in widget.findChildren(QComboBox):
        if isinstance(combo, SermonComboBox):
            combo.set_sermon_theme(theme)
        else:
            polish_sermon_combo(combo, theme)

"""讲篇编辑器主窗口（P0：多页 + 文本/图片/背景 + 保存打开）。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QBuffer, QIODevice, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import (
    Background,
    Element,
    ElementStyle,
    new_document,
    new_image_element,
    new_shape_element,
    new_slide,
    new_text_element,
    SermonDocument,
    Slide,
)
from core.sermon.store import (
    LEGACY_FILTER,
    PACKAGE_EXT,
    PACKAGE_FILTER,
    SermonStore,
    suggest_package_name,
)
from core.sermon.templates import TemplateStore

from .anim_panel import AnimPanel
from .canvas import SlideCanvas
from .property_panel import BackgroundPanel, PropertyPanel
from .slide_list import SlideListWidget
from .transition_panel import TransitionPanel
from ui.sermon.player.stage import SlideStage
from ui.sermon.styles import SermonComboBox, apply_sermon_theme


class SermonEditorWindow(QWidget):
    """主窗口中央全屏叠层编辑器（非独立顶层窗）。"""

    closed = pyqtSignal()

    def __init__(self, store: SermonStore | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonEditorWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        self.store = store or SermonStore()
        self.template_store = TemplateStore()
        self.doc: SermonDocument = new_document()
        self._package_path: Path | None = None
        self._slide_index = 0
        self._dirty = False
        self._saved_once = False
        self._presenting = False
        self._host_window = None
        self._clip_elements: list[Element] = []
        self._undo_stack: list[tuple] = []
        self._redo_stack: list[tuple] = []
        self._history_limit = 40
        self._restoring = False
        self._syncing_from_ctrl = False
        self._wheel_guard_ms = 0
        self._thumb_queue: list[int] = []
        self._last_text_style = ElementStyle()
        self._format_sticky = False
        self._format_ignore = False

        self._build_ui()
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setInterval(24)
        self._thumb_timer.timeout.connect(self._pump_thumbnails)
        self._build_menus()
        self._build_present_shortcuts()
        self._wrap_canvas_remove()
        self._load_document(self.doc, mark_clean=True)
        self.apply_theme(self._parent_theme())

    def _parent_theme(self) -> str:
        host = getattr(self, "_host_window", None)
        if host is not None and hasattr(host, "theme"):
            return str(getattr(host, "theme") or "dark")
        parent = self.parent()
        if parent is not None and hasattr(parent, "theme"):
            return str(getattr(parent, "theme") or "dark")
        return "dark"

    def apply_theme(self, theme: str = "dark"):
        apply_sermon_theme(self, theme)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "btn_format", None) and event.type() == QEvent.Type.MouseButtonDblClick:
            self._start_format_paint(sticky=True)
            return True
        return super().eventFilter(obj, event)

    def statusBar(self) -> QStatusBar:
        return self._status

    def menuBar(self) -> QMenuBar:
        return self._menu_bar

    def fit_to_parent(self):
        parent = self.parentWidget()
        if parent is None:
            return
        main = self._main_window()
        splitter = getattr(main, "main_splitter", None) if main is not None else None
        bar = getattr(main, "session_bar", None) if main is not None else None
        if splitter is not None and splitter.parentWidget() is parent:
            self.setGeometry(splitter.geometry())
        else:
            r = parent.rect()
            if bar is not None and bar.isVisible() and bar.parentWidget() is not None:
                top = bar.mapTo(parent, QPoint(0, 0))
                if 0 < top.y() < r.height():
                    r.setHeight(top.y())
                else:
                    h = max(bar.height(), bar.sizeHint().height())
                    r.setHeight(max(0, r.height() - h))
            self.setGeometry(r)
        self.raise_()
        if bar is not None and bar.isVisible():
            bar.raise_()

    def _build_ui(self):
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self._menu_bar = QMenuBar(self)
        shell.addWidget(self._menu_bar)

        toolbar = QToolBar("讲篇")
        toolbar.setMovable(False)
        toolbar.setObjectName("sermonToolBar")
        shell.addWidget(toolbar)

        self.title_label = QLabel("")
        self.title_label.setObjectName("sermonTitleLabel")
        toolbar.addWidget(self.title_label)
        toolbar.addSeparator()

        sec_canvas = QLabel("画布")
        sec_canvas.setObjectName("sermonToolSection")
        toolbar.addWidget(sec_canvas)
        self.aspect_combo = SermonComboBox()
        self.aspect_combo.addItem("16:9", "16:9")
        self.aspect_combo.addItem("4:3", "4:3")
        self.aspect_combo.setToolTip("画布比例")
        # 工具栏短下拉：不要 Expanding 抢宽度
        self.aspect_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.aspect_combo.setMinimumContentsLength(4)
        self.aspect_combo.setFixedWidth(78)
        self.aspect_combo.currentIndexChanged.connect(self._on_aspect)
        toolbar.addWidget(self.aspect_combo)
        toolbar.addSeparator()

        sec_insert = QLabel("插入")
        sec_insert.setObjectName("sermonToolSection")
        toolbar.addWidget(sec_insert)
        btn_text = QPushButton("文本")
        btn_text.setObjectName("sermonInsertTextBtn")
        btn_text.setCheckable(True)
        btn_text.setToolTip("点一下，再在画布上拖出文本框")
        btn_text.clicked.connect(self._toggle_draw_text)
        btn_image = QPushButton("图片")
        btn_image.setObjectName("sermonInsertImageBtn")
        btn_image.setToolTip("添加图片")
        btn_image.clicked.connect(self._add_image)
        btn_shape = QPushButton("形状")
        btn_shape.setObjectName("sermonInsertShapeBtn")
        btn_shape.setCheckable(True)
        btn_shape.setToolTip("点一下，再在画布上拖出形状")
        btn_shape.clicked.connect(self._toggle_draw_shape)
        btn_format = QPushButton("格式刷")
        btn_format.setObjectName("sermonFormatPaintBtn")
        btn_format.setCheckable(True)
        btn_format.setToolTip("先选中文本（含导入的），再点一次刷一个；双击可连续刷。Esc 取消")
        btn_format.clicked.connect(self._toggle_format_paint)
        btn_format.installEventFilter(self)
        toolbar.addWidget(btn_text)
        toolbar.addWidget(btn_image)
        toolbar.addWidget(btn_shape)
        toolbar.addWidget(btn_format)
        self.btn_text = btn_text
        self.btn_shape = btn_shape
        self.btn_format = btn_format
        toolbar.addSeparator()

        btn_save = QPushButton("保存")
        btn_save.setObjectName("sermonSaveBtn")
        btn_save.clicked.connect(self.save)
        toolbar.addWidget(btn_save)
        toolbar.addSeparator()

        sec_present = QLabel("放映")
        sec_present.setObjectName("sermonToolSection")
        toolbar.addWidget(sec_present)
        self.play_btn = QPushButton("开始放映")
        self.play_btn.setObjectName("sermonPlayBtn")
        self.play_btn.setToolTip("在扩展屏放映当前讲篇  F5")
        self.play_btn.clicked.connect(self.start_presentation)
        self.stop_btn = QPushButton("结束")
        self.stop_btn.setObjectName("sermonStopBtn")
        self.stop_btn.setToolTip("结束放映并淡回经文  Esc")
        self.stop_btn.clicked.connect(self.stop_presentation)
        self.stop_btn.setEnabled(False)
        toolbar.addWidget(self.play_btn)
        toolbar.addWidget(self.stop_btn)
        toolbar.addSeparator()

        btn_back = QPushButton("返回经文")
        btn_back.setObjectName("sermonBackBtn")
        btn_back.setToolTip("关闭讲篇编辑，回到经文界面")
        btn_back.clicked.connect(self.request_close)
        toolbar.addWidget(btn_back)
        for b in (
            btn_text,
            btn_image,
            btn_shape,
            btn_format,
            btn_save,
            self.play_btn,
            self.stop_btn,
            btn_back,
        ):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(32)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.slide_list = SlideListWidget()
        self.slide_list.slide_selected.connect(self._on_slide_selected)
        self.slide_list.add_requested.connect(self._add_slide)
        self.slide_list.delete_requested.connect(self._delete_slide)
        self.slide_list.duplicate_requested.connect(self._duplicate_slide)
        self.slide_list.slides_reordered.connect(self._on_slides_reordered)
        root.addWidget(self.slide_list)

        canvas_host = QWidget()
        canvas_host.setObjectName("sermonCanvasHost")
        canvas_layout = QVBoxLayout(canvas_host)
        canvas_layout.setContentsMargins(0, 0, 0, 8)
        canvas_layout.setSpacing(0)
        self.canvas_caption = QLabel("编辑画布 · 拖动元素调整位置")
        self.canvas_caption.setObjectName("sermonCanvasCaption")
        canvas_layout.addWidget(self.canvas_caption)

        self.canvas_stack = QStackedWidget()
        self.canvas = SlideCanvas()
        self.canvas.selection_changed.connect(self._on_canvas_selection)
        self.canvas.slide_modified.connect(self._on_slide_modified)
        self.canvas.rect_drawn.connect(self._on_rect_drawn)
        self.canvas.status_message.connect(self._on_canvas_status)
        self.canvas.format_paint_target.connect(self._on_format_paint_target)
        self.canvas_stack.addWidget(self.canvas)  # 0 = 编辑

        self.present_stage = SlideStage()
        self.present_stage.setObjectName("sermonPresentPreview")
        self.present_stage.page_step_requested.connect(self._on_present_stage_step)
        self.canvas_stack.addWidget(self.present_stage)  # 1 = 放映预览（跟副屏同画）
        canvas_layout.addWidget(self.canvas_stack, 1)
        root.addWidget(canvas_host, 1)

        right = QWidget()
        right.setObjectName("sermonSideRail")
        right.setFixedWidth(340)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.side_tabs = QTabWidget()
        self.side_tabs.setObjectName("sermonSideTabs")
        self.side_tabs.setDocumentMode(True)
        self.side_tabs.tabBar().setExpanding(True)

        self.bg_panel = BackgroundPanel()
        self.bg_panel.background_changed.connect(self._on_bg_changed)
        self.bg_panel.pick_bg_image.connect(self._pick_bg_image)
        self.bg_panel.clear_bg_image.connect(self._clear_bg_image)
        self.bg_panel.apply_to_all.connect(self._apply_bg_to_all)
        self.side_tabs.addTab(self.bg_panel, "背景")

        self.props = PropertyPanel()
        self.props.element_changed.connect(self._on_element_changed)
        self.props.layer_reorder.connect(self._on_layer_reorder)
        self.props.align_requested.connect(self._on_align_requested)
        self.props.distribute_requested.connect(self._on_distribute_requested)
        self.side_tabs.addTab(self.props, "属性")

        self.anim_panel = AnimPanel()
        self.anim_panel.changed.connect(self._on_anims_changed)
        self.side_tabs.addTab(self.anim_panel, "动画")

        self.transition_panel = TransitionPanel()
        self.transition_panel.changed.connect(self._on_transition_changed)
        self.side_tabs.addTab(self.transition_panel, "切换")
        right_layout.addWidget(self.side_tabs, 1)
        root.addWidget(right)

        shell.addWidget(body, 1)

        self._status = QStatusBar(self)
        self._status.setSizeGripEnabled(False)
        shell.addWidget(self._status)
        self._status.showMessage("就绪")

    def _build_menus(self):
        file_menu = self._menu_bar.addMenu("文件(&F)")
        act_new = QAction("新建", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self.new_document)
        act_open = QAction("打开…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.open_document)
        act_save = QAction("保存", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self.save)
        act_save_as = QAction("另存为…", self)
        act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(self.save_as)
        act_rename = QAction("重命名讲篇…", self)
        act_rename.triggered.connect(self._rename)
        act_close = QAction("返回经文", self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self.request_close)
        for a in (act_new, act_open, act_save, act_save_as, act_rename, act_close):
            file_menu.addAction(a)
        file_menu.addSeparator()
        act_tpl_save = QAction("另存为模板…", self)
        act_tpl_save.triggered.connect(self.save_as_template)
        act_tpl_new = QAction("从模板新建…", self)
        act_tpl_new.triggered.connect(self.new_from_template)
        act_tpl_manage = QAction("管理模板…", self)
        act_tpl_manage.triggered.connect(self.manage_templates)
        for a in (act_tpl_save, act_tpl_new, act_tpl_manage):
            file_menu.addAction(a)
        file_menu.addSeparator()
        act_pptx_in = QAction("导入 PPTX…", self)
        act_pptx_in.triggered.connect(self.import_pptx)
        act_pptx_out = QAction("导出 PPTX…", self)
        act_pptx_out.triggered.connect(self.export_pptx)
        file_menu.addAction(act_pptx_in)
        file_menu.addAction(act_pptx_out)

        edit_menu = self._menu_bar.addMenu("编辑(&E)")
        act_undo = QAction("撤销", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self._undo)
        act_redo = QAction("重做", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self._redo)
        act_cut = QAction("剪切", self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self._cut_selected)
        act_copy = QAction("复制", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self._copy_selected)
        act_paste = QAction("粘贴", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._paste_clipboard)
        act_del = QAction("删除选中元素", self)
        act_del.setShortcut(QKeySequence.StandardKey.Delete)
        act_del.triggered.connect(self._delete_selected)
        act_select_all = QAction("全选", self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(self._select_all)
        act_select_slides = QAction("全选幻灯片", self)
        act_select_slides.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_select_slides.triggered.connect(self._select_all_slides)
        for a in (act_undo, act_redo):
            edit_menu.addAction(a)
        edit_menu.addSeparator()
        for a in (act_cut, act_copy, act_paste, act_del, act_select_all, act_select_slides):
            edit_menu.addAction(a)

        present_menu = self._menu_bar.addMenu("放映(&P)")
        act_play = QAction("开始放映", self)
        act_play.setShortcut(QKeySequence(Qt.Key.Key_F5))
        act_play.triggered.connect(self.start_presentation)
        act_scripture = QAction("切到经文", self)
        act_scripture.triggered.connect(self._switch_to_scripture)
        act_stop = QAction("结束放映", self)
        act_stop.triggered.connect(self.stop_presentation)
        act_next = QAction("下一页", self)
        act_next.triggered.connect(self._present_next)
        act_prev = QAction("上一页", self)
        act_prev.triggered.connect(self._present_prev)
        for a in (act_play, act_scripture, act_stop, act_next, act_prev):
            present_menu.addAction(a)

    def _build_present_shortcuts(self):
        """放映专用快捷键：仅在放映中启用。空格/↓ 下一页，↑ 上一页。"""
        self._present_shortcuts = []
        bindings = [
            (Qt.Key.Key_Space, self._present_next),
            (Qt.Key.Key_Down, self._present_next),
            (Qt.Key.Key_Up, self._present_prev),
            (Qt.Key.Key_Right, self._present_next),
            (Qt.Key.Key_Left, self._present_prev),
        ]
        for key, slot in bindings:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.setEnabled(False)
            sc.activated.connect(slot)
            self._present_shortcuts.append(sc)

    def _wrap_canvas_remove(self):
        """画布 Del 删除前写入撤销栈。"""
        self._canvas_remove_raw = self.canvas.remove_selected

        def _wrapped():
            if self.canvas.selected_elements():
                self._push_history()
            self._canvas_remove_raw()

        self.canvas.remove_selected = _wrapped  # type: ignore[method-assign]

    def _focus_is_text_field(self) -> bool:
        w = QApplication.focusWidget()
        if isinstance(w, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return True
        scene = self.canvas.scene()
        focus = scene.focusItem() if scene is not None else None
        if focus is not None and hasattr(focus, "textInteractionFlags"):
            flags = focus.textInteractionFlags()
            if flags != Qt.TextInteractionFlag.NoTextInteraction:
                return True
        return False

    def _push_history(self, *, full: bool = False):
        if self._restoring:
            return
        try:
            self.canvas.commit_geometry()
        except Exception:
            pass
        self._undo_stack.append(self._capture_history(full=full))
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _capture_history(self, *, full: bool = False) -> tuple:
        idx = int(self._slide_index)
        if full:
            return ("doc", self.doc.to_dict(), idx)
        slide = self._current_slide()
        if slide is None:
            return ("doc", self.doc.to_dict(), idx)
        return ("slide", idx, slide.to_dict())

    def _capture_like(self, snap: tuple) -> tuple:
        if snap and snap[0] == "slide":
            idx = int(snap[1])
            idx = max(0, min(idx, len(self.doc.slides) - 1)) if self.doc.slides else 0
            if self.doc.slides:
                return ("slide", idx, self.doc.slides[idx].to_dict())
        return ("doc", self.doc.to_dict(), int(self._slide_index))

    def _restore_snapshot(self, snap: tuple):
        self._restoring = True
        try:
            kind = snap[0] if snap else "doc"
            if kind == "slide":
                _, idx, slide_data = snap
                idx = max(0, min(int(idx), len(self.doc.slides) - 1))
                if self.doc.slides:
                    self.doc.slides[idx] = Slide.from_dict(slide_data)
                self._slide_index = idx
                self.slide_list.refresh(self._slide_index)
                self._show_slide(self._slide_index)
            else:
                data, idx = snap[1], snap[2]
                doc_id = self.doc.id
                self.doc = SermonDocument.from_dict(data)
                self.doc.id = doc_id
                self._slide_index = max(0, min(int(idx), len(self.doc.slides) - 1))
                self.slide_list.set_document(self.doc, self._slide_index)
                self._show_slide(self._slide_index)
                QTimer.singleShot(0, self._refresh_all_thumbnails)
            self._set_dirty(True)
            self._push_hot_update()
        finally:
            self._restoring = False

    def _undo(self):
        if self._focus_is_text_field():
            return
        if not self._undo_stack:
            self.statusBar().showMessage("没有可撤销的操作", 2000)
            return
        try:
            self.canvas.commit_geometry()
        except Exception:
            pass
        snap = self._undo_stack.pop()
        self._redo_stack.append(self._capture_like(snap))
        self._restore_snapshot(snap)
        self.statusBar().showMessage("已撤销", 2000)

    def _redo(self):
        if self._focus_is_text_field():
            return
        if not self._redo_stack:
            self.statusBar().showMessage("没有可重做的操作", 2000)
            return
        try:
            self.canvas.commit_geometry()
        except Exception:
            pass
        snap = self._redo_stack.pop()
        self._undo_stack.append(self._capture_like(snap))
        self._restore_snapshot(snap)
        self.statusBar().showMessage("已重做", 2000)

    def _copy_selected(self):
        if self._focus_is_text_field():
            return
        els = self.canvas.selected_elements()
        if not els:
            return
        self._clip_elements = [e.clone() for e in els]
        self.statusBar().showMessage(f"已复制 {len(els)} 个图层", 2000)

    def _cut_selected(self):
        if self._focus_is_text_field():
            return
        els = self.canvas.selected_elements()
        if not els:
            return
        self._push_history()
        self._clip_elements = [e.clone() for e in els]
        self._canvas_remove_raw()
        self.statusBar().showMessage(f"已剪切 {len(els)} 个图层", 2000)

    def _paste_clipboard(self):
        if self._focus_is_text_field():
            return
        if not self._clip_elements:
            return
        slide = self._current_slide()
        if slide is None:
            return
        self._push_history()
        self.canvas.commit_geometry()
        pasted_ids: set[str] = set()
        for src in self._clip_elements:
            el = src.clone()
            el.x = float(src.x) + 24
            el.y = float(src.y) + 24
            el.z = len(slide.elements)
            slide.elements.append(el)
            pasted_ids.add(el.id)
            src.x = el.x
            src.y = el.y
        self.canvas.load_slide(self.doc, slide)
        for item in self.canvas._scene.items():
            eid = getattr(item, "element_id", None)
            item.setSelected(eid in pasted_ids)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()
        self.statusBar().showMessage(f"已粘贴 {len(pasted_ids)} 个图层", 2000)

    def _slide_list_has_focus(self) -> bool:
        w = QApplication.focusWidget()
        if w is None:
            return False
        return w is self.slide_list or self.slide_list.isAncestorOf(w)

    def _delete_selected(self):
        if self._focus_is_text_field():
            return
        if self._slide_list_has_focus():
            self._delete_slide()
            return
        if not self.canvas.selected_elements():
            return
        self._push_history()
        self._canvas_remove_raw()

    def _select_all(self):
        if self._focus_is_text_field():
            w = QApplication.focusWidget()
            if isinstance(w, (QLineEdit, QTextEdit)):
                w.selectAll()
                return
            scene = self.canvas.scene()
            focus = scene.focusItem() if scene is not None else None
            if focus is not None and hasattr(focus, "textCursor"):
                from PyQt6.QtGui import QTextCursor

                cursor = focus.textCursor()
                cursor.select(QTextCursor.SelectionType.Document)
                focus.setTextCursor(cursor)
            return
        if self._slide_list_has_focus():
            self.slide_list.select_all_slides()
            n = len(self.slide_list.selected_indexes())
            if n:
                self.statusBar().showMessage(f"已全选 {n} 页幻灯片", 2000)
            return
        self.canvas.select_all()
        els = self.canvas.selected_elements()
        if els:
            self.statusBar().showMessage(f"已全选 {len(els)} 个图层", 2000)

    def _select_all_slides(self):
        self.slide_list.select_all_slides()
        n = len(self.slide_list.selected_indexes())
        if n:
            self.statusBar().showMessage(f"已全选 {n} 页幻灯片", 2000)

    def _set_present_shortcuts_enabled(self, enabled: bool):
        for sc in getattr(self, "_present_shortcuts", []):
            sc.setEnabled(enabled)

    def _main_window(self):
        host = getattr(self, "_host_window", None)
        if host is not None and hasattr(host, "start_sermon_presentation"):
            return host
        w = self.parent()
        while w is not None:
            if hasattr(w, "start_sermon_presentation"):
                return w
            w = w.parent()
        return None

    def start_presentation(self):
        main = self._main_window()
        if main is None:
            QMessageBox.warning(self, "放映", "无法连接到主窗口。")
            return
        self.canvas.commit_geometry()
        # 确保资源目录存在
        self.store.sermon_dir(self.doc.id).mkdir(parents=True, exist_ok=True)
        ok = main.start_sermon_presentation(
            self.doc,
            self._slide_index,
            self.store.sermon_dir(self.doc.id),
        )
        if not ok:
            QMessageBox.information(self, "放映", "无法打开扩展显示，请检查屏幕设置。")
            return
        self._presenting = True
        self._thumb_timer.stop()
        self._set_present_shortcuts_enabled(True)
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._enter_present_preview()
        self.fit_to_parent()
        self.show()
        self.raise_()
        main2 = self._main_window()
        if main2 is not None and hasattr(main2, "_update_session_chrome"):
            main2._update_session_chrome()

    def _switch_to_scripture(self):
        main = self._main_window()
        if main is not None:
            main.show_scripture_channel()
            self.statusBar().showMessage("已切到经文（讲篇进度保留）", 4000)

    def stop_presentation(self):
        main = self._main_window()
        if main is not None:
            main.stop_sermon_presentation()
        else:
            self.on_presentation_stopped()

    def on_presentation_stopped(self, *, reshow: bool = True):
        self._presenting = False
        self._set_present_shortcuts_enabled(False)
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.anim_panel.set_play_cursor(-1)
        self._exit_present_preview()
        self.statusBar().showMessage("放映已结束", 3000)
        if self.doc.slides:
            self._show_slide(self._slide_index)
        if getattr(self, "_suppress_reshow", False):
            return
        if not reshow:
            return
        self.fit_to_parent()
        self.show()
        self.raise_()
        host = self._main_window()
        btn = getattr(host, "sermon_button", None) if host is not None else None
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)

    def on_presentation_status(self, text: str):
        return

    def _enter_present_preview(self):
        """放映中：中间区换成与副屏同画的只读舞台。"""
        root = self.store.sermon_dir(self.doc.id)
        self.present_stage.set_assets_root(root)
        self.canvas_stack.setCurrentIndex(1)
        self.canvas_caption.setText("放映预览 · 与观众同画（空格步进 / 滚轮翻页）")
        # 动画列表更直观
        anim_idx = self.side_tabs.indexOf(self.anim_panel)
        if anim_idx >= 0:
            self.side_tabs.setCurrentIndex(anim_idx)
        main = self._main_window()
        if main is not None and main.sermon_controller.active:
            ctrl = main.sermon_controller
            self.mirror_present_slide(
                ctrl.doc,
                ctrl.index,
                ctrl.assets_root,
                prepare_anims=True,
                anim_cursor=ctrl.anim_cursor,
            )
        else:
            self.mirror_present_slide(
                self.doc,
                self._slide_index,
                root,
                prepare_anims=True,
                anim_cursor=0,
            )

    def _exit_present_preview(self):
        self.present_stage.stop_animations(apply_end=False)
        self.present_stage.clear_stage()
        self.canvas_stack.setCurrentIndex(0)
        self.canvas_caption.setText("编辑画布 · 拖动元素调整位置")

    def _on_present_stage_step(self, delta: int):
        if not self._presenting:
            return
        if delta < 0:
            self._present_prev()
        else:
            self._present_next()

    def mirror_present_slide(
        self,
        doc,
        index: int,
        assets_root=None,
        *,
        prepare_anims: bool = True,
        anim_cursor: int = 0,
        pending_reveal: bool = False,
    ):
        """跟副屏同步一页（不含换页过渡，入场跟控制器）。"""
        if doc is None or not doc.slides:
            return
        if index < 0 or index >= len(doc.slides):
            return
        if self.canvas_stack.currentIndex() != 1:
            if not self._presenting:
                return
            self.canvas_stack.setCurrentIndex(1)
            self.canvas_caption.setText("放映预览 · 与观众同画（空格步进 / 滚轮翻页）")
        root = Path(assets_root) if assets_root else self.store.sermon_dir(doc.id)
        self.present_stage.set_assets_root(root)
        slide = doc.slides[index]
        if pending_reveal:
            self.present_stage.show_slide(doc, slide, prepare_anims=False)
            self.present_stage.reveal_all()
        else:
            self.present_stage.show_slide(doc, slide, prepare_anims=prepare_anims)
            played = slide.sorted_animations()[: max(0, int(anim_cursor))]
            if played:
                self.present_stage.apply_played_steps(played)
        self._slide_index = index
        self.slide_list.list.blockSignals(True)
        self.slide_list.list.setCurrentRow(index)
        self.slide_list.list.blockSignals(False)
        self.anim_panel.set_slide(slide)
        self._update_present_status(doc, index, anim_cursor)

    def mirror_present_steps(self, steps, anim_cursor: int | None = None):
        """主屏预览跟步进：先更新进度文字，动画延后一帧，避免和副屏抢线程。"""
        if not self._presenting:
            return
        batch = list(steps or [])
        main = self._main_window()
        cur = int(anim_cursor if anim_cursor is not None else 0)
        if main is not None and main.sermon_controller.active:
            ctrl = main.sermon_controller
            cur = int(anim_cursor if anim_cursor is not None else ctrl.anim_cursor)
            self.anim_panel.set_play_cursor(cur)
            if ctrl.doc is not None:
                self._update_present_status(ctrl.doc, ctrl.index, cur)
        if batch:
            # 副屏播完整动画；主屏预览只落到终态，避免两套动画抢线程
            QTimer.singleShot(40, lambda b=list(batch): self._play_preview_steps(b))

    def _play_preview_steps(self, batch: list):
        if not self._presenting or self.canvas_stack.currentIndex() != 1:
            return
        self.present_stage.apply_played_steps(batch)

    def mirror_present_reveal(self):
        if self._presenting:
            self.present_stage.reveal_all()

    def _update_present_status(self, doc, index: int, anim_cursor: int):
        if doc is None or not doc.slides:
            return
        if index < 0 or index >= len(doc.slides):
            return
        self.anim_panel.set_play_cursor(max(0, int(anim_cursor)))

    def _present_next(self):
        if not self._presenting:
            return
        if self._focus_is_text_field():
            return
        main = self._main_window()
        if main is None:
            return
        if getattr(main, "_projection_channel", "sermon") != "sermon":
            if hasattr(main, "show_sermon_channel"):
                main.show_sermon_channel()
            return
        main.sermon_controller.advance()
        self.sync_from_controller()

    def _present_prev(self):
        if not self._presenting:
            return
        if self._focus_is_text_field():
            return
        main = self._main_window()
        if main is None:
            return
        if getattr(main, "_projection_channel", "sermon") != "sermon":
            if hasattr(main, "show_sermon_channel"):
                main.show_sermon_channel()
            return
        main.sermon_controller.prev_slide()
        self.sync_from_controller()

    def sync_from_controller(self, *, rebuild_canvas: bool = False):
        """放映同步：侧栏跟页；中间预览舞台由 mirror_* 驱动。"""
        main = self._main_window()
        if main is None or not main.sermon_controller.active:
            return
        ctrl = main.sermon_controller
        idx = ctrl.index
        page_changed = idx != self._slide_index
        if page_changed:
            self._syncing_from_ctrl = True
            try:
                self.slide_list.list.blockSignals(True)
                self._slide_index = max(0, min(idx, len(self.doc.slides) - 1))
                self.slide_list.list.setCurrentRow(self._slide_index)
                if self.isVisible() and 0 <= self._slide_index < len(self.doc.slides):
                    slide = self.doc.slides[self._slide_index]
                    self.anim_panel.set_slide(slide)
                    self.transition_panel.set_slide(slide)
                    self.bg_panel.set_slide(slide)
                    if rebuild_canvas or not self._presenting:
                        self._show_slide(self._slide_index)
            finally:
                self.slide_list.list.blockSignals(False)
                self._syncing_from_ctrl = False
        if self.isVisible():
            self.anim_panel.set_play_cursor(int(ctrl.anim_cursor))
        if self._presenting and ctrl.doc is not None:
            if self.canvas_stack.currentIndex() != 1:
                self._enter_present_preview()

    def _on_transition_changed(self):
        self._set_dirty(True)

    def _sync_editor_to_controller(self):
        self.sync_from_controller()

    def wheelEvent(self, event):
        if self._focus_is_text_field():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return
        from PyQt6.QtCore import QDateTime

        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._wheel_guard_ms < 180:
            event.accept()
            return
        self._wheel_guard_ms = now
        self._wheel_change_slide(delta)
        event.accept()

    def _wheel_change_slide(self, delta: int):
        if self._presenting:
            if delta < 0:
                self._present_next()
            else:
                self._present_prev()
            return
        if not self.doc.slides:
            return
        nxt = self._slide_index + (1 if delta < 0 else -1)
        if nxt < 0 or nxt >= len(self.doc.slides):
            return
        self._show_slide(nxt)
        self.slide_list.list.blockSignals(True)
        self.slide_list.list.setCurrentRow(nxt)
        self.slide_list.list.blockSignals(False)

    def _push_hot_update(self):
        if not self._presenting or self._syncing_from_ctrl:
            return
        main = self._main_window()
        if main is None:
            return
        self.canvas.commit_geometry()
        main.sermon_presentation_hot_update(
            self.doc,
            self._slide_index,
            self.store.sermon_dir(self.doc.id),
        )

    # —— 文档生命周期 ——

    def _load_document(
        self,
        doc: SermonDocument,
        mark_clean: bool = False,
        package_path: Path | str | None = None,
    ):
        self.doc = doc
        self._slide_index = 0
        self._undo_stack.clear()
        self._redo_stack.clear()
        if package_path is not None:
            self._package_path = Path(package_path)
        else:
            self._package_path = None
        self._saved_once = bool(self._package_path and self._package_path.is_file())
        self.store.sermon_dir(doc.id).mkdir(parents=True, exist_ok=True)
        self.canvas.set_assets_root(self.store.sermon_dir(doc.id))
        idx = self.aspect_combo.findData(doc.aspect)
        self.aspect_combo.blockSignals(True)
        if idx >= 0:
            self.aspect_combo.setCurrentIndex(idx)
        self.aspect_combo.blockSignals(False)
        self.slide_list.set_document(doc, 0)
        self._show_slide(0)
        self._set_dirty(False if mark_clean else self._dirty)
        if mark_clean:
            self._set_dirty(False)
        self._update_title()
        # 导入/打开后稍晚刷缩略图，避免场景未布局时全是灰块
        QTimer.singleShot(80, self._refresh_all_thumbnails)
        QTimer.singleShot(280, self._refresh_all_thumbnails)

    def save_as_template(self):
        self.canvas.commit_geometry()
        title, ok = QInputDialog.getText(
            self, "另存为模板", "模板名称：", text=self.doc.title or "未命名模板"
        )
        if not ok:
            return
        pix = self.canvas.render_thumbnail(320)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pix.toImage().save(buf, "PNG")
        thumb_bytes = bytes(buf.data())
        try:
            tpl_id = self.template_store.save_from_document(
                self.doc,
                title=title.strip() or "未命名模板",
                source_assets=self.store.sermon_dir(self.doc.id),
                thumb_png=thumb_bytes,
            )
        except OSError as exc:
            QMessageBox.warning(self, "保存模板失败", str(exc))
            return
        self.statusBar().showMessage(f"已保存模板：{tpl_id}", 4000)

    def new_from_template(self):
        if not self._confirm_discard():
            return
        items = self.template_store.list_templates()
        if not items:
            QMessageBox.information(self, "模板", "还没有模板，请先「另存为模板」。")
            return
        labels = [f"{it['title']}  ({it['id']})" for it in items]
        label, ok = QInputDialog.getItem(self, "从模板新建", "选择模板：", labels, 0, False)
        if not ok or not label:
            return
        tpl = items[labels.index(label)]
        doc = self.template_store.instantiate(tpl["id"])
        self.store.save(doc)
        self.template_store.copy_assets_to(tpl["id"], self.store.assets_dir(doc.id))
        self._load_document(doc, mark_clean=True, package_path=None)
        self.statusBar().showMessage("已从模板新建讲篇（请保存为 .sermon）", 3000)

    def manage_templates(self):
        items = self.template_store.list_templates()
        if not items:
            QMessageBox.information(self, "模板", "暂无模板。")
            return
        labels = [f"{it['title']}  ({it['id']})" for it in items]
        label, ok = QInputDialog.getItem(
            self, "管理模板", "选择要删除的模板：", labels, 0, False
        )
        if not ok or not label:
            return
        tpl = items[labels.index(label)]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("删除模板")
        box.setText(f"确定删除模板「{tpl['title']}」？")
        yes_btn = box.addButton("是", QMessageBox.ButtonRole.YesRole)
        box.addButton("否", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return
        self.template_store.delete(tpl["id"])
        self.statusBar().showMessage("模板已删除", 3000)

    def import_pptx(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 PPTX", "", "PPTX 文件 (*.pptx)"
        )
        if not path:
            return
        try:
            from core.sermon.pptx_io import import_pptx
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        try:
            doc = import_pptx(path, self.store)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._load_document(doc, mark_clean=True, package_path=None)
        self.statusBar().showMessage(f"已导入 {len(doc.slides)} 页（请保存为 .sermon）", 4000)

    def export_pptx(self):
        self.canvas.commit_geometry()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 PPTX",
            f"{self.doc.title or '讲篇'}.pptx",
            "PPTX 文件 (*.pptx)",
        )
        if not path:
            return
        try:
            from core.sermon.pptx_io import export_pptx

            dest = export_pptx(self.doc, path, self.store)
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self.statusBar().showMessage(f"已导出：{dest}", 4000)

    def new_document(self):
        if not self._confirm_discard():
            return
        title, ok = QInputDialog.getText(self, "新建讲篇", "标题：", text="未命名讲篇")
        if not ok:
            return
        doc = new_document(title=title.strip() or "未命名讲篇")
        # 仅建工作目录；真正落盘等用户「保存」选路径
        self.store.save(doc)
        self._load_document(doc, mark_clean=True, package_path=None)
        self.statusBar().showMessage("已新建讲篇（尚未保存为 .sermon）", 3000)

    def open_document(self):
        if not self._confirm_discard():
            return
        start_dir = str(
            self._package_path.parent
            if self._package_path is not None
            else self.store.default_save_dir()
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开讲篇",
            start_dir,
            f"{PACKAGE_FILTER};;{LEGACY_FILTER};;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            opened = Path(path)
            if opened.suffix.lower() == PACKAGE_EXT:
                doc = self.store.load_package(opened)
                self._load_document(doc, mark_clean=True, package_path=opened)
            else:
                doc = self.store.load_path(opened)
                self.store.save(doc)
                self._load_document(doc, mark_clean=True, package_path=None)
            self.statusBar().showMessage(f"已打开：{opened.name}", 4000)
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def save(self) -> bool:
        self.canvas.commit_geometry()
        if self._package_path is None:
            return self.save_as()
        return self._write_package(self._package_path)

    def save_as(self) -> bool:
        self.canvas.commit_geometry()
        default_name = suggest_package_name(self.doc.title) + PACKAGE_EXT
        start_dir = (
            self._package_path.parent
            if self._package_path is not None
            else self.store.default_save_dir()
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存讲篇",
            str(start_dir / default_name),
            PACKAGE_FILTER,
        )
        if not path:
            return False
        dest = Path(path)
        if dest.suffix.lower() != PACKAGE_EXT:
            dest = dest.with_suffix(PACKAGE_EXT)
        # 用文件名作为讲篇标题（对话框里可改名）
        stem = dest.stem.strip()
        if stem:
            self.doc.title = stem
            self._update_title()
        return self._write_package(dest)

    def _write_package(self, package_path: Path) -> bool:
        try:
            saved = self.store.save_package(self.doc, package_path)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self._package_path = saved
        self._saved_once = True
        self._set_dirty(False)
        self.statusBar().showMessage(f"已保存：{saved}", 5000)
        return True

    def _rename(self):
        title, ok = QInputDialog.getText(self, "重命名", "标题：", text=self.doc.title)
        if not ok:
            return
        new_title = title.strip() or self.doc.title
        if new_title == self.doc.title:
            return
        self.doc.title = new_title
        self._set_dirty(True)
        self._update_title()
        # 若已绑定 .sermon，提示可用「另存为」改文件名
        if self._package_path is not None:
            self.statusBar().showMessage(
                "标题已改；若要改文件名请用「另存为…」", 4000
            )

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("未保存的更改")
        box.setText("是否保存当前讲篇？")
        save_btn = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn:
            return False
        if clicked is save_btn:
            return self.save()
        return True

    def stash_and_hide(self) -> bool:
        """叠层收起：保留未保存更改；若在放映则继续投屏，不结束会话。"""
        try:
            self.canvas.commit_geometry()
        except Exception:
            pass
        if self._presenting:
            self._push_hot_update()
            # 叠层收起后由主窗口快捷键接管翻页
            self._set_present_shortcuts_enabled(False)
            main = self._main_window()
            if main is not None and hasattr(main, "_update_session_chrome"):
                main._update_session_chrome()
        self.hide()
        self.closed.emit()
        return True

    def request_close(self) -> bool:
        """关闭叠层回到经文（暂存，不问保存）。"""
        return self.stash_and_hide()

    def confirm_close_app(self) -> bool:
        """彻底退出程序时才询问未保存更改。"""
        if self._presenting:
            self._suppress_reshow = True
            try:
                self.stop_presentation()
            finally:
                self._suppress_reshow = False
        return self._confirm_discard()

    def closeEvent(self, event):
        if self.request_close():
            event.accept()
        else:
            event.ignore()

    def _set_dirty(self, dirty: bool):
        self._dirty = dirty
        self._update_title()

    def _update_title(self):
        mark = " *" if self._dirty else ""
        self.title_label.setText(f"  {self.doc.title}{mark}  ")
        if self._package_path is not None:
            self.setWindowTitle(f"{self.doc.title}{mark} — {self._package_path.name}")
        else:
            self.setWindowTitle(f"{self.doc.title}{mark}")

    # —— 幻灯片 ——

    def _current_slide(self):
        if not self.doc.slides:
            return None
        self._slide_index = max(0, min(self._slide_index, len(self.doc.slides) - 1))
        return self.doc.slides[self._slide_index]

    def _show_slide(self, index: int):
        if not self.doc.slides:
            return
        self.canvas.commit_geometry()
        self._slide_index = max(0, min(index, len(self.doc.slides) - 1))
        slide = self.doc.slides[self._slide_index]
        self.canvas.load_slide(self.doc, slide)
        self.bg_panel.set_slide(slide)
        self.props.set_selection([])
        self.anim_panel.set_slide(slide)
        self.anim_panel.set_selected_element(None)
        self.transition_panel.set_slide(slide)
        QTimer.singleShot(0, self._refresh_thumbnail)
        if self._presenting and not self._syncing_from_ctrl:
            main = self._main_window()
            if main is not None:
                main.sermon_presentation_go_to(self._slide_index)

    def _on_slide_selected(self, index: int):
        keep_list = self._slide_list_has_focus()
        if index != self._slide_index:
            self._show_slide(index)
        if keep_list:
            self.slide_list.list.setFocus(Qt.FocusReason.OtherFocusReason)

    def _add_slide(self):
        self._push_history(full=True)
        self.canvas.commit_geometry()
        cur = self._current_slide()
        bg = cur.background if cur is not None else None
        self.doc.slides.append(new_slide(background=bg))
        self._slide_index = len(self.doc.slides) - 1
        self.slide_list.refresh(self._slide_index)
        self._show_slide(self._slide_index)
        self._set_dirty(True)
        self._push_hot_update()

    def _delete_slide(self):
        idxs = self.slide_list.selected_indexes()
        if not idxs:
            idxs = [self._slide_index]
        if len(self.doc.slides) - len(idxs) < 1:
            QMessageBox.information(self, "提示", "至少保留一页幻灯片。")
            return
        self._push_history(full=True)
        for i in reversed(idxs):
            del self.doc.slides[i]
        self._slide_index = min(idxs[0], len(self.doc.slides) - 1)
        self.slide_list.refresh(self._slide_index)
        self._show_slide(self._slide_index)
        self._set_dirty(True)
        self._push_hot_update()

    def _duplicate_slide(self):
        idxs = self.slide_list.selected_indexes()
        if not idxs:
            idxs = [self._slide_index]
        self._push_history(full=True)
        self.canvas.commit_geometry()
        clones = [self.doc.slides[i].clone() for i in idxs if 0 <= i < len(self.doc.slides)]
        if not clones:
            return
        insert_at = idxs[-1] + 1
        for i, clone in enumerate(clones):
            self.doc.slides.insert(insert_at + i, clone)
        self._slide_index = insert_at + len(clones) - 1
        self.slide_list.refresh(self._slide_index)
        self._show_slide(self._slide_index)
        self._set_dirty(True)
        self._push_hot_update()

    def _on_slides_reordered(self, ids: list):
        if self._restoring or not ids:
            return
        by_id = {s.id: s for s in self.doc.slides}
        if set(ids) != set(by_id):
            self.slide_list.refresh(self._slide_index)
            return
        new_slides = [by_id[i] for i in ids]
        if [s.id for s in new_slides] == [s.id for s in self.doc.slides]:
            return
        self._push_history(full=True)
        current_id = self.doc.slides[self._slide_index].id if self.doc.slides else None
        self.doc.slides = new_slides
        if current_id:
            for i, s in enumerate(new_slides):
                if s.id == current_id:
                    self._slide_index = i
                    break
        self.slide_list.refresh(self._slide_index)
        self._set_dirty(True)
        self._push_hot_update()

    def _refresh_thumbnail(self):
        pix = self.canvas.render_thumbnail(168 * 2)
        self.slide_list.update_thumbnail(self._slide_index, pix)

    def _refresh_all_thumbnails(self):
        if self._presenting:
            self._thumb_timer.stop()
            return
        if self.doc is None or not self.doc.slides:
            self._thumb_queue = []
            self._thumb_timer.stop()
            return
        seen = set()
        ordered: list[int] = []
        for i in self.slide_list.visible_indexes() + list(range(len(self.doc.slides))):
            if 0 <= i < len(self.doc.slides) and i not in seen:
                seen.add(i)
                ordered.append(i)
        self._thumb_queue = ordered
        if not self._thumb_timer.isActive():
            self._thumb_timer.start()

    def _pump_thumbnails(self):
        if self._presenting or self.doc is None or not self._thumb_queue:
            self._thumb_timer.stop()
            if self._presenting:
                return
            self._thumb_queue = []
            return
        i = self._thumb_queue.pop(0)
        if 0 <= i < len(self.doc.slides):
            if i == self._slide_index:
                pix = self.canvas.render_thumbnail(168 * 2)
            else:
                pix = self.canvas.render_slide_thumbnail(
                    self.doc, self.doc.slides[i], 168 * 2
                )
            self.slide_list.update_thumbnail(i, pix)
        if not self._thumb_queue:
            self._thumb_timer.stop()

    # —— 元素 / 背景 ——

    def _toggle_draw_text(self):
        if self._presenting:
            self.btn_text.setChecked(False)
            return
        if not self.btn_text.isChecked():
            if self.canvas.is_drawing():
                self.canvas.cancel_draw()
            self.statusBar().showMessage("已取消画文本框", 2000)
            return
        self._end_format_paint(None)
        self.btn_shape.blockSignals(True)
        self.btn_shape.setChecked(False)
        self.btn_shape.blockSignals(False)
        self.canvas.begin_draw("text")
        self.canvas_stack.setCurrentIndex(0)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _toggle_draw_shape(self):
        if self._presenting:
            self.btn_shape.setChecked(False)
            return
        if not self.btn_shape.isChecked():
            if self.canvas.is_drawing():
                self.canvas.cancel_draw()
            self.statusBar().showMessage("已取消画形状", 2000)
            return
        self._end_format_paint(None)
        self.btn_text.blockSignals(True)
        self.btn_text.setChecked(False)
        self.btn_text.blockSignals(False)
        self.canvas.begin_draw("shape")
        self.canvas_stack.setCurrentIndex(0)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_canvas_status(self, text: str):
        self.statusBar().showMessage(text, 4000)
        if not self.canvas.is_drawing():
            self.btn_text.blockSignals(True)
            self.btn_shape.blockSignals(True)
            self.btn_text.setChecked(False)
            self.btn_shape.setChecked(False)
            self.btn_text.blockSignals(False)
            self.btn_shape.blockSignals(False)

    def _on_rect_drawn(self, kind: str, x: float, y: float, w: float, h: float):
        self.btn_text.blockSignals(True)
        self.btn_shape.blockSignals(True)
        self.btn_text.setChecked(False)
        self.btn_shape.setChecked(False)
        self.btn_text.blockSignals(False)
        self.btn_shape.blockSignals(False)
        self._push_history()
        cw, ch = self.doc.canvas_size()
        if kind == "text":
            el = new_text_element(
                "在此输入",
                canvas_w=cw,
                canvas_h=ch,
                style=self._last_text_style,
            )
            el.x, el.y, el.w, el.h = x, y, w, h
            self.canvas.add_element(el)
            eid = el.id
            QTimer.singleShot(0, lambda i=eid: self._begin_edit_text(i))
            self.statusBar().showMessage("已创建文本框，直接输入文字", 3000)
        else:
            el = new_shape_element(canvas_w=cw, canvas_h=ch)
            el.x, el.y, el.w, el.h = x, y, w, h
            self.canvas.add_element(el)
            self.statusBar().showMessage("已创建形状", 2000)

    def _begin_edit_text(self, element_id: str):
        item = self.canvas._items.get(element_id)
        if item is None or not hasattr(item, "setTextInteractionFlags"):
            return
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        item.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(item, "_place_cursor_for_edit"):
            item._place_cursor_for_edit()

    def _add_text(self):
        """兼容入口：进入拖拽画框。"""
        if self._presenting:
            return
        self._end_format_paint(None)
        self.btn_text.blockSignals(True)
        self.btn_text.setChecked(True)
        self.btn_text.blockSignals(False)
        self.btn_shape.blockSignals(True)
        self.btn_shape.setChecked(False)
        self.btn_shape.blockSignals(False)
        self.canvas.begin_draw("text")
        self.canvas_stack.setCurrentIndex(0)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _add_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp *.gif)",
        )
        if not path:
            return
        try:
            # 确保目录存在后再导入
            self.store.sermon_dir(self.doc.id).mkdir(parents=True, exist_ok=True)
            rel = self.store.import_asset(self.doc.id, path)
        except OSError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._push_history()
        el = new_image_element(rel)
        self.canvas.add_element(el)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _add_shape(self):
        """兼容入口：进入拖拽画形状。"""
        if self._presenting:
            return
        self._end_format_paint(None)
        self.btn_shape.blockSignals(True)
        self.btn_shape.setChecked(True)
        self.btn_shape.blockSignals(False)
        self.btn_text.blockSignals(True)
        self.btn_text.setChecked(False)
        self.btn_text.blockSignals(False)
        self.canvas.begin_draw("shape")
        self.canvas_stack.setCurrentIndex(0)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "背景图片",
            "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp *.gif)",
        )
        if not path:
            return
        slide = self._current_slide()
        if slide is None:
            return
        try:
            self.store.sermon_dir(self.doc.id).mkdir(parents=True, exist_ok=True)
            rel = self.store.import_asset(self.doc.id, path)
        except OSError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        slide.background = Background(type="image", value=rel, fit=slide.background.fit)
        self.canvas.refresh_background()
        self.bg_panel.set_slide(slide)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _clear_bg_image(self):
        slide = self._current_slide()
        if slide is None:
            return
        color = "#1A1A2E"
        if slide.background.type == "color":
            color = slide.background.value
        slide.background = Background(type="color", value=color, fit=slide.background.fit)
        self.canvas.refresh_background()
        self.bg_panel.set_slide(slide)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _on_bg_changed(self):
        self.canvas.refresh_background()
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _apply_bg_to_all(self):
        slide = self._current_slide()
        if slide is None or not self.doc.slides:
            return
        self._push_history(full=True)
        src = slide.background.clone()
        for s in self.doc.slides:
            s.background = src.clone()
        self.canvas.refresh_background()
        self._set_dirty(True)
        self._refresh_all_thumbnails()
        self._push_hot_update()
        self.statusBar().showMessage("已将当前背景应用到全部幻灯片，之后仍可单页修改", 4000)

    def _app_config(self):
        host = self._main_window()
        return getattr(host, "config", None) if host is not None else None

    def reload_last_text_style(self):
        cfg = self._app_config()
        if cfg is None:
            return
        self._last_text_style = cfg.load_sermon_text_style()

    def _remember_text_style(self, element):
        if element is None or getattr(element, "type", None) != "text":
            return
        self._last_text_style = element.style.clone()
        cfg = self._app_config()
        if cfg is not None:
            cfg.save_sermon_text_style(self._last_text_style)

    def _toggle_format_paint(self, checked: bool = False):
        if self._format_ignore:
            return
        if self._presenting:
            self.btn_format.setChecked(False)
            return
        if not self.btn_format.isChecked():
            self._end_format_paint()
            return
        self._start_format_paint(sticky=False)

    def _start_format_paint(self, *, sticky: bool):
        if self._presenting:
            self._end_format_paint()
            return
        src = None
        for el in self.canvas.selected_elements():
            if el.type == "text":
                src = el
                break
        if src is None:
            self._format_ignore = True
            self.btn_format.setChecked(False)
            self._format_ignore = False
            self.statusBar().showMessage("请先选中一个文本框（导入的也可以），再点格式刷", 4000)
            return
        self._remember_text_style(src)
        self._format_sticky = sticky
        self._format_ignore = True
        self.btn_format.setChecked(True)
        self._format_ignore = False
        self.btn_text.blockSignals(True)
        self.btn_shape.blockSignals(True)
        self.btn_text.setChecked(False)
        self.btn_shape.setChecked(False)
        self.btn_text.blockSignals(False)
        self.btn_shape.blockSignals(False)
        self.canvas.set_format_paint(True)
        self.canvas_stack.setCurrentIndex(0)
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        if sticky:
            self.statusBar().showMessage("连续格式刷：点文本框套用样式，Esc 取消", 5000)
        else:
            self.statusBar().showMessage("格式刷：点一个文本框套用样式，Esc 取消", 4000)

    def _end_format_paint(self, message: str | None = "已取消格式刷"):
        self._format_sticky = False
        self.canvas.set_format_paint(False)
        self._format_ignore = True
        self.btn_format.setChecked(False)
        self._format_ignore = False
        if message:
            self.statusBar().showMessage(message, 2500)

    def _on_format_paint_target(self, target):
        if target is False:
            self._end_format_paint("已取消格式刷")
            return
        if target is None or getattr(target, "type", None) != "text":
            if not self._format_sticky:
                self._end_format_paint("已取消格式刷")
            return
        self._push_history()
        target.style = self._last_text_style.clone()
        self.canvas.update_selected_from_element(target)
        self.props.set_element(target)
        self._remember_text_style(target)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()
        if self._format_sticky:
            self.statusBar().showMessage("已套用格式，可继续点其他文本框", 2500)
        else:
            self._end_format_paint("已套用文字格式")

    def _on_element_changed(self, element):
        self.canvas.update_selected_from_element(element)
        self._remember_text_style(element)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _on_layer_reorder(self, action: str):
        self.canvas.reorder_selected(action)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _on_align_requested(self, mode: str):
        self.canvas.align_selected(mode, relative=self.props.align_relative_mode())
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _on_distribute_requested(self, axis: str):
        self.canvas.distribute_selected(axis)
        self._set_dirty(True)
        self._refresh_thumbnail()
        self._push_hot_update()

    def _on_canvas_selection(self, element):
        els = self.canvas.selected_elements()
        self.props.set_selection(els)
        self.anim_panel.set_selected_element(element if len(els) == 1 else None)
        if els and self.side_tabs.currentIndex() == 0:
            self.side_tabs.setCurrentIndex(1)

    def _on_anims_changed(self):
        self._set_dirty(True)
        self._push_hot_update()

    def _prune_orphan_anims(self):
        slide = self._current_slide()
        if slide is None:
            return
        ids = {e.id for e in slide.elements}
        kept = [a for a in slide.animations if a.element_id in ids]
        if len(kept) != len(slide.animations):
            slide.animations = kept
            for i, a in enumerate(slide.sorted_animations()):
                a.order = i
            slide.animations = slide.sorted_animations()
            self.anim_panel.refresh()

    def _on_slide_modified(self):
        if self._syncing_from_ctrl:
            return
        self._prune_orphan_anims()
        self._set_dirty(True)
        els = self.canvas.selected_elements()
        self.props.set_selection(els)
        self.anim_panel.set_selected_element(els[0] if len(els) == 1 else None)
        QTimer.singleShot(0, self._refresh_thumbnail)
        self._push_hot_update()

    def _on_aspect(self):
        aspect = self.aspect_combo.currentData()
        if not aspect or aspect == self.doc.aspect:
            return
        self.canvas.commit_geometry()
        self.doc.aspect = aspect
        self._show_slide(self._slide_index)
        self._set_dirty(True)
        self._push_hot_update()

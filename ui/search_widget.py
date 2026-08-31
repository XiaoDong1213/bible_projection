import re
import sys
import ctypes
from ctypes import wintypes

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
)


class SearchLineEdit(QLineEdit):
    special_key = pyqtSignal(int)

    def keyPressEvent(self, event):
        key = event.key()

        if key in (
            Qt.Key.Key_Escape,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Space,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        ):
            self.special_key.emit(key)
            event.accept()
            return

        super().keyPressEvent(event)


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

    # 搜索框允许输入的字符
    ALLOWED = re.compile(r"[A-Za-z0-9 :：.．。\-]")

    def __init__(self, db, parent=None):
        super().__init__(parent)

        self.db = db

        self._formatting = False
        self._converted_book = False
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._candidate_cache = {}
        self._confirming = False
        self._scroll_anim = None

        self.setObjectName("searchPanel")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setMinimumWidth(660)
        self.setMaximumWidth(900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(0)

        # ============================================================
        # 搜索框
        # ============================================================

        self.search_input = SearchLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setMinimumHeight(58)
        self.search_input.setPlaceholderText(
            "输入书卷简拼、章节或节号"
        )
        self.search_input.setClearButtonEnabled(False)

        self.search_input.textEdited.connect(
            self._on_text_edited
        )

        self.search_input.special_key.connect(
            self._on_special_key
        )

        layout.addWidget(self.search_input)

        # ============================================================
        # 提示文字
        # ============================================================

        self.hint_label = QLabel(
            "↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭"
        )

        self.hint_label.setObjectName("searchHint")
        self.hint_label.setMinimumHeight(34)

        self.hint_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self.hint_label)

        # ============================================================
        # 候选列表
        # ============================================================

        self.result_list = QListWidget()
        self.result_list.setObjectName("searchCandidates")

        self.result_list.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        # 完全隐藏滚动条
        self.result_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.result_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.result_list.setFrameShape(
            QListWidget.Shape.NoFrame
        )

        self.result_list.setSpacing(5)
        self.result_list.setUniformItemSizes(True)

        # 仍然允许内部滚动，但用户看不到滚动条
        self.result_list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )

        self.result_list.itemClicked.connect(
            self._on_item_clicked
        )

        layout.addWidget(self.result_list)

        self._apply_visual_style()
        self._resize_result_area()

    # ================================================================
    # UI主题
    # ================================================================

    def _apply_visual_style(self):
        """
        根据当前系统/Qt主题自动调整。
        不使用 QPalette.color()，避免 PyQt6 版本兼容问题。
        """

        dark = (
            self.palette()
            .window()
            .color()
            .lightness()
            < 128
        )

        if dark:
            # --------------------------------------------------------
            # 暗色主题
            # --------------------------------------------------------

            panel = "rgba(25, 27, 31, 248)"
            input_bg = "rgba(36, 39, 44, 252)"

            item_bg = "rgba(255, 255, 255, 18)"
            hover_bg = "rgba(255, 255, 255, 30)"

            # 明显的选中效果
            selected_bg = "rgba(80, 150, 255, 82)"
            selected_border = "rgba(110, 175, 255, 235)"
            selected_text = "rgba(255,255,255,255)"

            border = "rgba(255,255,255,38)"

            hint = "rgba(225,230,238,220)"

            # 左侧高亮条
            accent = "rgba(100,170,255,255)"

        else:
            # --------------------------------------------------------
            # 亮色主题
            # --------------------------------------------------------

            panel = "rgba(248, 249, 252, 250)"
            input_bg = "rgba(255, 255, 255, 252)"

            item_bg = "rgba(0, 0, 0, 10)"
            hover_bg = "rgba(0, 0, 0, 20)"

            # 明显的选中效果
            selected_bg = "rgba(70, 130, 230, 42)"
            selected_border = "rgba(65, 125, 225, 210)"
            selected_text = "rgba(25,35,50,255)"

            border = "rgba(0,0,0,28)"

            hint = "rgba(55,60,68,220)"

            # 左侧高亮条
            accent = "rgba(65,125,225,255)"

        self.setStyleSheet(
            f"""
            /* =====================================================
               整体面板
               ===================================================== */

            QWidget#searchPanel {{
                background: {panel};
                border: 1px solid {border};
                border-radius: 20px;
            }}


            /* =====================================================
               搜索框
               ===================================================== */

            QLineEdit#searchInput {{
                background: {input_bg};
                color: palette(text);

                border: 1px solid {border};
                border-radius: 17px;

                padding: 0 20px;

                selection-background-color: rgba(90,140,220,100);
                selection-color: palette(text);
            }}

            QLineEdit#searchInput:focus {{
                border: 2px solid {selected_border};
            }}


            /* =====================================================
               提示文字
               ===================================================== */

            QLabel#searchHint {{
                background: transparent;

                color: {hint};

                border: none;

                padding: 0 7px;
            }}


            /* =====================================================
               候选列表
               ===================================================== */

            QListWidget#searchCandidates {{
                background: transparent;

                color: palette(text);

                border: none;

                padding: 5px 0 0 0;

                outline: none;
            }}


            /* =====================================================
               普通候选
               ===================================================== */

            QListWidget#searchCandidates::item {{
                background: {item_bg};

                color: palette(text);

                border: 1px solid {border};
                border-radius: 12px;

                padding: 8px 16px;

                min-height: 28px;
            }}


            /* =====================================================
               鼠标悬停
               ===================================================== */

            QListWidget#searchCandidates::item:hover {{
                background: {hover_bg};

                border: 1px solid {selected_border};
            }}


            /* =====================================================
               当前高亮项
               ===================================================== */

            QListWidget#searchCandidates::item:selected {{
                background: {selected_bg};

                color: {selected_text};

                border: 2px solid {selected_border};

                border-radius: 12px;

                padding-left: 15px;
            }}
            """
        )

        self._update_native_acrylic()

    # ================================================================
    # Windows 毛玻璃/实体背景
    # ================================================================

    def _update_native_acrylic(self):
        if sys.platform != "win32":
            return

        try:
            hwnd = int(self.winId())

            user32 = ctypes.windll.user32

            class Accent(ctypes.Structure):
                _fields_ = [
                    ("AccentState", wintypes.DWORD),
                    ("AccentFlags", wintypes.DWORD),
                    ("GradientColor", wintypes.DWORD),
                    ("AnimationId", wintypes.DWORD),
                ]

            class Data(ctypes.Structure):
                _fields_ = [
                    ("Attribute", wintypes.DWORD),
                    ("Data", ctypes.c_void_p),
                    ("SizeOfData", wintypes.SIZE),
                ]

            dark = (
                self.palette()
                .window()
                .color()
                .lightness()
                < 128
            )

            # 提高实体感，避免正文透过候选区域
            if dark:
                gradient = 0xF51E2024
            else:
                gradient = 0xF5F8F9FB

            accent = Accent(
                4,
                2,
                gradient,
                0,
            )

            data = Data(
                19,
                ctypes.addressof(accent),
                ctypes.sizeof(accent),
            )

            fn = getattr(
                user32,
                "SetWindowCompositionAttribute",
                None,
            )

            if fn:
                fn.argtypes = [
                    wintypes.HWND,
                    ctypes.POINTER(Data),
                ]

                fn.restype = wintypes.BOOL

                fn(
                    hwnd,
                    ctypes.byref(data),
                )

        except Exception:
            pass

    # ================================================================
    # 显示
    # ================================================================

    def showEvent(self, event):
        super().showEvent(event)

        self._formatting = False
        self._converted_book = False
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._confirming = False

        self.result_list.clear()

        self._resize_result_area()

        self._update_hint(
            "↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭"
        )

        self.search_input.setFocus()
        self.search_input.selectAll()

        self._update_native_acrylic()

    # ================================================================
    # 提示条
    # ================================================================

    def _update_hint(self, text):
        self.hint_label.setText(text)
        self._resize_result_area()

    # ================================================================
    # 候选框高度
    # ================================================================

    def _resize_result_area(self):
        count = self.result_list.count()

        visible = min(count, 8)

        if visible:
            row_h = max(
                42,
                self.result_list.sizeHintForRow(0),
            )

            height = (
                visible * row_h
                + max(0, visible - 1) * 5
                + 10
            )

            self.result_list.setFixedHeight(height)

        else:
            self.result_list.setFixedHeight(0)

        self.adjustSize()

    # ================================================================
    # 文本规范化
    # ================================================================

    @staticmethod
    def _norm(value):
        return re.sub(
            r"[\s._\-]+",
            "",
            str(value or "")
            .strip()
            .lower(),
        )

    # ================================================================
    # 简拼
    # ================================================================

    def _code(self, book):
        return self._norm(
            self.db.book_meta
            .get(book, {})
            .get("pinyin", "")
        )

    def _candidates(self, query):
        query = self._norm(query)

        if query in self._candidate_cache:
            return self._candidate_cache[query]

        result = [
            b
            for b in self.db.book_names
            if self._code(b).startswith(query)
        ] if query else []

        self._candidate_cache[query] = result

        return result

    def _exact(self, query):
        query = self._norm(query)

        for book in self.db.book_names:
            if self._code(book) == query:
                return book

        return None

    # ================================================================
    # 章节/节最大限制
    # ================================================================

    def _chapter_count(self, book):
        try:
            return int(
                self.db.book_meta
                .get(book, {})
                .get("chapter_count")
                or self.db.get_chapter_count(book)
                or 0
            )
        except Exception:
            return 0

    def _verse_count(self, book, chapter):
        try:
            return int(
                self.db.get_verse_count(
                    book,
                    chapter,
                )
                or 0
            )
        except Exception:
            return 0

    # ================================================================
    # 设置搜索框文字
    # ================================================================

    def _set_text(self, text, converted=None):
        self._formatting = True

        try:
            value = str(text or "")

            self.search_input.setText(value)

            self.search_input.setCursorPosition(
                len(value)
            )

        finally:
            self._formatting = False

        if converted is not None:
            self._converted_book = bool(converted)

    # ================================================================
    # 转换为书卷
    # ================================================================

    def _convert_book(self, book):
        self._selected_book = book
        self._stage = "chapter"
        self._space_mode = False
        self._converted_book = True

        self._set_text(book, True)

        self.result_list.clear()

        self._resize_result_area()

        self._update_hint(
            f"已识别为 {book}　·　请输入章节　·　Space 进入节号"
        )

        self.search_input.setFocus()

    # ================================================================
    # 显示候选
    # ================================================================

    def _show_candidates(self, books):
        self.result_list.setUpdatesEnabled(False)

        try:
            self.result_list.clear()

            for index, book in enumerate(books, 1):

                code = self._code(book).upper()

                try:
                    short = self.db._short_name(book)
                except Exception:
                    short = book

                item = QListWidgetItem(
                    f"{index:02d}    {code or short}    {book}"
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    book,
                )

                self.result_list.addItem(item)

        finally:
            self.result_list.setUpdatesEnabled(True)

        if self.result_list.count():
            self.result_list.setCurrentRow(0)

        self._resize_result_area()

    # ================================================================
    # 上下选择
    # ================================================================

    def _move_highlight(self, delta):
        count = self.result_list.count()

        if not count:
            return

        row = max(
            0,
            min(
                self.result_list.currentRow() + delta,
                count - 1,
            ),
        )

        self.result_list.setCurrentRow(row)

        item = self.result_list.item(row)

        if item:
            self._smooth_scroll_to(item)

    # ================================================================
    # 平滑滚动
    # ================================================================

    def _smooth_scroll_to(self, item):
        bar = self.result_list.verticalScrollBar()

        row_h = max(
            1,
            self.result_list.sizeHintForRow(0),
        )

        target = (
            self.result_list.indexFromItem(item).row()
            * (row_h + 5)
        )

        target = max(
            bar.minimum(),
            min(target, bar.maximum()),
        )

        if self._scroll_anim:
            self._scroll_anim.stop()

        self._scroll_anim = QPropertyAnimation(
            bar,
            b"value",
            self,
        )

        self._scroll_anim.setDuration(160)

        self._scroll_anim.setStartValue(
            bar.value()
        )

        self._scroll_anim.setEndValue(target)

        self._scroll_anim.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self._scroll_anim.start()

    # ================================================================
    # 当前书卷
    # ================================================================

    def _select_current_book(self):
        item = self.result_list.currentItem()

        if item is None:
            return

        book = item.data(
            Qt.ItemDataRole.UserRole
        )

        if book:
            self._convert_book(book)

    # ================================================================
    # 获取书卷后面的内容
    # ================================================================

    def _suffix(self):
        if (
            self._selected_book
            and self.search_input.text().startswith(
                self._selected_book
            )
        ):
            return self.search_input.text()[
                len(self._selected_book):
            ]

        return ""

    # ================================================================
    # Space：章节 → 节
    # ================================================================

    def _space_after_chapter(self):
        value = self._suffix().strip()

        if not re.fullmatch(r"\d+", value):
            return

        chapter = int(value)

        maximum = self._chapter_count(
            self._selected_book
        )

        if not 1 <= chapter <= maximum:
            self._update_hint(
                f"章节超出范围　·　本书最多 {maximum} 章"
            )
            return

        self._stage = "verse"

        self._set_text(
            f"{self._selected_book} {chapter}:"
        )

        self._update_hint(
            "请输入开始节　·　Space 生成节范围"
        )

    # ================================================================
    # Space：开始节 → 结束节
    # ================================================================

    def _space_after_verse(self):
        match = re.fullmatch(
            r"(\d+)\s*[:.]\s*(\d+)",
            self._suffix().strip(),
        )

        if not match:
            return

        chapter, verse = map(
            int,
            match.groups(),
        )

        maximum = self._verse_count(
            self._selected_book,
            chapter,
        )

        if not 1 <= verse <= maximum:
            self._update_hint(
                f"本章最多 {maximum} 节"
            )
            return

        self._space_mode = True

        self._set_text(
            f"{self._selected_book} "
            f"{chapter}:{verse}-"
        )

        self._update_hint(
            f"请输入结束节　·　范围 {verse}–{maximum}"
        )

    # ================================================================
    # 删除逻辑
    # ================================================================

    def _delete_segment(self):
        text = self.search_input.text()

        # ------------------------------------------------------------
        # 还没选择书卷
        # ------------------------------------------------------------

        if not self._selected_book:

            if text:
                self._set_text(text[:-1])
            else:
                self._set_text("")

            self._refresh_book_state(
                self.search_input.text()
            )

            self.search_input.setFocus()

            return

        book = self._selected_book

        if not text.startswith(book):
            self._set_text("")
            self._selected_book = None
            self._stage = "book"
            self._refresh_book_state("")
            return

        suffix = text[len(book):]

        # ------------------------------------------------------------
        # 删除结束节：
        #
        # 例如：
        # 创世记 1:1-5
        # 删除 → 创世记 1:1-
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"\s*(\d+)\s*[:.]\s*(\d+)\s*-\s*(\d+)\s*",
            suffix,
        )

        if match:
            chapter, verse, end = match.groups()

            self._set_text(
                f"{book} {chapter}:{verse}-"
            )

            self._stage = "verse"
            self._space_mode = True

            self._refresh_selected(
                book,
                self._suffix(),
            )

            self._update_hint(
                "请输入结束节"
            )

            return

        # ------------------------------------------------------------
        # 删除范围连接符
        #
        # 创世记 1:1-
        # → 创世记 1:1
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"\s*(\d+)\s*[:.]\s*(\d+)\s*-\s*",
            suffix,
        )

        if match:
            chapter, verse = match.groups()

            self._set_text(
                f"{book} {chapter}:{verse}"
            )

            self._stage = "verse"
            self._space_mode = False

            self._refresh_selected(
                book,
                self._suffix(),
            )

            self._update_hint(
                "请输入开始节　·　Space 生成节范围"
            )

            return

        # ------------------------------------------------------------
        # 删除节
        #
        # 创世记 1:5
        # → 创世记 1:
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"\s*(\d+)\s*[:.]\s*(\d+)\s*",
            suffix,
        )

        if match:
            chapter = match.group(1)

            self._set_text(
                f"{book} {chapter}:"
            )

            self._stage = "verse"
            self._space_mode = False

            self._refresh_selected(
                book,
                self._suffix(),
            )

            self._update_hint(
                "请输入开始节　·　Space 生成节范围"
            )

            return

        # ------------------------------------------------------------
        # 删除冒号
        #
        # 创世记 1:
        # → 创世记 1
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"\s*(\d+)\s*[:.]\s*",
            suffix,
        )

        if match:
            chapter = match.group(1)

            self._set_text(
                f"{book} {chapter}"
            )

            self._stage = "chapter"
            self._space_mode = False

            self._refresh_selected(
                book,
                self._suffix(),
            )

            self._update_hint_for_stage()

            return

        # ------------------------------------------------------------
        # 删除章节
        #
        # 创世记 1
        # → 创世记
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"\s*(\d+)\s*",
            suffix,
        )

        if match:
            self._set_text(book)

            self._stage = "chapter"
            self._space_mode = False

            self._refresh_selected(
                book,
                "",
            )

            self._update_hint_for_stage()

            return

        # ------------------------------------------------------------
        # 最后才删除整个书卷
        # ------------------------------------------------------------

        self._set_text("")

        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._converted_book = False

        self.result_list.clear()

        self._resize_result_area()

        self._refresh_book_state("")

        self.search_input.setFocus()

    # ================================================================
    # 刷新书卷搜索
    # ================================================================

    def _refresh_book_state(self, text):
        self._stage = "book"
        self._selected_book = None
        self._converted_book = False
        self._space_mode = False

        self.result_list.clear()

        query = text.strip()

        if not query:
            self._update_hint(
                "↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭"
            )
            return

        if re.fullmatch(r"[A-Za-z]+", query):

            candidates = self._candidates(query)

            # 单字母唯一匹配
            if (
                len(query) == 1
                and len(candidates) == 1
            ):
                self._convert_book(
                    candidates[0]
                )
                return

            # 完整简拼唯一匹配
            if (
                len(candidates) == 1
                and self._code(candidates[0])
                == self._norm(query)
            ):
                self._convert_book(
                    candidates[0]
                )
                return

            # 多候选
            if candidates:
                self._show_candidates(
                    candidates
                )

                self._update_hint(
                    "↑↓ 选择书卷　·　Space 确认当前项　·　Enter 确认"
                )

                return

            # 单字母兜底
            if len(query) == 1:

                first = [
                    b
                    for b in self.db.book_names
                    if self._code(b)[:1]
                    == query.lower()
                ]

                if len(first) == 1:
                    self._convert_book(
                        first[0]
                    )
                    return

            exact = self._exact(query)

            if exact:
                self._convert_book(exact)
                return

        self._update_hint(
            "↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭"
        )

    # ================================================================
    # 阶段提示
    # ================================================================

    def _update_hint_for_stage(self):

        if self._stage == "chapter":

            self._update_hint(
                f"已选择 {self._selected_book}　·　请输入章节　·　Space 进入节号"
            )

        elif self._stage == "verse":

            self._update_hint(
                "请输入开始节　·　Space 生成节范围"
            )

        elif self._space_mode:

            self._update_hint(
                "请输入结束节"
            )

    # ================================================================
    # 特殊按键
    # ================================================================

    def _on_special_key(self, key):

        if key == Qt.Key.Key_Escape:

            self.close_requested.emit()

        elif key == Qt.Key.Key_Up:

            self._move_highlight(-1)

        elif key == Qt.Key.Key_Down:

            self._move_highlight(1)

        elif key == Qt.Key.Key_Space:

            if (
                self._stage == "book"
                and self.result_list.count()
            ):
                self._select_current_book()

            elif (
                self._stage == "chapter"
                and self._selected_book
            ):
                self._space_after_chapter()

            elif (
                self._stage == "verse"
                and self._selected_book
            ):
                self._space_after_verse()

        elif key in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        ):

            self._delete_segment()

    # ================================================================
    # 输入文字
    # ================================================================

    def _on_text_edited(self, text):

        if self._formatting:
            return

        # ------------------------------------------------------------
        # 书卷阶段
        # ------------------------------------------------------------

        if self._stage == "book":

            clean = "".join(
                c
                for c in text
                if self.ALLOWED.fullmatch(c)
            )

            if clean != text:
                self._set_text(clean)
                text = clean

            self._refresh_book_state(text)

            return

        # ------------------------------------------------------------
        # 已经选中书卷
        # ------------------------------------------------------------

        if not self._selected_book:
            return

        book = self._selected_book

        # 防止删除书卷名
        if not text.startswith(book):

            self._set_text(
                book,
                True,
            )

            return

        suffix = text[len(book):]

        # 只允许章节/节相关字符
        if not re.fullmatch(
            r"[\s0-9:：.．。\-]*",
            suffix,
        ):

            suffix = re.sub(
                r"[^0-9 :：.．。\-]",
                "",
                suffix,
            )

            self._set_text(
                book + suffix,
                True,
            )

        self._refresh_selected(
            book,
            suffix,
        )

    # ================================================================
    # 刷新章节/节候选
    # ================================================================

    def _refresh_selected(
        self,
        book,
        suffix,
    ):

        value = (
            suffix
            .strip()
            .replace("：", ":")
            .replace("．", ".")
            .replace("。", ".")
        )

        self.result_list.clear()

        if not value:

            self._resize_result_area()

            self._update_hint_for_stage()

            return

        match = re.fullmatch(
            r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?",
            value,
        )

        if not match:
            return

        chapter_text, verse_text, end_text = (
            match.groups()
        )

        chapter = int(chapter_text)

        max_chapter = self._chapter_count(book)

        # ------------------------------------------------------------
        # 章节最大限制
        # ------------------------------------------------------------

        if not 1 <= chapter <= max_chapter:

            self._update_hint(
                f"章节超出范围　·　本书最多 {max_chapter} 章"
            )

            return

        # ------------------------------------------------------------
        # 只有章节
        # ------------------------------------------------------------

        if verse_text is None:

            item = QListWidgetItem(
                f"01    {book}    第 {chapter} 章"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                (
                    book,
                    chapter,
                    None,
                    None,
                ),
            )

            self.result_list.addItem(item)

            self.result_list.setCurrentRow(0)

            self._resize_result_area()

            return

        verse = int(verse_text)

        max_verse = self._verse_count(
            book,
            chapter,
        )

        # ------------------------------------------------------------
        # 节最大限制
        # ------------------------------------------------------------

        if not 1 <= verse <= max_verse:

            self._update_hint(
                f"第 {chapter} 章最多 {max_verse} 节"
            )

            return

        # ------------------------------------------------------------
        # 输入了 -
        # ------------------------------------------------------------

        if end_text is None:

            if "-" in value:

                self._update_hint(
                    f"请输入结束节　·　范围 {verse}–{max_verse}"
                )

                return

            # 单节
            item = QListWidgetItem(
                f"01    {book}    "
                f"{chapter}:{verse}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                (
                    book,
                    chapter,
                    verse,
                    verse,
                ),
            )

            self.result_list.addItem(item)

            self.result_list.setCurrentRow(0)

            self._resize_result_area()

            return

        # ------------------------------------------------------------
        # "-" 后面还没有数字
        # ------------------------------------------------------------

        if end_text == "":

            self._update_hint(
                f"请输入结束节　·　范围 {verse}–{max_verse}"
            )

            return

        end = int(end_text)

        # ------------------------------------------------------------
        # 范围不能倒着
        # ------------------------------------------------------------

        if end < verse:

            self._update_hint(
                f"结束节不能小于开始节 {verse}"
            )

            return

        # ------------------------------------------------------------
        # 结束节不能超过本章最大节
        # ------------------------------------------------------------

        if end > max_verse:

            self._update_hint(
                f"本章最多 {max_verse} 节，不能输入 {end}"
            )

            return

        # ------------------------------------------------------------
        # 完整范围
        # ------------------------------------------------------------

        item = QListWidgetItem(
            f"01    {book}    "
            f"{chapter}:{verse}-{end}"
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            (
                book,
                chapter,
                verse,
                end,
            ),
        )

        self.result_list.addItem(item)

        self.result_list.setCurrentRow(0)

        self._resize_result_area()

    # ================================================================
    # 解析最终输入
    # ================================================================

    def _parse(self, text):

        value = (
            text
            .strip()
            .replace("：", ":")
            .replace("．", ".")
            .replace("。", ".")
        )

        book = self._selected_book

        if not book:

            match = re.match(
                r"^([A-Za-z]+)",
                value,
            )

            book = (
                self._exact(match.group(1))
                if match
                else None
            )

        if not book:
            return None

        suffix = (
            value[len(book):].strip()
            if value.startswith(book)
            else value
        )

        # ------------------------------------------------------------
        # 只有章节
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"(\d+)",
            suffix,
        )

        if match:

            chapter = int(
                match.group(1)
            )

            return (
                (book, chapter, None, None)
                if 1 <= chapter
                <= self._chapter_count(book)
                else None
            )

        # ------------------------------------------------------------
        # 章节 + 节 / 节范围
        # ------------------------------------------------------------

        match = re.fullmatch(
            r"(\d+)\s*[:.]\s*(\d+)"
            r"(?:\s*-\s*(\d+))?",
            suffix,
        )

        if not match:
            return None

        chapter, verse, end = match.groups()

        chapter = int(chapter)
        verse = int(verse)

        end = (
            int(end)
            if end
            else verse
        )

        max_verse = self._verse_count(
            book,
            chapter,
        )

        if (
            1 <= chapter
            <= self._chapter_count(book)
            and 1 <= verse
            <= end
            <= max_verse
        ):

            return (
                book,
                chapter,
                verse,
                end,
            )

        return None

    # ================================================================
    # 点击候选
    # ================================================================

    def _on_item_clicked(self, item):

        data = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not data:
            return

        if (
            isinstance(data, tuple)
            and len(data) == 4
            and data[2] is not None
        ):

            self.search_triggered.emit(data)

            self.close_requested.emit()

            return

        book = (
            data[0]
            if isinstance(data, tuple)
            else data
        )

        self._convert_book(book)

    # ================================================================
    # Enter确认
    # ================================================================

    def _on_confirm(self):

        if self._confirming:
            return

        self._confirming = True

        try:

            parsed = self._parse(
                self.search_input.text()
            )

            if parsed:

                self.search_triggered.emit(
                    parsed
                )

                self.close_requested.emit()

            elif (
                self._stage == "book"
                and self.result_list.count()
            ):

                self._select_current_book()

            else:

                self._update_hint(
                    "请输入有效的书卷、章节或节范围"
                )

        finally:

            self._confirming = False

    # ================================================================
    # 回车
    # ================================================================

    def keyPressEvent(self, event):

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):

            self._on_confirm()

            event.accept()

            return

        super().keyPressEvent(event)
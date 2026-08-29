# ui/navigation_panel.py
# 左侧导航面板
# 功能：旧约/新约/简称/历史记录 四个标签页切换

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from .history_item import HistoryItemWidget


class NavigationPanel(QWidget):
    # 信号：书卷被选中
    book_selected = pyqtSignal(str, int)  # 参数：书卷名，章节

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.history = []  # 历史记录列表

        self.setFixedWidth(210)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签页容器
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        # 1. 旧约列表
        self.old_list = self._create_book_list("old")
        self.tab_widget.addTab(self.old_list, "旧约")

        # 2. 新约列表
        self.new_list = self._create_book_list("new")
        self.tab_widget.addTab(self.new_list, "新约")

        # 3. 简称列表
        self.short_list = self._create_short_list()
        self.tab_widget.addTab(self.short_list, "简称")

        # 4. 历史记录页
        history_widget = QWidget()
        history_layout = QVBoxLayout()
        history_layout.setContentsMargins(0, 0, 0, 0)

        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        history_layout.addWidget(self.history_list, 1)

        # 清空历史按钮
        clear_btn = QPushButton("清空历史记录")
        clear_btn.setObjectName("clearHistoryBtn")
        clear_btn.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_btn)

        history_widget.setLayout(history_layout)
        self.tab_widget.addTab(history_widget, "历史")

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def _create_book_list(self, category):
        """创建书卷列表"""
        list_widget = QListWidget()
        books = self.db.get_books(category)
        for book_name, short_name in books:
            item = QListWidgetItem(book_name)
            item.setData(Qt.ItemDataRole.UserRole, book_name)
            list_widget.addItem(item)
        list_widget.itemClicked.connect(self._on_book_clicked)
        return list_widget

    def _create_short_list(self):
        """创建简称列表"""
        list_widget = QListWidget()
        books = self.db.get_books()
        for book_name, short_name in books:
            item = QListWidgetItem(f"{short_name}  —  {book_name}")
            item.setData(Qt.ItemDataRole.UserRole, book_name)
            list_widget.addItem(item)
        list_widget.itemClicked.connect(self._on_book_clicked)
        return list_widget

    def _on_book_clicked(self, item):
        """点击书卷，加载第一章"""
        book_name = item.data(Qt.ItemDataRole.UserRole)
        self.book_selected.emit(book_name, 1)
        self.add_to_history(book_name, 1, None, None)

    # ============== 历史记录管理 ==============
    def load_history(self, history_list):
        """加载历史记录"""
        self.history = history_list
        self._update_history_list()

    def add_to_history(self, book, chapter, start, end):
        """添加一条历史记录（自动去重，移到最前）"""
        entry = (book, chapter, start, end)
        if entry in self.history:
            self.history.remove(entry)
        self.history.insert(0, entry)
        self.history = self.history[:30]  # 最多保留30条
        self._update_history_list()

    def _update_history_list(self):
        """刷新历史记录列表显示"""
        self.history_list.clear()
        for i, (book, chapter, start, end) in enumerate(self.history):
            # 格式化显示文本
            if start is None:
                text = f"{book} {chapter}章"
            elif end is None:
                text = f"{book} {chapter}:{start}-末"
            elif start == end:
                text = f"{book} {chapter}:{start}"
            else:
                text = f"{book} {chapter}:{start}-{end}"

            item = QListWidgetItem()
            self.history_list.addItem(item)

            # 自定义历史项控件
            widget = HistoryItemWidget(i, text)
            widget.clicked.connect(self._on_history_clicked)
            widget.deleted.connect(self._delete_history)

            item.setSizeHint(widget.sizeHint())
            self.history_list.setItemWidget(item, widget)

    def _on_history_clicked(self, index):
        """点击历史记录，加载对应经文"""
        book, chapter, start, end = self.history[index]
        self.book_selected.emit(book, chapter)
        # 移到最顶部
        entry = self.history.pop(index)
        self.history.insert(0, entry)
        self._update_history_list()

    def _delete_history(self, index):
        """删除单条历史记录"""
        if 0 <= index < len(self.history):
            del self.history[index]
            self._update_history_list()

    def _clear_history(self):
        """清空所有历史记录"""
        self.history.clear()
        self._update_history_list()

    def get_history(self):
        """获取当前历史列表，用于保存"""
        return self.history

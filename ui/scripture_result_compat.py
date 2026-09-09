import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from .themes import theme_tokens


class ScriptureResultWidget(QFrame):
    """旧版经文搜索面板使用的结果卡片，兼容当前搜索结果数据结构。"""

    activated = pyqtSignal(object)
    copy_requested = pyqtSignal(object)
    project_requested = pyqtSignal(object)

    def __init__(self, result, keywords, theme="dark", parent=None):
        super().__init__(parent)
        self.result = result
        self.keywords = keywords
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.setObjectName("scriptureSearchResult")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 13, 16, 13)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        label = result.get("verse_label", result.get("verse", ""))
        title = QPushButton(f"{result['book']} {result['chapter']}:{label}")
        title.setObjectName("scriptureResultTitle")
        title.setFlat(True)
        title.setCursor(Qt.CursorShape.PointingHandCursor)
        title.clicked.connect(lambda: self.activated.emit(self.result))
        top.addWidget(title, 1)

        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("scriptureResultAction")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.result))
        top.addWidget(copy_btn)

        project_btn = QPushButton("投影")
        project_btn.setObjectName("scriptureResultAction")
        project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        project_btn.clicked.connect(lambda: self.project_requested.emit(self.result))
        top.addWidget(project_btn)
        root.addLayout(top)

        text = QLabel(self._highlight(result.get("text", ""), keywords, self.theme))
        text.setObjectName("scriptureResultText")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        root.addWidget(text)

    @staticmethod
    def _highlight(text, keywords, theme):
        t = theme_tokens(theme)
        safe = html.escape(str(text))
        terms = sorted(
            {str(k).strip() for k in keywords if str(k).strip()},
            key=len,
            reverse=True,
        )
        for term in terms:
            safe_term = html.escape(term)
            safe = safe.replace(
                safe_term,
                f'<span style="background-color:{t["accent"]}; '
                f'color:#FFFFFF; padding:1px 3px;">{safe_term}</span>',
            )
        return safe

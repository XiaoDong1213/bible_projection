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
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        label = result.get("verse_label", result.get("verse", ""))
        title = QPushButton(f"{result['book']} {result['chapter']}:{label}")
        title.setObjectName("scriptureResultTitle")
        title.setFlat(True)
        title.setCursor(Qt.CursorShape.PointingHandCursor)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title.setFixedHeight(30)
        title.setStyleSheet("padding:0; margin:0; border:none; background:transparent;")
        title.clicked.connect(lambda: self.activated.emit(self.result))
        top.addWidget(title, 1)

        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("scriptureResultAction")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFixedSize(48, 30)
        copy_btn.setStyleSheet("padding:0; margin:0;")
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.result))
        top.addWidget(copy_btn)

        project_btn = QPushButton("投影")
        project_btn.setObjectName("scriptureResultAction")
        project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        project_btn.setFixedSize(48, 30)
        project_btn.setStyleSheet("padding:0; margin:0;")
        project_btn.clicked.connect(lambda: self.project_requested.emit(self.result))
        top.addWidget(project_btn)
        root.addLayout(top)

        text = QLabel(self._highlight(result.get("text", ""), keywords, self.theme))
        text.setObjectName("scriptureResultText")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
                f'<span style="background-color:{t["accent"]}; color:#FFFFFF;">{safe_term}</span>',
            )
        return safe

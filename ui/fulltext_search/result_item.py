import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout


class ScriptureResultWidget(QFrame):
    """搜索结果卡片。"""

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
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        label = result.get("verse_label", result.get("verse", ""))
        title = QPushButton(f"{result['book']} {result['chapter']}:{label}")
        title.setObjectName("scriptureResultTitle")
        title.setFlat(True)
        title.setCursor(Qt.CursorShape.PointingHandCursor)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title.setFixedHeight(28)
        title.clicked.connect(lambda: self.activated.emit(self.result))
        top.addWidget(title, 1)

        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("scriptureResultAction")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFixedSize(48, 28)
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.result))
        top.addWidget(copy_btn)

        project_btn = QPushButton("投影")
        project_btn.setObjectName("scriptureResultAction")
        project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        project_btn.setFixedSize(48, 28)
        project_btn.clicked.connect(lambda: self.project_requested.emit(self.result))
        top.addWidget(project_btn)
        root.addLayout(top)

        text = QLabel(self._highlight(result.get("text", ""), keywords, self.theme))
        text.setObjectName("scriptureResultText")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(text)

    @staticmethod
    def _highlight(text, keywords, theme):
        # 搜索高亮用暖黄底 + 深色字，亮/暗主题都清晰可读
        if theme == "light":
            bg, fg = "#FDE68A", "#1C1917"
        else:
            bg, fg = "#EAB308", "#1C1917"

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
                f'<span style="background-color:{bg};color:{fg};'
                f'border-radius:3px;padding:0 2px;">{safe_term}</span>',
            )
        return safe

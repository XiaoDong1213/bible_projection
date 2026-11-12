"""关于对话框：软件简介、联系方式、贡献者与检查更新入口。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.version import APP_VERSION
from core.paths import icon_path
from ui.themes import theme_tokens

GITHUB_URL = "https://github.com/XiaoDong1213/bible_projection"

ABOUT_TEXT = (
    "「Bible Pro」是一款免费的圣经投影软件，供教会聚会与个人灵修时投影经文使用。"
    "支持多个译本、快速定位与全文检索，也可以配合讲篇编辑与放映一起使用。\n"
    "软件由弟兄姊妹在业余时间开发维护，免费提供给有需要的人使用。"
)

CONTACT_TEXT = (
    "如您有任何意见或建议，可以通过以下方式联系我们，我们会尽快回复您。\n"
    "电子邮箱：sxd20041213@gmail.com\n"
    "开发者微信：SXD-20041213\n"
    f"GitHub项目地址：{GITHUB_URL}"
)

DATA_SUPPORT_URL = "https://biblepro.vip"

CONTRIBUTORS_TEXT = (
    "感谢以下贡献者（排名不分先后）：\n"
    "Xiao Dong、JiangRTTTR\n"
    "也感谢每一位反馈意见与建议的弟兄姊妹。\n"
    "感谢主内云实验室提供数据支持。"
)

COPYRIGHT_TEXT = f"Copyright © 2026 Bible Pro · Version {APP_VERSION}"


class AboutDialog(QDialog):
    """「关于」对话框，样式与帮助对话框同一套主题令牌。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme = getattr(parent, "theme", "dark") or "dark"
        self.setWindowTitle("关于")
        self.setObjectName("aboutDialog")
        self.setMinimumWidth(560)
        self._wrap_labels = []
        self._build_ui()
        # 初始宽度先定住；高度在 showEvent 里按真实几何精调
        # （未显示的窗口布局不生效，sizeHint 在真实字体下也虚高，预显示阶段无法算准）
        self.setFixedWidth(560)
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_sized_once", False):
            return
        self._sized_once = True
        # 定高必须用布局自己的 heightForWidth：sizeHint 有缓存虚高，
        # 是历次「空行」的根源。先失效全部缓存再取真实高度。
        for lab in self._wrap_labels:
            lab.ensurePolished()
            lab.updateGeometry()
        lay = self.layout()
        lay.invalidate()
        width = self.width()
        height = lay.heightForWidth(width) if lay.hasHeightForWidth() else self.sizeHint().height()
        screen = self.screen()
        if screen:
            height = min(screen.availableGeometry().height() - 80, height)
        self.setFixedSize(width, height)
        frame = self.frameGeometry()
        if screen:
            frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # 头部：图标 + 名称 + 版本
        header = QWidget()
        header.setObjectName("aboutHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 4, 0, 6)
        header_layout.setSpacing(6)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_label = QLabel()
        icon_file = icon_path()
        if icon_file.exists():
            icon_label.setPixmap(QIcon(str(icon_file)).pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(icon_label)

        name_label = QLabel("Bible Pro")
        name_label.setObjectName("aboutAppName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(name_label)

        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setObjectName("aboutVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(version_label)
        root.addWidget(header)

        root.addWidget(self._make_section("📖 关于我们", ABOUT_TEXT))
        root.addWidget(self._make_section("📮 联系我们", CONTACT_TEXT))
        # 致谢：主内云实验室带链接（biblepro.vip）
        accent = theme_tokens(self._theme)["accent"]
        link = (
            f'<a style="color: {accent}; text-decoration: none;" '
            f'href="{DATA_SUPPORT_URL}">主内云实验室</a>'
        )
        thanks_rich = CONTRIBUTORS_TEXT.replace("主内云实验室", link).replace(chr(10), "<br>")
        root.addWidget(self._make_section("💛 致谢", thanks_rich, rich=True))

        doxology_label = QLabel("愿荣耀归于我们在天上的父！")
        doxology_label.setObjectName("aboutDoxology")
        doxology_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(doxology_label)

        copyright_label = QLabel(COPYRIGHT_TEXT)
        copyright_label.setObjectName("aboutCopyright")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(copyright_label)

        footer = QWidget()
        footer.setObjectName("aboutFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(12)

        update_btn = QPushButton("检查更新")
        update_btn.setObjectName("aboutUpdateBtn")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setFixedHeight(34)
        update_btn.setMinimumWidth(90)
        update_btn.clicked.connect(self._check_update)
        footer_layout.addWidget(update_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addStretch(1)

        close_btn = QPushButton("知道了")
        close_btn.setObjectName("helpCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(
            close_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        root.addWidget(footer)

    def _make_section(self, title, body, rich=False):
        section = QFrame()
        section.setObjectName("helpSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("helpSectionTitle")
        layout.addWidget(title_label)

        body_label = QLabel()
        body_label.setObjectName("aboutBody")
        body_label.setWordWrap(True)
        self._wrap_labels.append(body_label)
        if rich:
            body_html = body
        else:
            body_html = (
                str(body)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
        # 行距 165%：纯 QLabel 排多行文字太紧凑
        body_label.setText(f'<p style="line-height: 165%">{body_html}</p>')
        body_label.setTextFormat(Qt.TextFormat.RichText)
        if rich:
            body_label.setOpenExternalLinks(True)
            body_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
        else:
            body_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
        layout.addWidget(body_label)
        return section

    def _check_update(self):
        from ui.update_prompt import run_update_check

        run_update_check(self, quiet=False)

"""运行时 UI 修复：集中处理经文分节间距和章/节选择器箭头可见性。"""


def apply_runtime_fixes(ScriptureDisplay, NavigationPanel):
    # 1. 按节分段：不用 QTextDocument 的 <p> 段落，避免段落高度被 line-height + margin
    #    叠加后造成第一节和第二节之间出现异常大的空白。
    def _render_scripture_fixed(self):
        fs = self._px(self.font_size)
        top = max(10, int(fs * 0.35))
        bottom = max(12, int(fs * 0.45))

        if self.verse_segmentation:
            items = "".join(
                f"<div style='margin:0;padding:0 0 {self._px(2)}px 0;"
                f"line-height:{self.line_spacing}%;text-align:justify;'>"
                f"{self._verse_html(n, t)}</div>"
                for n, t in self.verses
            )
        else:
            items = (
                "<p style='margin:0;padding:0;white-space:normal;text-align:justify;"
                f"line-height:{self.line_spacing}%;'>"
                + " ".join(self._verse_html(n, t) for n, t in self.verses)
                + "</p>"
            )

        html = (
            f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;"
            f"line-height:{self.line_spacing}%;text-align:justify;'>"
            + items
            + "</div>"
        )
        self.text_display.set_html(html)
        self._fit_document_width()

    ScriptureDisplay._render_scripture = _render_scripture_fixed

    # 2. 左侧“章 / 起 / 止”QSpinBox 的上下箭头改成高对比三角形，
    #    避免深色主题下系统默认黑色箭头几乎不可见。
    old_init = NavigationPanel.__init__

    def _init_fixed(self, db, parent=None):
        old_init(self, db, parent)
        spin_style = """
            QSpinBox {
                background: #242B38;
                color: #E8EAED;
                border: 1px solid #2A3344;
                border-radius: 6px;
                padding: 5px 24px 5px 8px;
                min-height: 26px;
                font-size: 13px;
            }
            QSpinBox:hover, QSpinBox:focus {
                border-color: #3B82F6;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #2C3545;
                border: none;
                width: 22px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #3A4558;
            }
            QSpinBox::up-arrow {
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 6px solid #E8EAED;
            }
            QSpinBox::down-arrow {
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #E8EAED;
            }
        """
        for spin in (self.chapter_spin, self.start_spin, self.end_spin):
            spin.setStyleSheet(spin_style)

    NavigationPanel.__init__ = _init_fixed

# 经文显示核心控件
# 提词器式滚动：QTextDocument + 浮点偏移绘制，避免滚动条整像素台阶
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt, QTimer, QElapsedTimer, pyqtSignal, QPropertyAnimation, QEasingCurve,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QFontMetrics, QPainter, QTextDocument,
)


class ScriptureBody(QWidget):
    """经文正文区：用浮点 scroll_y 平移绘制，观感接近网页提词器。"""

    scroll_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._doc = QTextDocument(self)
        self._doc.setDocumentMargin(0)
        self._scroll_y = 0.0
        self._pad_left = 0
        self._pad_right = 0
        self._pad_bottom = 0

    def set_html(self, html):
        self._doc.setHtml(html)
        self._doc.setDocumentMargin(0)
        self._clamp_scroll()
        self.update()

    def set_pads(self, left, right, bottom):
        self._pad_left = max(0, int(left))
        self._pad_right = max(0, int(right))
        self._pad_bottom = max(0, int(bottom))
        self._fit_text_width()
        self._clamp_scroll()
        self.update()

    def set_text_width(self, width):
        self._doc.setTextWidth(max(1.0, float(width)))
        self._clamp_scroll()
        self.update()

    def _fit_text_width(self):
        width = max(1, self.width() - self._pad_left - self._pad_right)
        self._doc.setTextWidth(float(width))

    def content_height(self):
        return float(self._doc.size().height())

    def view_height(self):
        return max(1.0, float(max(0, self.height() - self._pad_bottom)))

    def max_scroll(self):
        return max(0.0, self.content_height() - self.view_height())

    def scroll_y(self):
        return self._scroll_y

    def set_scroll_y(self, value, emit=True):
        try:
            y = float(value)
        except (TypeError, ValueError):
            return
        y = max(0.0, min(y, self.max_scroll()))
        if abs(y - self._scroll_y) < 1e-4:
            self._scroll_y = y
            return
        self._scroll_y = y
        self.update()
        if emit:
            self.scroll_changed.emit(self._scroll_y)

    def _clamp_scroll(self):
        self.set_scroll_y(self._scroll_y, emit=False)

    def scroll_fraction(self):
        m = self.max_scroll()
        return 0.0 if m <= 0 else self._scroll_y / m

    def set_scroll_fraction(self, fraction):
        try:
            f = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            return
        self.set_scroll_y(f * self.max_scroll())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_text_width()
        self._clamp_scroll()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = self.rect()
        if self._pad_bottom:
            clip.setHeight(max(0, clip.height() - self._pad_bottom))
        painter.setClipRect(clip)
        painter.translate(float(self._pad_left), -self._scroll_y)
        self._doc.drawContents(painter)

    def document(self):
        return self._doc


class ScriptureDisplay(QWidget):
    scroll_changed = pyqtSignal(int)
    # 自动滚动到达底部时通知外层，便于把速度 UI 同步回「暂停」
    scroll_finished = pyqtSignal()

    # 旧逻辑：每 30ms 滚 N 像素 → 折算成像素/秒，档位手感保持接近
    _TICK_MS_LEGACY = 30.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_family = "微软雅黑"
        self.font_size = 24
        self.font_color = QColor("#FFFFFF")
        self.bg_color = QColor("#000000")
        self.bg_image = None
        self._bg_pixmap = None
        self._bg_pixmap_path = None
        self._bg_scaled = None
        self._bg_scaled_size = None
        self.line_spacing = 160
        self.margin_left = 60
        self.margin_right = 60
        self.title_font_family = "微软雅黑"
        self.title_color = QColor("#87CEEB")
        self.title_size = 36
        self.title_min_size = 12
        self.verse_num_color = QColor("#FFD700")
        self.verse_num_size = 24
        self.verse_num_font_family = "微软雅黑"
        self.footer_text = ""
        self.footer_height = 45
        self.footer_size = 14
        self.footer_color = QColor("#AAAAAA")
        self.footer_font_family = "微软雅黑"
        self.scroll_speed = 0
        self._scroll_anim = None
        self._scroll_clock = QElapsedTimer()
        self._refresh_hz = 60.0
        self._screen_hooked = False
        self._title_text = ""
        self.verses = []
        self.verse_segmentation = False
        self._show_chapter_nums = False
        self._reference_size = None
        self._design_height = 1080
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.scroll_timer.timeout.connect(self._auto_scroll)
        self._apply_refresh_interval()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title_bar = QLabel("")
        self.title_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.title_bar)
        # 兼容旧引用名 text_display → 提词器正文
        self.text_display = ScriptureBody()
        self.text_display.scroll_changed.connect(self._on_body_scroll_changed)
        layout.addWidget(self.text_display, 1)
        self.footer_label = QLabel(self)
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.footer_label.show()
        self._update_footer_style()
        self._update_viewport_margins()

    def layout_scale(self):
        if self._reference_size:
            h = self._reference_size[1]
        else:
            h = max(1, self.height())
        return max(0.55, min(3.0, float(h) / float(self._design_height)))

    def _px(self, value):
        return max(1, int(round(float(value) * self.layout_scale())))

    def set_stage_size(self, width, height):
        self.set_reference_size(width, height)

    def clear_stage_size(self):
        self.clear_reference_size()

    def set_reference_size(self, width, height):
        try:
            self._reference_size = (max(1, int(width)), max(1, int(height)))
        except (TypeError, ValueError):
            self._reference_size = None
        self._refresh_layout_metrics()

    def clear_reference_size(self):
        self._reference_size = None
        self._refresh_layout_metrics()

    def _refresh_layout_metrics(self):
        self._update_viewport_margins()
        if self._title_text:
            self._set_adaptive_title(self._title_text)
        if self.verses:
            old = self.scroll_fraction()
            self._render_scripture()
            self.set_scroll_fraction(old)
        self._update_footer_style()
        self.update()

    def _update_viewport_margins(self):
        ml = self._px(self.margin_left)
        mr = self._px(self.margin_right)
        fh = self._px(self.footer_height)
        self.text_display.set_pads(ml, mr, fh)
        self._fit_document_width()

    def _fit_document_width(self):
        if self._reference_size:
            ref_width = max(1, self._reference_size[0])
            content_width = max(1, ref_width - self._px(self.margin_left) - self._px(self.margin_right))
            self.text_display.set_text_width(content_width)
        else:
            self.text_display._fit_text_width()
            self.text_display.update()

    def set_scripture(self, book_name, chapter, start_verse, end_verse, verses, title=None, show_chapter_nums=False):
        self.verses = list(verses or [])
        self._show_chapter_nums = bool(show_chapter_nums)
        if title:
            self._set_adaptive_title(title)
        else:
            unit = "篇" if book_name == "诗篇" else "章"
            if start_verse is None:
                title_text = f"{book_name}{chapter}{unit}"
            elif end_verse is None:
                title_text = f"{book_name}{chapter}{unit}{start_verse}-末节"
            elif start_verse == end_verse:
                title_text = f"{book_name}{chapter}{unit}{start_verse}节"
            else:
                title_text = f"{book_name}{chapter}{unit}{start_verse}-{end_verse}节"
            self._set_adaptive_title(title_text)
        self._render_scripture()
        self.set_scroll_position(0)
        self.update()

    def set_from_selection(self, selection, verses):
        """按 ScriptureSelection 更新标题与经文。"""
        self.set_scripture(
            selection.book,
            selection.primary_chapter,
            selection.primary_start,
            selection.primary_end,
            verses,
            title=selection.title(),
            show_chapter_nums=selection.is_multi_chapter,
        )

    def clear_scripture(self):
        """清空标题与经文内容。"""
        self.verses = []
        self._show_chapter_nums = False
        self._set_adaptive_title("")
        self.text_display.set_html("")
        self.set_scroll_position(0)
        self.update()

    def _set_adaptive_title(self, text):
        self._title_text = str(text or "")
        size = max(self._px(self.title_min_size), self._px(self.title_size))
        font = QFont(self.title_font_family, size)
        font.setBold(True)
        pad = self._px(24)
        avail = max(100, self.title_bar.width() - pad * 2)
        min_size = self._px(self.title_min_size)
        while QFontMetrics(font).horizontalAdvance(self._title_text) > avail and size > min_size:
            size -= 1
            font = QFont(self.title_font_family, size)
            font.setBold(True)
        h = max(self._px(42), QFontMetrics(font).height() + self._px(6))
        self.title_bar.setMinimumHeight(h)
        self.title_bar.setMaximumHeight(h)
        self.title_bar.setFont(font)
        self.title_bar.setStyleSheet(
            f'color:{self.title_color.name()};font-family:"{self.title_font_family}";'
            f"font-size:{size}px;font-weight:bold;background:transparent;padding:0 {pad}px;"
        )
        self.title_bar.setText(self._title_text)

    def set_verse_segmentation(self, enabled):
        enabled = bool(enabled)
        if self.verse_segmentation == enabled:
            return
        old = self.scroll_fraction()
        self.verse_segmentation = enabled
        if self.verses:
            self._render_scripture()
            self.set_scroll_fraction(old)

    def _verse_row(self, row):
        """兼容 (verse, text) 与 (chapter, verse, text)。"""
        if row is None:
            return None, None, ""
        if len(row) >= 3:
            return row[0], row[1], row[2]
        return None, row[0], row[1]

    def _verse_html(self, chapter, n, t):
        safe = str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        vn = self._px(self.verse_num_size)
        fs = self._px(self.font_size)
        label = f"{chapter}:{n}" if getattr(self, "_show_chapter_nums", False) and chapter is not None else str(n)
        return (
            f'<span style="color:{self.verse_num_color.name()};font-size:{vn}px;'
            f'font-family:&quot;{self.verse_num_font_family}&quot;;font-weight:bold;vertical-align:super;">{label}</span>'
            f'&nbsp;<span style="color:{self.font_color.name()};font-size:{fs}px;'
            f'font-family:&quot;{self.font_family}&quot;;">{safe}</span>'
        )

    def _render_scripture(self):
        fs = self._px(self.font_size)
        top = max(10, int(fs * 0.35))
        bottom = max(12, int(fs * 0.45))
        html = (
            f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;"
            f"line-height:{self.line_spacing}%;text-align:justify;'>"
        )
        rows = [self._verse_row(row) for row in self.verses]
        if self.verse_segmentation:
            html += "".join(
                f"<p style='margin:0 0 {self._px(1)}px 0;padding:0;"
                f"text-align:justify;line-height:{self.line_spacing}%;'>"
                f"{self._verse_html(ch, n, t)}</p>"
                for ch, n, t in rows
            )
        else:
            html += (
                "<p style='margin:0;padding:0;white-space:normal;text-align:justify;'>"
                + " ".join(self._verse_html(ch, n, t) for ch, n, t in rows)
                + "</p>"
            )
        self.text_display.set_html(html + "</div>")
        self._fit_document_width()

    def _update_footer_style(self):
        fs = self._px(self.footer_size)
        self.footer_label.setText(self.footer_text)
        self.footer_label.setFont(QFont(self.footer_font_family, fs))
        self.footer_label.setStyleSheet(
            f'color:{self.footer_color.name()};font-family:"{self.footer_font_family}";'
            f"font-size:{fs}px;background:transparent;"
        )

    def _ensure_bg_pixmap(self):
        path = self.bg_image
        if not path or not os.path.exists(path):
            self._bg_pixmap = None
            self._bg_pixmap_path = None
            self._bg_scaled = None
            self._bg_scaled_size = None
            return None
        if self._bg_pixmap is None or self._bg_pixmap_path != path:
            pix = QPixmap(path)
            self._bg_pixmap = pix if not pix.isNull() else None
            self._bg_pixmap_path = path
            self._bg_scaled = None
            self._bg_scaled_size = None
        return self._bg_pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), self.bg_color)
        pix = self._ensure_bg_pixmap()
        if pix is not None:
            size = self.size()
            if self._bg_scaled is None or self._bg_scaled_size != size:
                self._bg_scaled = pix.scaled(
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._bg_scaled_size = size
            scaled = self._bg_scaled
            painter.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
        super().paintEvent(event)
        self._update_overlay_geometry()

    def _on_body_scroll_changed(self, value):
        self.scroll_changed.emit(int(round(float(value))))

    def scroll_fraction(self):
        return self.text_display.scroll_fraction()

    def set_scroll_fraction(self, fraction):
        self.text_display.set_scroll_fraction(fraction)

    def set_scroll_position(self, value):
        self.text_display.set_scroll_y(value)

    def force_scroll_to(self, value):
        self.text_display.set_scroll_y(value)
        self.text_display.update()
        self.update()

    def get_scroll_y(self):
        return self.text_display.scroll_y()

    def max_scroll(self):
        return self.text_display.max_scroll()

    def get_scroll_anchor(self):
        # 改为比例锚点，重排后恢复相对位置
        return self.scroll_fraction()

    def set_scroll_anchor(self, anchor):
        try:
            a = float(anchor)
        except (TypeError, ValueError):
            return
        if a > 1.0:
            # 兼容旧字符位置：尽量落到文档顶部附近
            a = 0.0
        self.set_scroll_fraction(a)

    def _get_anim_y(self):
        return self.text_display.scroll_y()

    def _set_anim_y(self, value):
        self.text_display.set_scroll_y(value)

    anim_scroll_y = pyqtProperty(float, _get_anim_y, _set_anim_y)

    def _smooth_to(self, target, duration=120):
        target = max(0.0, min(float(target), self.text_display.max_scroll()))
        if self._scroll_anim:
            self._scroll_anim.stop()
        self._scroll_anim = QPropertyAnimation(self, b"anim_scroll_y", self)
        self._scroll_anim.setDuration(duration)
        self._scroll_anim.setStartValue(self.text_display.scroll_y())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.start()

    def set_scroll_speed(self, speed):
        # 与工具栏 0–9 档对齐；按像素/秒计速，定时器跟屏幕刷新率
        self.scroll_speed = max(0, min(9, int(speed)))
        if self.scroll_speed == 0:
            self.scroll_timer.stop()
            return
        self._hook_screen_changes()
        self._apply_refresh_interval()
        self._scroll_clock.restart()
        if not self.scroll_timer.isActive():
            self.scroll_timer.start()

    def _scroll_px_per_sec(self):
        if self.scroll_speed <= 0:
            return 0.0
        return float(self.scroll_speed) * (1000.0 / self._TICK_MS_LEGACY)

    def _detect_refresh_hz(self):
        screen = self.screen()
        if screen is None:
            win = self.window()
            if win is not None:
                screen = win.screen()
        hz = 60.0
        if screen is not None:
            try:
                hz = float(screen.refreshRate())
            except Exception:
                hz = 60.0
        if hz < 30.0:
            hz = 60.0
        elif hz > 240.0:
            hz = 240.0
        return hz

    def _apply_refresh_interval(self):
        self._refresh_hz = self._detect_refresh_hz()
        interval = max(1, int(round(1000.0 / self._refresh_hz)))
        self.scroll_timer.setInterval(interval)

    def _hook_screen_changes(self):
        if self._screen_hooked:
            return
        win = self.window()
        handle = win.windowHandle() if win is not None else None
        if handle is None:
            return
        handle.screenChanged.connect(self._on_screen_changed)
        self._screen_hooked = True

    def _on_screen_changed(self, _screen):
        was_running = self.scroll_timer.isActive() and self.scroll_speed > 0
        self._apply_refresh_interval()
        if was_running:
            self._scroll_clock.restart()
            self.scroll_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._hook_screen_changes()
        self._apply_refresh_interval()

    def _auto_scroll(self):
        body = self.text_display
        if body.scroll_y() >= body.max_scroll() - 0.05:
            self.scroll_timer.stop()
            self.scroll_speed = 0
            body.set_scroll_y(body.max_scroll())
            self.scroll_finished.emit()
            return

        elapsed_ms = self._scroll_clock.restart()
        if elapsed_ms <= 0:
            elapsed_ms = self.scroll_timer.interval()
        dt = min(float(elapsed_ms), 100.0) / 1000.0
        body.set_scroll_y(body.scroll_y() + self._scroll_px_per_sec() * dt)
        if body.scroll_y() >= body.max_scroll() - 0.05:
            self.scroll_timer.stop()
            self.scroll_speed = 0
            body.set_scroll_y(body.max_scroll())
            self.scroll_finished.emit()

    def scroll_by(self, delta):
        self._smooth_to(self.text_display.scroll_y() + float(delta))

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        self._smooth_to(self.text_display.scroll_y() - steps * 120.0, 90)
        event.accept()

    def apply_settings(self, settings):
        str_keys = (
            ("font_family", "font_family"),
            ("title_font_family", "title_font_family"),
            ("verse_num_font_family", "verse_num_font_family"),
            ("footer_font_family", "footer_font_family"),
        )
        int_keys = (
            ("font_size", "font_size"),
            ("line_spacing", "line_spacing"),
            ("title_size", "title_size"),
            ("verse_num_size", "verse_num_size"),
            ("footer_height", "footer_height"),
            ("footer_size", "footer_size"),
        )
        for attr, key in str_keys:
            if key in settings:
                try:
                    setattr(self, attr, str(settings[key]))
                except Exception:
                    pass
        for attr, key in int_keys:
            if key in settings:
                try:
                    setattr(self, attr, int(settings[key]))
                except Exception:
                    pass
        for attr, key in (
            ("font_color", "font_color"),
            ("verse_num_color", "verse_num_color"),
            ("title_color", "title_color"),
            ("bg_color", "bg_color"),
            ("footer_color", "footer_color"),
        ):
            if key in settings:
                setattr(self, attr, QColor(settings[key]))

        new_bg = settings.get("bg_image", self.bg_image) or None
        if new_bg != self.bg_image:
            self.bg_image = new_bg
            self._bg_pixmap = None
            self._bg_pixmap_path = None
            self._bg_scaled = None
            self._bg_scaled_size = None
        elif "bg_image" in settings and not settings.get("bg_image"):
            self.bg_image = None
            self._bg_pixmap = None
            self._bg_pixmap_path = None
            self._bg_scaled = None
            self._bg_scaled_size = None

        if "margin" in settings:
            try:
                self.margin_left = self.margin_right = int(settings["margin"])
            except Exception:
                pass
        if "footer_text" in settings:
            self.footer_text = settings["footer_text"]

        self._update_footer_style()
        self._update_viewport_margins()

        if "verse_segmentation" in settings:
            self.set_verse_segmentation(bool(settings["verse_segmentation"]))

        if self._title_text:
            self._set_adaptive_title(self._title_text)
        if self.verses:
            old = self.scroll_fraction()
            self._render_scripture()
            self.set_scroll_fraction(old)
        self.update()

    def _update_overlay_geometry(self):
        fh = self._px(self.footer_height)
        self.footer_label.setGeometry(0, max(0, self.height() - fh), self.width(), fh)
        self.title_bar.raise_()
        self.footer_label.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg_scaled = None
        self._bg_scaled_size = None
        if self._reference_size is None:
            if self._title_text:
                self._set_adaptive_title(self._title_text)
            self._update_viewport_margins()
            if self.verses:
                old = self.scroll_fraction()
                self._render_scripture()
                self.set_scroll_fraction(old)
            self._update_footer_style()
        else:
            if self._title_text:
                self._set_adaptive_title(self._title_text)
            self._update_viewport_margins()
            self._fit_document_width()
        self._update_overlay_geometry()

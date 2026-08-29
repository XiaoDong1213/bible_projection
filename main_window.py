# 主窗口 - 业务逻辑层
# 功能：协调各UI组件，处理快捷键、双屏同步、事件响应

import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar, QLabel, QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QKeySequence, QShortcut

from config import AppConfig
from bible_database import BibleDatabase
from ui import ScriptureDisplay, SearchWidget, NavigationPanel, ToolBarWidget, ExtensionWindow

class MainWindow(QMainWindow):
    def __init__(self, db: BibleDatabase, config: AppConfig):
        super().__init__(); self.db=db; self.config=config; self.extension_window=None
        self.current_book=None; self.current_chapter=None; self.current_start=None; self.current_end=None; self.verses=[]
        self.settings=config.load_display_settings(); self.theme=self.settings.get("theme","dark"); self.setWindowTitle("圣经投影系统"); self.setMinimumSize(800,600)
        geometry=config.load_window_state()
        if geometry: self.restoreGeometry(geometry)
        else: self.resize(1200,800)
        self._load_theme_style(); self._create_central_widget(); self._create_toolbar(); self._create_shortcuts(); self._create_statusbar()
        self.nav_panel.load_history(config.load_history()); self.nav_panel.history_changed.connect(self._save_history); self._apply_settings(self.settings)

    def _save_history(self, history): self.config.save_history(history)
    def _set_footer_text(self, text):
        text=str(text or ""); self.settings["footer_text"]=text; self.scripture_display.footer_text=text
        if hasattr(self.scripture_display,"footer_label"): self.scripture_display.footer_label.setText(text)
        if self.extension_window:
            self.extension_window.scripture_display.footer_text=text
            if hasattr(self.extension_window.scripture_display,"footer_label"): self.extension_window.scripture_display.footer_label.setText(text)
        self.config.save_display_settings({"footer_text":text})

    def _load_theme_style(self):
        style_path=os.path.join("styles",f"{self.theme}.qss")
        if os.path.exists(style_path):
            with open(style_path,"r",encoding="utf-8") as f: QApplication.instance().setStyleSheet(f.read())

    def _create_toolbar(self):
        self.toolbar=ToolBarWidget(); self.addToolBar(self.toolbar); self.toolbar.theme=self.theme; self.toolbar.load_settings(self.settings)
        self.toolbar.scroll_speed_changed.connect(self._on_scroll_speed); self.toolbar.extend_toggled.connect(self._toggle_extension); self.toolbar.settings_changed.connect(self._on_settings_changed)
        self.toolbar.theme_changed.connect(self._on_theme_changed); self.toolbar.topmost_toggled.connect(self._toggle_extension_topmost); self.toolbar.scroll_up.connect(lambda:self._scroll_manual(-40)); self.toolbar.scroll_down.connect(lambda:self._scroll_manual(40))
        self.scripture_display.scroll_changed.connect(self._sync_extension_scroll)

    def _create_central_widget(self):
        central=QWidget(); main_layout=QHBoxLayout(); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0); splitter=QSplitter(Qt.Orientation.Horizontal)
        self.nav_panel=NavigationPanel(self.db); self.nav_panel.book_selected.connect(self._on_book_selected); self.nav_panel.range_selected.connect(self._on_range_selected); self.nav_panel.verse_segmentation_changed.connect(self._on_verse_segmentation_changed); splitter.addWidget(self.nav_panel)
        self.scripture_display=ScriptureDisplay(); splitter.addWidget(self.scripture_display); splitter.setStretchFactor(0,0); splitter.setStretchFactor(1,1); splitter.setSizes([330,870]); main_layout.addWidget(splitter); central.setLayout(main_layout); self.setCentralWidget(central)

    def _create_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Return),self,self._show_search); QShortcut(QKeySequence(Qt.Key.Key_Enter),self,self._show_search); QShortcut(QKeySequence(Qt.Key.Key_F12),self,self._toggle_extension); QShortcut(QKeySequence(Qt.Key.Key_Right),self,self._add_verse_end); QShortcut(QKeySequence(Qt.Key.Key_Left),self,self._remove_verse_end); QShortcut(QKeySequence("Ctrl+Right"),self,self._add_verse_start); QShortcut(QKeySequence("Ctrl+Left"),self,self._remove_verse_start); QShortcut(QKeySequence(Qt.Key.Key_Up),self,lambda:self._scroll_manual(-30)); QShortcut(QKeySequence(Qt.Key.Key_Down),self,lambda:self._scroll_manual(30)); QShortcut(QKeySequence(Qt.Key.Key_Space),self,self._toggle_scroll_pause)

    def _create_statusbar(self):
        status=QStatusBar(); self.setStatusBar(status); self.status_label=QLabel("按回车键打开搜索"); status.addWidget(self.status_label)
    def _on_settings_changed(self,settings): self.settings.update(settings); self._apply_settings(settings); self.config.save_display_settings(settings)
    def _apply_settings(self,settings):
        self.settings.update(settings); self.scripture_display.apply_settings(settings); self.nav_panel.set_verse_segmentation(bool(settings.get("verse_segmentation",False))); self.scripture_display.set_verse_segmentation(bool(settings.get("verse_segmentation",False)))
        if self.extension_window: self.extension_window.apply_settings(settings); self.extension_window.scripture_display.set_verse_segmentation(bool(settings.get("verse_segmentation",False)))
    def _on_theme_changed(self,theme): self.theme=theme; self.settings["theme"]=theme; self._load_theme_style(); self.config.save_display_settings({"theme":theme})
    def _show_search(self):
        if hasattr(self,"search_widget") and self.search_widget.isVisible(): self.search_widget.close(); return
        self.search_widget=SearchWidget(self.db,self); self.search_widget.search_triggered.connect(self._on_search_result); self.search_widget.close_requested.connect(self._close_search); self.search_widget.move(self.mapToGlobal(QPoint(self.width()//2-180,80))); self.search_widget.show(); self.search_widget.search_input.setFocus()
    def _close_search(self):
        if hasattr(self,"search_widget"): self.search_widget.close()
    def _on_search_result(self,parsed):
        book_name,chapter,start_verse,end_verse=parsed; self._load_scripture(book_name,chapter,start_verse,end_verse); self.nav_panel.add_to_history(book_name,chapter,start_verse,end_verse); self._close_search()
    def _on_book_selected(self,book_name,chapter): self._load_scripture(book_name,chapter,None,None); self.nav_panel.add_to_history(book_name,chapter,1,self.db.get_verse_count(book_name,chapter))
    def _on_verse_segmentation_changed(self,enabled):
        enabled=bool(enabled); self.settings['verse_segmentation']=enabled; self.scripture_display.set_verse_segmentation(enabled)
        if self.extension_window: self.extension_window.scripture_display.set_verse_segmentation(enabled)
        self.config.save_display_settings({'verse_segmentation':enabled})
    def _on_range_selected(self,book_name,chapter,start_verse,end_verse): self._load_scripture(book_name,chapter,start_verse,end_verse); self.nav_panel.add_to_history(book_name,chapter,start_verse,end_verse)
    def _load_scripture(self,book_name,chapter,start_verse,end_verse):
        self.current_book=book_name; self.current_chapter=chapter; self.current_start=start_verse; self.current_end=end_verse
        if start_verse is None:
            verses=self.db.get_verse_range(book_name,chapter,1); self.current_start=1; self.current_end=verses[-1][0] if verses else 0
        else:
            verses=self.db.get_verse_range(book_name,chapter,start_verse,end_verse)
            if end_verse is None: self.current_end=verses[-1][0] if verses else start_verse
        self.verses=verses; self.scripture_display.set_scripture(book_name,chapter,self.current_start,self.current_end,verses)
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.update_scripture(book_name,chapter,start_verse,self.current_end if end_verse is None else end_verse,verses)
        self._update_status()
    def _update_status(self):
        if self.current_start is None: status=f"{self.current_book} 第{self.current_chapter}章（整章）"
        elif self.current_end is None: status=f"{self.current_book} {self.current_chapter}:{self.current_start}-末"
        elif self.current_start==self.current_end: status=f"{self.current_book} {self.current_chapter}:{self.current_start}"
        else: status=f"{self.current_book} {self.current_chapter}:{self.current_start}-{self.current_end}"
        self.status_label.setText(status)
    def _toggle_extension(self):
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.hide(); self.toolbar.set_extend_active(False); self.status_label.setText("已关闭扩展显示")
        else: self._show_extension()
    def _show_extension(self):
        screens=QApplication.screens()
        if len(screens)<2: self.status_label.setText("未检测到第二块屏幕"); return
        if not self.extension_window: self.extension_window=ExtensionWindow(); self.extension_window.apply_settings(self.settings)
        self.extension_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,self.toolbar.topmost_btn.isChecked()); geom=screens[1].geometry(); self.extension_window.setGeometry(geom); self.extension_window.showFullScreen()
        if self.verses: self.extension_window.update_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses)
        self.extension_window.set_scroll_speed(self.toolbar.scroll_slider.value()); self.toolbar.set_extend_active(True); self.status_label.setText(f"扩展显示: 屏幕2 ({geom.width()}x{geom.height()})")
    def _toggle_extension_topmost(self,on):
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,on); self.extension_window.show(); self.status_label.setText(f"扩展屏已{'开启' if on else '关闭'}置顶")
        self.config.save_display_settings({"extension_topmost":on})
    def _on_scroll_speed(self,speed):
        self.scripture_display.set_scroll_speed(speed)
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.set_scroll_speed(speed)
    def _scroll_manual(self,delta):
        self.scripture_display.scroll_by(delta)
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.scroll_by(delta)
    def _toggle_scroll_pause(self):
        slider=self.toolbar.scroll_slider
        if slider.value()>0: self._last_speed=slider.value(); slider.setValue(0)
        else: slider.setValue(getattr(self,"_last_speed",3))
    def _add_verse_end(self):
        if not self.verses:return
        max_verse=self.db.get_verse_count(self.current_book,self.current_chapter)
        if self.current_end<max_verse:
            self.current_end+=1; self.verses.extend(self.db.get_verse_range(self.current_book,self.current_chapter,self.current_end,self.current_end)); self._refresh_display()
    def _remove_verse_end(self):
        if len(self.verses)>1:self.verses.pop(); self.current_end-=1; self._refresh_display()
    def _add_verse_start(self):
        if not self.verses or self.current_start<=1:return
        new_start=self.current_start-1; self.verses=self.db.get_verse_range(self.current_book,self.current_chapter,new_start,new_start)+self.verses; self.current_start=new_start; self._refresh_display()
    def _remove_verse_start(self):
        if len(self.verses)>1:self.verses.pop(0); self.current_start+=1; self._refresh_display()
    def _refresh_display(self):
        self.scripture_display.set_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses)
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.update_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses)
        self._update_status()
    def _sync_extension_scroll(self,value):
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.set_scroll_position(value)
    def keyPressEvent(self,event):
        if hasattr(self,"search_widget") and self.search_widget.isVisible():
            if event.key()==Qt.Key.Key_Escape:self._close_search()
            return
        super().keyPressEvent(event)

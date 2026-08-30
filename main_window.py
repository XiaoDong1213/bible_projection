# 主窗口 - 业务逻辑层
import os
from PyQt6.QtWidgets import QMainWindow,QWidget,QHBoxLayout,QSplitter,QStatusBar,QLabel,QApplication
from PyQt6.QtCore import Qt,QPoint
from PyQt6.QtGui import QKeySequence,QShortcut
from config import AppConfig
from bible_database import BibleDatabase
from ui import ScriptureDisplay,SearchWidget,NavigationPanel,ToolBarWidget,ExtensionWindow

class MainWindow(QMainWindow):
    def __init__(self,db:BibleDatabase,config:AppConfig):
        super().__init__(); self.db=db; self.config=config; self.extension_window=None; self._syncing_scroll=False; self.current_book=None; self.current_chapter=None; self.current_start=None; self.current_end=None; self.verses=[]; self.settings=config.load_display_settings(); self.theme=self.settings.get("theme","dark"); self.setWindowTitle("圣经投影系统"); self.setMinimumSize(800,600)
        geometry=config.load_window_state(); self.restoreGeometry(geometry) if geometry else self.resize(1200,800); self._load_theme_style(); self._create_central_widget(); self._create_toolbar(); self._create_shortcuts(); self._create_statusbar(); self.nav_panel.load_history(config.load_history()); self.nav_panel.history_changed.connect(self._save_history); self._apply_settings(self.settings)
    def _save_history(self,h): self.config.save_history(h)
    def _load_theme_style(self):
        p=os.path.join("styles",f"{self.theme}.qss")
        if os.path.exists(p):
            with open(p,"r",encoding="utf-8") as f: QApplication.instance().setStyleSheet(f.read())
    def _create_toolbar(self): self.toolbar=ToolBarWidget(); self.addToolBar(self.toolbar); self.toolbar.theme=self.theme; self.toolbar.load_settings(self.settings); self.toolbar.scroll_speed_changed.connect(self._on_scroll_speed); self.toolbar.extend_toggled.connect(self._toggle_extension); self.toolbar.settings_changed.connect(self._on_settings_changed); self.toolbar.theme_changed.connect(self._on_theme_changed); self.toolbar.topmost_toggled.connect(self._toggle_extension_topmost); self.toolbar.scroll_up.connect(lambda:self._scroll_manual(-40)); self.toolbar.scroll_down.connect(lambda:self._scroll_manual(40)); self.scripture_display.scroll_changed.connect(self._sync_extension_scroll)
    def _create_central_widget(self):
        central=QWidget(); layout=QHBoxLayout(); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); splitter=QSplitter(Qt.Orientation.Horizontal); self.nav_panel=NavigationPanel(self.db); self.nav_panel.book_selected.connect(self._on_book_selected); self.nav_panel.range_selected.connect(self._on_range_selected); self.nav_panel.verse_segmentation_changed.connect(self._on_verse_segmentation_changed); splitter.addWidget(self.nav_panel); splitter.addWidget(ScriptureDisplay()); self.scripture_display=splitter.widget(1); splitter.setSizes([330,870]); layout.addWidget(splitter); central.setLayout(layout); self.setCentralWidget(central)
    def _create_shortcuts(self):
        shortcuts=[(Qt.Key.Key_Return,self._show_search),(Qt.Key.Key_Enter,self._show_search),(Qt.Key.Key_F12,self._toggle_extension),(Qt.Key.Key_Right,self._add_verse_end),(Qt.Key.Key_Left,self._remove_verse_end),("Ctrl+Right",self._add_verse_start),("Ctrl+Left",self._remove_verse_start),(Qt.Key.Key_Up,lambda:self._scroll_manual(-30)),(Qt.Key.Key_Down,lambda:self._scroll_manual(30)),(Qt.Key.Key_Space,self._toggle_scroll_pause)]+[(getattr(Qt.Key,f"Key_{i}"),lambda i=i:self._set_speed_hotkey(i)) for i in range(1,7)]
        self._shortcuts=[]
        for key,fn in shortcuts:
            s=QShortcut(QKeySequence(key),self); s.setContext(Qt.ShortcutContext.WindowShortcut); s.activated.connect(fn); self._shortcuts.append(s)
    def _set_speed_hotkey(self,speed): self.toolbar.scroll_slider.setValue(speed); self._on_scroll_speed(speed)
    def _create_statusbar(self): self.status_label=QLabel("按回车键打开搜索"); status=QStatusBar(); status.addWidget(self.status_label); self.setStatusBar(status)
    def _on_settings_changed(self,s): self.settings.update(s); self._apply_settings(s); self.config.save_display_settings(s)
    def _apply_settings(self,s):
        enabled=bool(s.get("verse_segmentation",False)); self.scripture_display.apply_settings(s); self.nav_panel.set_verse_segmentation(enabled)
        if self.extension_window:self.extension_window.apply_settings(s); QApplication.processEvents(); self._sync_extension_scroll()
    def _on_theme_changed(self,t): self.theme=t; self.settings["theme"]=t; self._load_theme_style(); self.config.save_display_settings({"theme":t})
    def _show_search(self):
        if hasattr(self,"search_widget") and self.search_widget.isVisible(): self.search_widget.close(); return
        self.search_widget=SearchWidget(self.db,self); self.search_widget.search_triggered.connect(self._on_search_result); self.search_widget.close_requested.connect(self._close_search); self.search_widget.move(self.mapToGlobal(QPoint(self.width()//2-180,80))); self.search_widget.show(); self.search_widget.search_input.setFocus()
    def _close_search(self):
        if hasattr(self,"search_widget"): self.search_widget.close()
    def _on_search_result(self,p): b,c,s,e=p; self._load_scripture(b,c,s,e); self.nav_panel.add_to_history(b,c,s,e); self._close_search()
    def _on_book_selected(self,b,c): self._load_scripture(b,c,None,None); self.nav_panel.add_to_history(b,c,1,self.db.get_verse_count(b,c))
    def _on_verse_segmentation_changed(self,e): self.settings["verse_segmentation"]=bool(e); self.scripture_display.set_verse_segmentation(bool(e)); QApplication.processEvents(); self._sync_extension_scroll(); self.config.save_display_settings({"verse_segmentation":bool(e)})
    def _on_range_selected(self,b,c,s,e): self._load_scripture(b,c,s,e); self.nav_panel.add_to_history(b,c,s,e)
    def _load_scripture(self,b,c,s,e):
        self.current_book=b; self.current_chapter=c; self.current_start=s; self.current_end=e; v=self.db.get_verse_range(b,c,1) if s is None else self.db.get_verse_range(b,c,s,e); self.current_start=1 if s is None else s; self.current_end=(v[-1][0] if v else 0) if s is None or e is None else e; self.verses=v; self.scripture_display.set_scripture(b,c,self.current_start,self.current_end,v)
        if self.extension_window and self.extension_window.isVisible(): QApplication.processEvents(); self.extension_window.update_scripture(b,c,self.current_start,self.current_end,v); QApplication.processEvents(); self._sync_extension_scroll()
        self._update_status()
    def _update_status(self): self.status_label.setText(f"{self.current_book} {self.current_chapter}:{self.current_start}-{self.current_end}" if self.current_book else "按回车键打开搜索")
    def _toggle_extension(self):
        if self.extension_window and self.extension_window.isVisible():
            self.extension_window.hide(); self.scripture_display.clear_reference_size(); self.toolbar.set_extend_active(False); return
        self._show_extension()
    def _show_extension(self):
        screens=QApplication.screens()
        if len(screens)<2: self.status_label.setText("未检测到第二块屏幕"); return
        if not self.extension_window:self.extension_window=ExtensionWindow(); self.extension_window.apply_settings(self.settings)
        geom=screens[1].geometry();
        # 扩展模式下，主屏和扩展屏统一使用第二屏的实际分辨率作为经文排版基准。
        # 不改变主窗口尺寸，避免破坏左侧导航和工具栏；只统一经文内容的有效显示尺寸/换行计算。
        self.scripture_display.set_reference_size(geom.width(),geom.height())
        self.extension_window.scripture_display.set_reference_size(geom.width(),geom.height())
        self.extension_window.setGeometry(geom); self.extension_window.showFullScreen();
        if self.verses:self.extension_window.update_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses)
        self.extension_window.set_scroll_speed(0); QApplication.processEvents(); self._sync_extension_scroll(); self.toolbar.set_extend_active(True); self.status_label.setText(f"扩展显示: 屏幕2 ({geom.width()}x{geom.height()})，主屏排版基准已锁定")
    def _toggle_extension_topmost(self,on):
        if self.extension_window and self.extension_window.isVisible(): self.extension_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,on); self.extension_window.show()
        self.config.save_display_settings({"extension_topmost":on})
    def _on_scroll_speed(self,speed): self.scripture_display.set_scroll_speed(speed); self.extension_window.set_scroll_speed(0) if self.extension_window and self.extension_window.isVisible() else None
    def _scroll_manual(self,delta): self.scripture_display.scroll_by(delta)
    def _toggle_scroll_pause(self):
        slider=self.toolbar.scroll_slider
        if slider.value()>0:self._last_speed=slider.value(); slider.setValue(0)
        else:slider.setValue(getattr(self,"_last_speed",3))
    def _add_verse_end(self):
        if self.verses and self.current_end<self.db.get_verse_count(self.current_book,self.current_chapter): self.current_end+=1; self.verses=self.db.get_verse_range(self.current_book,self.current_chapter,self.current_start,self.current_end); self._refresh_display()
    def _remove_verse_end(self):
        if len(self.verses)>1:self.current_end-=1; self.verses.pop(); self._refresh_display()
    def _add_verse_start(self):
        if self.verses and self.current_start>1:self.current_start-=1; self.verses=self.db.get_verse_range(self.current_book,self.current_chapter,self.current_start,self.current_end); self._refresh_display()
    def _remove_verse_start(self):
        if len(self.verses)>1:self.current_start+=1; self.verses.pop(0); self._refresh_display()
    def _refresh_display(self):
        self.scripture_display.set_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses)
        if self.extension_window and self.extension_window.isVisible():self.extension_window.update_scripture(self.current_book,self.current_chapter,self.current_start,self.current_end,self.verses); QApplication.processEvents(); self._sync_extension_scroll()
        self._update_status()
    def _sync_extension_scroll(self,value=None):
        if self._syncing_scroll or not self.extension_window or not self.extension_window.isVisible(): return
        self._syncing_scroll=True
        try:
            # 主屏是唯一滚动源；每次主屏滚动都把实际滚动比例映射到扩展屏。
            self.extension_window.sync_from_main(self.scripture_display)
        finally:
            self._syncing_scroll=False

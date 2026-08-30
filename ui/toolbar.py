# ui/toolbar.py
# 顶部工具栏：速度使用按钮选择
from PyQt6.QtWidgets import QToolBar,QPushButton,QLabel,QDialog,QFormLayout,QGroupBox,QHBoxLayout,QVBoxLayout,QSpinBox,QFontComboBox,QColorDialog,QFileDialog,QLineEdit,QDialogButtonBox
from PyQt6.QtCore import Qt,QSize,pyqtSignal
from PyQt6.QtGui import QFont,QColor

class DisplaySettingsDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent); self.setWindowTitle("显示设置"); self.setMinimumWidth(560); self.settings=dict(settings); self._build_ui(); self._load_settings()
    def _build_ui(self):
        root=QVBoxLayout(self); text_group=QGroupBox("文字设置"); form=QFormLayout(text_group)
        self.font_combo=QFontComboBox(); self.font_size=QSpinBox(); self.font_size.setRange(12,300); self.font_size.setSuffix(" px"); self.font_color_btn=QPushButton("正文颜色")
        self.title_font_combo=QFontComboBox(); self.title_size=QSpinBox(); self.title_size.setRange(12,300); self.title_size.setSuffix(" px"); self.title_color_btn=QPushButton("标题颜色")
        self.verse_font_combo=QFontComboBox(); self.verse_size=QSpinBox(); self.verse_size.setRange(10,200); self.verse_size.setSuffix(" px"); self.verse_color_btn=QPushButton("节号颜色")
        self.footer_font_combo=QFontComboBox(); self.footer_size=QSpinBox(); self.footer_size.setRange(10,100); self.footer_size.setSuffix(" px"); self.footer_color_btn=QPushButton("底注颜色")
        for label,w in [("正文",self.font_combo),("正文字号",self.font_size),("正文字色",self.font_color_btn),("标题字体",self.title_font_combo),("标题字号",self.title_size),("标题颜色",self.title_color_btn),("节号字体",self.verse_font_combo),("节号字号",self.verse_size),("节号颜色",self.verse_color_btn),("底注字体",self.footer_font_combo),("底注字号",self.footer_size),("底注颜色",self.footer_color_btn)]: form.addRow(label,w)
        root.addWidget(text_group)
        layout_group=QGroupBox("布局与底注"); lf=QFormLayout(layout_group); self.line_spacing=QSpinBox(); self.line_spacing.setRange(100,300); self.line_spacing.setSuffix("%"); self.margin=QSpinBox(); self.margin.setRange(0,300); self.margin.setSuffix(" px"); self.footer_height=QSpinBox(); self.footer_height.setRange(20,300); self.footer_height.setSuffix(" px"); self.footer_text=QLineEdit(); self.footer_text.setPlaceholderText("留空则不显示底注")
        for label,w in [("行距",self.line_spacing),("左右边距",self.margin),("底注区域高度",self.footer_height),("底注文字",self.footer_text)]: lf.addRow(label,w)
        root.addWidget(layout_group)
        bg_group=QGroupBox("背景"); bg_layout=QFormLayout(bg_group); self.bg_color_btn=QPushButton("背景颜色"); self.bg_image=QLineEdit(); self.bg_image.setReadOnly(True); bg_choose=QPushButton("选择图片"); bg_clear=QPushButton("清除图片"); bg_row=QHBoxLayout(); bg_row.addWidget(self.bg_image,1); bg_row.addWidget(bg_choose); bg_row.addWidget(bg_clear); bg_layout.addRow("背景颜色",self.bg_color_btn); bg_layout.addRow("背景图片",bg_row); root.addWidget(bg_group)
        bg_choose.clicked.connect(self._choose_bg); bg_clear.clicked.connect(self._clear_bg)
        for key,attr in [("font_color","font_color_btn"),("title_color","title_color_btn"),("verse_num_color","verse_color_btn"),("footer_color","footer_color_btn"),("bg_color","bg_color_btn")]: getattr(self,attr).clicked.connect(lambda checked=False,k=key:self._choose_color(k))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def _set_color_button(self,button,color):
        color=QColor(color); button.setText(color.name()); text="black" if color.lightness()>128 else "white"; button.setStyleSheet(f"background:{color.name()};color:{text};padding:6px 12px;border-radius:4px;")
    def _choose_color(self,key):
        color=QColorDialog.getColor(QColor(self.settings.get(key,"#FFFFFF")),self)
        if color.isValid(): self.settings[key]=color; self._set_color_button(getattr(self,{"font_color":"font_color_btn","title_color":"title_color_btn","verse_num_color":"verse_color_btn","footer_color":"footer_color_btn","bg_color":"bg_color_btn"}[key]),color)
    def _choose_bg(self):
        path,_=QFileDialog.getOpenFileName(self,"选择背景图片","","图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path: self.settings["bg_image"]=path; self.bg_image.setText(path)
    def _clear_bg(self): self.settings["bg_image"]=""; self.bg_image.clear()
    def _load_settings(self):
        s=self.settings; self.font_combo.setCurrentFont(QFont(s.get("font_family","微软雅黑"))); self.font_size.setValue(int(s.get("font_size",24))); self.title_font_combo.setCurrentFont(QFont(s.get("title_font_family","微软雅黑"))); self.title_size.setValue(int(s.get("title_size",36))); self.verse_font_combo.setCurrentFont(QFont(s.get("verse_num_font_family","微软雅黑"))); self.verse_size.setValue(int(s.get("verse_num_size",24))); self.footer_font_combo.setCurrentFont(QFont(s.get("footer_font_family","微软雅黑"))); self.footer_size.setValue(int(s.get("footer_size",14))); self.line_spacing.setValue(int(s.get("line_spacing",160))); self.margin.setValue(int(s.get("margin",60))); self.footer_height.setValue(int(s.get("footer_height",45))); self.footer_text.setText(s.get("footer_text","")); self.bg_image.setText(s.get("bg_image",""))
        for key,attr in [("font_color","font_color_btn"),("title_color","title_color_btn"),("verse_num_color","verse_color_btn"),("footer_color","footer_color_btn"),("bg_color","bg_color_btn")]: self._set_color_button(getattr(self,attr),s.get(key,"#FFFFFF"))
    def get_settings(self):
        s=dict(self.settings); s.update({"font_family":self.font_combo.currentFont().family(),"font_size":self.font_size.value(),"title_font_family":self.title_font_combo.currentFont().family(),"title_size":self.title_size.value(),"verse_num_font_family":self.verse_font_combo.currentFont().family(),"verse_num_size":self.verse_size.value(),"footer_font_family":self.footer_font_combo.currentFont().family(),"footer_size":self.footer_size.value(),"line_spacing":self.line_spacing.value(),"margin":self.margin.value(),"footer_height":self.footer_height.value(),"footer_text":self.footer_text.text(),"bg_image":self.bg_image.text()}); return s

class ToolBarWidget(QToolBar):
    settings_changed=pyqtSignal(dict); scroll_speed_changed=pyqtSignal(int); extend_toggled=pyqtSignal(); footer_triggered=pyqtSignal(); theme_changed=pyqtSignal(str); topmost_toggled=pyqtSignal(bool); scroll_up=pyqtSignal(); scroll_down=pyqtSignal()
    def __init__(self,parent=None):
        super().__init__("主工具栏",parent); self.setMovable(False); self.setIconSize(QSize(18,18)); self.theme="dark"; self.settings={}
        self.extend_btn=QPushButton("扩展显示 (F12)"); self.extend_btn.clicked.connect(self.extend_toggled); self.addWidget(self.extend_btn)
        self.topmost_btn=QPushButton("🔝 置顶"); self.topmost_btn.setCheckable(True); self.topmost_btn.setChecked(True); self.topmost_btn.setEnabled(False); self.topmost_btn.toggled.connect(self.topmost_toggled); self.addWidget(self.topmost_btn)
        self.addSeparator(); self.addWidget(QLabel("滚动:")); up=QPushButton("↑"); up.setFixedWidth(32); up.clicked.connect(self.scroll_up); self.addWidget(up); down=QPushButton("↓"); down.setFixedWidth(32); down.clicked.connect(self.scroll_down); self.addWidget(down)
        self.addWidget(QLabel("速度:")); self.speed_buttons=[]
        for speed,text in [(0,"暂停"),(1,"1档"),(2,"2档"),(3,"3档"),(4,"4档"),(5,"5档"),(6,"6档")]:
            btn=QPushButton(text); btn.setCheckable(True); btn.setAutoExclusive(False); btn.setFixedWidth(42 if speed else 50); btn.clicked.connect(lambda checked=False,s=speed:self._set_speed(s)); self.speed_buttons.append(btn); self.addWidget(btn)
        self.speed_label=QLabel("暂停"); self.speed_label.setFixedWidth(40); self.addWidget(self.speed_label); self._set_speed(0)
        self.addSeparator(); self.settings_btn=QPushButton("⚙ 显示设置"); self.settings_btn.clicked.connect(self._open_settings); self.addWidget(self.settings_btn); self.theme_btn=QPushButton("☀ 亮色"); self.theme_btn.clicked.connect(self._toggle_theme); self.addWidget(self.theme_btn)
    def load_settings(self,settings): self.settings=dict(settings); self.theme=settings.get("theme","dark"); self.topmost_btn.setChecked(settings.get("extension_topmost",True)); self._update_theme_button()
    def _open_settings(self):
        dialog=DisplaySettingsDialog(self.settings,self.window())
        if dialog.exec()==QDialog.DialogCode.Accepted: self.settings=dialog.get_settings(); self.settings_changed.emit(self.settings)
    def _set_speed(self,speed):
        for i,btn in enumerate(self.speed_buttons): btn.setChecked(i==speed)
        names=["暂停","1档","2档","3档","4档","5档","6档"]; self.speed_label.setText(names[speed]); self.scroll_speed_changed.emit(speed)
    def _toggle_theme(self): self.theme="light" if self.theme=="dark" else "dark"; self._update_theme_button(); self.theme_changed.emit(self.theme)
    def _update_theme_button(self): self.theme_btn.setText("🌙 暗色" if self.theme=="light" else "☀ 亮色")
    def set_extend_active(self,active):
        if active: self.extend_btn.setText("关闭扩展 (Esc)"); self.topmost_btn.setEnabled(True)
        else: self.extend_btn.setText("扩展显示 (F12)"); self.topmost_btn.setEnabled(False)

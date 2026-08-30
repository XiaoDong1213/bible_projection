# config.py
# 配置管理模块：自动保存/加载显示设置、窗口状态、搜索历史

import json
import os
import sys
from pathlib import Path
from configparser import ConfigParser
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox


from app_paths import app_dir


class AppConfig:
    def __init__(self):
        self.app_root = app_dir()
        self.mark_file = self.app_root / "install.mark"
        self.is_install_version = self.mark_file.exists()
        # 安装版写入用户可写目录，避免 Program Files 无权限
        if self.is_install_version:
            if sys.platform == "win32":
                base = Path(os.environ.get("APPDATA", str(Path.home())))
            else:
                base = Path.home()
            self.data_dir = base / "bible_projection"
        else:
            self.data_dir = self.app_root
        self.ini_path = self.data_dir / "config.ini"
        self.parser = ConfigParser()
        self._ensure_data_dir()
        self._load_ini()

    def _ensure_data_dir(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            QMessageBox.critical(
                None,
                "权限警告",
                f"目录无写入权限：{self.data_dir}\n本次会话设置无法保存。",
            )

    def _load_ini(self):
        if self.ini_path.exists():
            self.parser.read(self.ini_path, encoding="utf-8")
            if "Display" not in self.parser:
                self._fill_default_config()
            elif "verse_segmentation" not in self.parser["Display"]:
                self.parser["Display"]["verse_segmentation"] = "False"
                self._save_ini()
            if "Window" not in self.parser:
                self.parser["Window"] = {"geometry": ""}
            if "History" not in self.parser:
                self.parser["History"] = {"search_history": "[]"}
        else:
            self._fill_default_config()
            self._save_ini()

    def _fill_default_config(self):
        self.parser.clear()
        self.parser["Display"] = {
            "theme": "dark",
            "font_family": "微软雅黑",
            "font_size": "24",
            "font_color": "#FFFFFF",
            "verse_num_color": "#FFD700",
            "verse_num_size": "16",
            "verse_num_font_family": "微软雅黑",
            "title_color": "#87CEEB",
            "title_size": "20",
            "title_font_family": "微软雅黑",
            "bg_color": "#000000",
            "bg_image": "",
            "line_spacing": "160",
            "margin": "60",
            "footer_text": "",
            "footer_height": "45",
            "footer_size": "14",
            "footer_color": "#AAAAAA",
            "footer_font_family": "微软雅黑",
            "extension_topmost": "True",
            "verse_segmentation": "False",
        }
        self.parser["Window"] = {"geometry": ""}
        self.parser["History"] = {"search_history": "[]"}

    def _save_ini(self):
        try:
            with open(self.ini_path, "w", encoding="utf-8") as f:
                self.parser.write(f)
        except PermissionError:
            QMessageBox.critical(
                None,
                "保存失败",
                f"无法写入配置文件：{self.ini_path}\n权限不足，设置不会保存。",
            )

    def save_display_settings(self, settings):
        if "Display" not in self.parser:
            self._fill_default_config()
        disp_section = self.parser["Display"]
        for key, value in settings.items():
            if isinstance(value, QColor):
                disp_section[key] = value.name()
            elif isinstance(value, bool):
                disp_section[key] = str(value)
            else:
                disp_section[key] = str(value)
        self._save_ini()

    def load_display_settings(self):
        defaults = {
            "theme": "dark",
            "font_family": "微软雅黑",
            "font_size": 24,
            "font_color": "#FFFFFF",
            "verse_num_color": "#FFD700",
            "verse_num_size": 16,
            "verse_num_font_family": "微软雅黑",
            "title_color": "#87CEEB",
            "title_size": 20,
            "title_font_family": "微软雅黑",
            "bg_color": "#000000",
            "bg_image": "",
            "line_spacing": 160,
            "margin": 60,
            "footer_text": "",
            "footer_height": 45,
            "footer_size": 14,
            "footer_color": "#AAAAAA",
            "footer_font_family": "微软雅黑",
            "extension_topmost": True,
            "verse_segmentation": False,
        }
        result = {}
        sec = self.parser["Display"] if "Display" in self.parser else {}
        color_keys = {"font_color", "verse_num_color", "title_color", "bg_color", "footer_color"}
        bool_keys = {"extension_topmost", "verse_segmentation"}
        int_keys = {
            "font_size",
            "verse_num_size",
            "title_size",
            "line_spacing",
            "margin",
            "footer_height",
            "footer_size",
        }

        for k, default_val in defaults.items():
            raw = sec.get(k, None) if hasattr(sec, "get") else None
            if raw is None:
                result[k] = default_val
            elif k in color_keys:
                result[k] = QColor(raw)
            elif k in bool_keys:
                result[k] = raw.strip().lower() in ("true", "1", "yes", "on")
            elif k in int_keys:
                try:
                    result[k] = int(raw)
                except ValueError:
                    result[k] = default_val
            else:
                result[k] = raw
        return result

    def save_window_state(self, geometry):
        import base64

        if "Window" not in self.parser:
            self.parser["Window"] = {"geometry": ""}
        geo_b64 = base64.b64encode(bytes(geometry)).decode("ascii") if geometry else ""
        self.parser["Window"]["geometry"] = geo_b64
        self._save_ini()

    def load_window_state(self):
        import base64

        if "Window" not in self.parser:
            return None
        raw = self.parser["Window"].get("geometry", "")
        if not raw:
            return None
        try:
            return base64.b64decode(raw)
        except Exception:
            return None

    def save_history(self, history_list):
        if "History" not in self.parser:
            self.parser["History"] = {"search_history": "[]"}
        self.parser["History"]["search_history"] = json.dumps(history_list, ensure_ascii=False)
        self._save_ini()

    def load_history(self):
        if "History" not in self.parser:
            return []
        raw = self.parser["History"].get("search_history", "[]")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

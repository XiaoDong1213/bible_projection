# config.py
# 配置管理模块
# 功能：自动保存/加载所有显示设置、窗口状态、搜索历史
# ✨ 修改点：移除QSettings注册表，改用INI本地文件；支持【安装版 / 便携版】双模式
# 规则：存在 install.mark → 安装版；无此文件 → 便携版；所有配置不写入C盘、不写注册表
# 全部配置文件（config.ini）存放于程序根目录，权限不足弹出GUI提示，不静默失败

import json
from pathlib import Path
from configparser import ConfigParser
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox


class AppConfig:
    def __init__(self):
        # 程序脚本所在根目录
        self.app_root = Path(__file__).parent.resolve()
        self.mark_file = self.app_root / "install.mark"
        # 判断模式：标记文件存在 = 安装版；不存在 = 便携版
        self.is_install_version = self.mark_file.exists()

        # 无论安装/便携，所有配置全部存程序目录，绝不写AppData/注册表
        self.data_dir = self.app_root
        self.ini_path = self.data_dir / "config.ini"

        self.parser = ConfigParser()
        # 确保目录存在，捕获权限报错弹窗
        self._ensure_data_dir()
        # 加载ini；文件缺失自动生成默认配置
        self._load_ini()

    def _ensure_data_dir(self):
        """校验数据目录，无权限弹出提示框，程序继续运行但无法保存"""
        try:
            self.data_dir.mkdir(exist_ok=True)
        except PermissionError:
            QMessageBox.critical(
                None,
                "权限警告",
                f"目录无写入权限：{self.data_dir}\n"
                "便携版请不要放在系统保护目录；安装版更换安装路径。\n"
                "本次会话设置无法保存。"
            )

    def _load_ini(self):
        """读取ini；文件不存在则写入默认配置"""
        if self.ini_path.exists():
            self.parser.read(self.ini_path, encoding="utf‑8")
        else:
            self._fill_default_config()
            self._save_ini()

    def _fill_default_config(self):
        """填充默认配置，和旧版QSettings默认项一一对应，保证兼容"""
        self.parser.clear()
        self.parser["Display"] = {
            "theme": "dark",
            "font_family": "微软雅黑",
            "font_size": "24",
            "font_color": "#FFFFFF",
            "verse_num_color": "#FFD700",
            "title_color": "#87CEEB",
            "title_size": "20",
            "bg_color": "#000000",
            "bg_image": "",
            "line_spacing": "160",
            "margin": "60",
            "footer_text": "",
            "footer_height": "45",
            "footer_size": "14",
            "footer_color": "#AAAAAA",
            "extension_topmost": "True"
        }
        self.parser["Window"] = {
            "geometry": ""
        }
        self.parser["History"] = {
            "search_history": "[]"
        }

    def _save_ini(self):
        """持久化写入config.ini，捕获权限异常弹窗"""
        try:
            with open(self.ini_path, "w", encoding="utf‑8") as f:
                self.parser.write(f)
        except PermissionError:
            QMessageBox.critical(
                None,
                "保存失败",
                f"无法写入配置文件：{self.ini_path}\n权限不足，设置不会保存。"
            )

    # ============== 显示设置（对外接口，完全兼容旧接口，上层代码无需改动） ==============
    def save_display_settings(self, settings):
        """
        保存显示设置到本地INI
        :param settings: 配置字典，支持str/int/QColor
        """
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
        """
        加载显示设置，带默认值兜底
        :return: 配置字典（和旧版返回格式完全一致，上层直接使用）
        """
        defaults = {
            "theme": "dark",          # 当前主题 dark/light
            "font_family": "微软雅黑",  # 正文字体
            "font_size": 24,           # 正文字号
            "font_color": "#FFFFFF",   # 正文字色
            "verse_num_color": "#FFD700",  # 节号颜色
            "verse_num_size":16,
            "verse_num_font_family":"微软雅黑",
            "title_color": "#87CEEB",    # 标题颜色
            "title_size": 20,             # 标题字号
            "title_font_family":"微软雅黑",
            "bg_color": "#000000",       # 背景色
            "bg_image": "",              # 背景图路径
            "line_spacing": 160,          # 行距百分比
            "margin": 60,                 # 左右边距
            "footer_text": "",            # 底注文字
            "footer_height": 45,          # 底注高度
            "footer_size": 14,            # 底注字号
            "footer_color": "#AAAAAA",    # 底注颜色
            "footer_font_family":"微软雅黑",
            "extension_topmost": True     # 扩展屏是否置顶
        }

        result = {}
        sec = self.parser["Display"]

        color_keys = {"font_color", "verse_num_color", "title_color", "bg_color", "footer_color"}
        bool_keys = {"extension_topmost"}
        int_keys = {"font_size", "title_size", "line_spacing", "margin", "footer_height", "footer_size"}

        for k, default_val in defaults.items():
            raw = sec.get(k, None)
            if raw is None:
                result[k] = default_val
                continue

            if k in color_keys:
                result[k] = QColor(raw)
            elif k in bool_keys:
                result[k] = (raw.lower() == "true")
            elif k in int_keys:
                try:
                    result[k] = int(raw)
                except ValueError:
                    result[k] = default_val
            else:
                result[k] = raw
        return result

    # ============== 窗口状态 ==============
    def save_window_state(self, geometry):
        """保存窗口二进制几何数据，base64文本存入INI"""
        import base64
        if geometry:
            geo_b64 = base64.b64encode(bytes(geometry)).decode("ascii")
        else:
            geo_b64 = ""
        self.parser["Window"]["geometry"] = geo_b64
        self._save_ini()

    def load_window_state(self):
        """加载窗口大小位置；返回QByteArray原始geometry或None"""
        import base64
        raw = self.parser["Window"].get("geometry", "")
        if not raw:
            return None
        try:
            return base64.b64decode(raw)
        except Exception:
            return None

    # ============== 搜索历史 ==============
    def save_history(self, history_list):
        """保存搜索历史：json字符串写入INI"""
        self.parser["History"]["search_history"] = json.dumps(history_list, ensure_ascii=False)
        self._save_ini()

    def load_history(self):
        """加载搜索历史，解析列表，异常返回空列表"""
        raw = self.parser["History"].get("search_history", "[]")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

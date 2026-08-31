# main.py
# 圣经投影系统 - 程序入口
# 功能：初始化各模块，启动主窗口

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from config import AppConfig
from bible_database import BibleDatabase
from main_window import MainWindow


def main():
    # 创建Qt应用实例
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用Fusion风格，跨平台一致美观

    # 使用项目根目录的 icon.ico 作为应用图标
    icon_path = Path(__file__).resolve().parent / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 1. 初始化配置管理器（负责保存/加载所有设置、历史记录）
    config = AppConfig()

    # 2. 初始化圣经数据库（对接你的数据库文件）
    db = BibleDatabase()

    # 3. 创建主窗口，注入数据库和配置
    window = MainWindow(db, config)
    window.show()

    # 进入事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

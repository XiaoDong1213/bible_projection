# 打包说明

打包脚本已放在项目根目录（与 v1 相同用法）：

| 文件 | 作用 |
|------|------|
| `../build_exe.bat` | 一键 PyInstaller 打 EXE |
| `../Bible Pro.spec` | PyInstaller 配置（资源来自 `resources/`） |
| `../Bible Pro.iss` | Inno Setup 7 安装包 |
| `../file_version_info.txt` | Windows 文件版本信息 |

流程：先运行根目录 `build_exe.bat`，再用 Inno Setup 打开 `Bible Pro.iss` 编译安装包。

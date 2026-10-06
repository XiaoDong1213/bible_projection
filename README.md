# Bible Pro

> 面向教会聚会、礼拜、讲道与查经的 Windows 圣经阅读与双屏投影软件。

Bible Pro 基于 **Python + PyQt6 + SQLite**。主屏负责选经文、控滚动与显示；副屏向投影仪、电视或第二显示器全屏展示经文。

---

## 当前功能

### 经文选择与阅读

- 旧约 / 新约书卷、简称快速定位；章节与起止节、整章或从某节到章末。
- 连续显示或按节分段；方向键调整范围。
- 实际打开过的经文进入历史，可再打开、单条删除、复制标题或清空。

### 快速定位（Enter）

日常投影时用来快速跳到书卷、章、节：

- 书卷简拼逐步匹配，多候选时继续输入或用方向键 / `Space` 选择，`Enter` 确认。
- 支持章节、节号和起止范围；无关字符会被限制。
- 每次打开为空，便于重新输入。

### 经文全文搜索（Ctrl+F）

搜索面板挂在主窗口右侧分割栏，随窗口缩放。

- **相近**（按字顺序，中间可少打）与 **一致**（须连续出现）。
- 空格分词时，同一节须全部命中（例如 `爱 盼望`）。
- 可限定旧约 / 新约 / 指定书卷；结果分页，可定位或直接投影。
- 保留最近搜索，支持单条删除。

### 经文小标题

- 与正文分开设置字体、字号、颜色；工具栏或功能开关启停。
- 主屏与副屏同步。搜索仍以经文正文为准，不把小标题里的交叉引用当成独立结果。

### 双屏投影

- Windows 扩展显示；自动选用非主屏作投影窗口，按副屏尺寸排版。
- 工具栏「扩展显示」：两块屏直接开；三块及以上可从三角菜单选输出屏，并记住上次选择。
- `F12` 开 / 关扩展屏。
- `Esc` 关闭扩展屏。
- 主屏换经文、滚动位置与副屏同步；副屏经文不独立滚动。

### 经文滚动

- 手动、滚轮、自动滚动（`1`～`9` 档速度，`0` 暂停，`Space` 暂停 / 继续）。
- `↑` / `↓` 微调位置；滚到末尾自动停止。

### 显示设置与主题

控制台与投影内容可调：正文 / 标题 / 小标题 / 节号 / 底注的字体、字号与颜色，行距、左右边距、底注高度、背景色或背景图，以及亮色 / 暗色主题。

样式在 `resources/styles/` 与 `ui/themes/`。

---

## 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Enter` | 打开 / 关闭快速定位 |
| `Ctrl + F` | 打开 / 关闭经文全文搜索（右侧栏） |
| `F1` | 快捷键帮助 |
| `F12` | 开 / 关扩展屏 |
| `Esc` | 关闭扩展屏 |
| `←` / `→` | 减少 / 增加结束节 |
| `Ctrl + ←` / `Ctrl + →` | 增加 / 减少起始节 |
| `↑` / `↓` | 手动滚动。搜索：切换候选项 |
| `Space` | 暂停 / 继续自动滚动。搜索：选择候选项 |
| `1` ～ `9` | 自动滚动速度 |
| `0` | 暂停自动滚动 |

焦点在搜索框、数字框等输入控件时，按键先交给当前控件。

---

## 功能开关

独立功能由 `app/feature_flags.py` 控制，不必删模块代码：

```python
ENABLE_SCRIPTURE_SEARCH = True   # 经文全文搜索（Ctrl+F）
ENABLE_SCRIPTURE_TITLES = True   # 经文小标题
ENABLE_SERMON = False            # 讲篇编辑与放映（本发行关闭）
```

关掉后对应工具栏入口、帮助项与相关设置项不会出现。

---

## 技术架构

| 技术 | 用途 |
| --- | --- |
| Python | 应用主体 |
| PyQt6 | 桌面界面与扩展屏 |
| SQLite | 经文与书卷数据 |
| QTextDocument | 经文排版 |
| QSS | 亮色 / 暗色主题 |
| PyInstaller | Windows EXE |
| Inno Setup 7 | 安装程序 |

`app` 负责启动与开关，`core` 负责配置 / 数据库 / 选择模型，`ui` 负责界面，`resources` 为只读资源，`tests` 为单测。

---

## 项目结构

```text
bible_projection/
├── main.py                         # 入口（转调 app.main）
├── tests/
├── requirements.txt
├── app/                            # 启动、启动页、功能开关
├── core/                           # 配置、数据库、选择模型
├── ui/                             # 主窗口、经文显示、搜索、工具栏、主题
├── resources/                      # 经文库、图标、QSS
├── Bible Pro.spec                  # PyInstaller
├── build_exe.bat
├── Bible Pro.iss                   # Inno Setup 7
├── file_version_info.txt
├── LICENSE
└── README.md
```

---

## 从源码运行

- Windows，Python 3.10+，PyQt6

```bash
pip install -r requirements.txt
python main.py
```

也可 `python -m app.main`。需能访问 `resources/` 中的经文库。

开发时配置在项目根目录 `config.ini`。安装版数据在 `%APPDATA%\bible_projection\`。

单测：

```bash
python -m pytest tests -q
```

---

## Windows 打包

根目录运行 `build_exe.bat`，产物一般在：

```text
dist/Bible Pro/Bible Pro.exe
```

用户配置、历史和窗口状态不应打进安装包。`build_exe.bat` 会尽量去掉 `dist` 里的个人配置。

安装程序用 Inno Setup 7 打开 `Bible Pro.iss`：先打包 EXE，确认能运行，再编译，安装包在 `dist_installer/Bible Pro_Setup.exe`。

---

## 使用流程

**投影经文**

1. 接好第二块屏，Windows 选择「扩展这些显示器」。
2. 主屏选好经文，点「扩展显示」或 `F12` 开扩展屏（三块及以上可从三角菜单选屏）。
3. 主屏换经文或滚动，副屏同步。`Esc` 关扩展。

**全文搜索**

`Ctrl + F` 打开面板，选相近 / 一致与书卷范围，从结果定位或投影。

---

## 版权与许可

代码采用 **MIT License**。贡献者：XiaoDong、JiangRTTTR。

```text
Copyright © 2026 XiaoDong and JiangRTTTR
```

详见根目录 `LICENSE`。

《和合本》经文、字体、图标及其他第三方资源版权归权利人所有，不在本项目代码许可证范围内。

---

## 项目定位

面向实际聚会投影：经文操作要快，双屏要稳，搜索要准，主题与 Windows 安装要可用。按使用反馈持续迭代。

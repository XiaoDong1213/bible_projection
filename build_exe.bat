@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo        Bible Pro Windows 打包工具
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python。
    pause
    exit /b 1
)

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [提示] 正在安装 PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败。
        pause
        exit /b 1
    )
)

echo [1/3] 清理旧的打包文件...
if exist build rmdir /s /q build
if exist "dist\Bible Pro" rmdir /s /q "dist\Bible Pro"
if exist "installer\Bible Pro_Setup.exe" del /q "installer\Bible Pro_Setup.exe"
if not exist installer mkdir installer

echo [2/3] 正在打包 Bible Pro...
python -m PyInstaller --noconfirm --clean "Bible Pro.spec"
if errorlevel 1 (
    echo.
    echo [错误] PyInstaller 打包失败。
    pause
    exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo.
    echo [错误] 未找到 Inno Setup 6。
    echo 请先安装 Inno Setup，然后重新运行本脚本。
    echo.
    echo 官方网站：https://jrsoftware.org/isinfo.php
    pause
    exit /b 1
)

echo [3/3] 正在生成安装程序...
"%ISCC%" "Bible Pro.iss"
if errorlevel 1 (
    echo.
    echo [错误] 安装程序生成失败。
    pause
    exit /b 1
)

echo.
echo ========================================
echo       Bible Pro 打包完成！
echo ========================================
echo.
echo 安装程序：
 echo %CD%\installer\Bible Pro_Setup.exe
echo.
pause
endlocal

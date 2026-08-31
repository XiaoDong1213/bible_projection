@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo          Bible Pro Build Tool
echo ========================================
echo.

set "PYTHON=D:\Python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

"%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller installation failed.
        pause
        exit /b 1
    )
)

echo [1/3] Cleaning old build files...
if exist build rmdir /s /q build
if exist "dist\Bible Pro" rmdir /s /q "dist\Bible Pro"
if exist "installer\Bible Pro_Setup.exe" del /q "installer\Bible Pro_Setup.exe"
if not exist installer mkdir installer

echo [2/3] Building Bible Pro...
"%PYTHON%" -m PyInstaller --noconfirm --clean "Bible Pro.spec"
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo [ERROR] Inno Setup 6 not found.
    echo Please install Inno Setup and run this script again.
    pause
    exit /b 1
)

echo [3/3] Creating installer...
"%ISCC%" "Bible Pro.iss"
if errorlevel 1 (
    echo [ERROR] Installer creation failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo       Bible Pro build completed!
echo ========================================
echo.
echo Installer:
echo %CD%\installer\Bible Pro_Setup.exe
echo.
pause
endlocal

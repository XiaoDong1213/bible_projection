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

echo [1/2] Cleaning old build files...
if exist build rmdir /s /q build
if exist "dist\Bible Pro" rmdir /s /q "dist\Bible Pro"
if not exist dist mkdir dist

echo [2/2] Building Bible Pro...
"%PYTHON%" -m PyInstaller --noconfirm --clean "Bible Pro.spec"
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo       Bible Pro build completed!
echo ========================================
echo.
echo EXE folder:
echo %CD%\dist\Bible Pro\
echo.
echo Open Inno Setup 7 to create the installer.
echo.
pause
endlocal

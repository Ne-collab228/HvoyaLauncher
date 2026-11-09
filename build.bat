@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python -m pip install -q pyinstaller
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name HvoyaLauncher --icon ui\icon.ico ^
  --add-data "ui;ui" --collect-data minecraft_launcher_lib main.py || exit /b 1
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
"%ISCC%" /Q installer.iss || exit /b 1
echo.
echo Готово: dist\HvoyaLauncher.exe и установщик dist\HvoyaLauncher-Setup-*.exe

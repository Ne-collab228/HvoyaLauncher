@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python -m pip install -q pyinstaller
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name HvoyaLauncher --icon ui\icon.ico ^
  --add-data "ui;ui" --collect-data minecraft_launcher_lib main.py
echo.
echo Готово: dist\HvoyaLauncher.exe
pause

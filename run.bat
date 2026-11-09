@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Первая настройка: создаю окружение Python...
  python -m venv .venv || (echo Нужен Python 3.10+ с python.org & pause & exit /b 1)
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
start "" .venv\Scripts\pythonw.exe main.py

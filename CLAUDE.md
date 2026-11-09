# Hvoya Launcher — заметки для разработки

Лёгкий лаунчер Minecraft (офлайн + Ely.by, Modrinth + CurseForge). Интерфейс по мотивам PineconeMC/Prism. Весь UI на русском.

## Стек
- Python 3.13, venv в `.venv` (`requirements.txt`: minecraft-launcher-lib 8.0, pywebview 6, requests; для сборки ещё pyinstaller, pillow).
- pywebview (WebView2) + чистый HTML/CSS/JS без фреймворков в `ui/`.
- `main.py` — окно, одна копия (mutex), свободный порт для встроенного http-сервера.

## Структура
- `launcher/util.py` — пути (`data/` рядом с exe, иначе %APPDATA%), JSON, HTTP-сессия, загрузки. **Патчит `requests.Session.request`: таймаут по умолчанию** (mll качает без таймаута и зависал навсегда).
- `launcher/events.py` — события в JS (`window.hvEvent`), фоновые задачи `run_task` с прогрессом.
- `launcher/accounts.py` — офлайн (UUID как у offline-mode сервера) и Ely.by (authserver.ely.by, 2FA через `пароль:код`), authlib-injector.
- `launcher/instances.py` — сборки: `data/instances/<id>/instance.json` + `.minecraft/`.
- `launcher/game.py` — установка версии/загрузчика (mll, до 20 повторов при сетевых ошибках), запуск, логи, kill.
- `launcher/sources.py` — Modrinth API v2 и CurseForge (без ключа через `api.curse.tools`, он умеет только GET; с ключом — официальный API).
- `launcher/content.py` — моды/ресурспаки/шейдеры в сборке, зависимости, обновления по sha1 (Modrinth), модпаки (.mrpack и CF .zip).
- `launcher/storage.py` — подсчёт места, что используется сборками, очистка; `version_ready()` проверяет версию + Java + индекс ассетов.
- `launcher/importer.py` — импорт из Prism/MultiMC/PineconeMC(ElyPrism), CurseForge, Modrinth App (app.db), ATLauncher, TLauncher/.minecraft.
- `launcher/api.py` — все методы для JS; ответы `{ok, data}` / `{ok:false, error}`.
- `ui/app.js` — основной UI; `ui/extra.js` — Хранилище и импорт из лаунчеров; `ui/icons.js` — SVG и пиксельные иконки.

## Общие файлы
`data/minecraft/` (versions, libraries, assets, runtime) общие для всех сборок; у каждой сборки свой `.minecraft`.

## Сборка и релиз
- `run.bat` — запуск из исходников; `python main.py --debug` — с DevTools.
- `build.bat` — PyInstaller (`dist/HvoyaLauncher.exe`) + Inno Setup 6 (`installer.iss` → `dist/HvoyaLauncher-Setup-<ver>.exe`).
- Версию менять в двух местах: `launcher/util.py` (`APP_VERSION`) и `installer.iss` (`AppVersion`).
- Релиз: `gh release create vX.Y dist/HvoyaLauncher-Setup-X.Y.exe dist/HvoyaLauncher.exe --title ... --notes-file ...`.

## Грабли
- pywebview с `private_mode=False` всегда берёт порт 42001 → вторая копия получает ошибку Edge/серый экран. Поэтому `http_port=_free_port()` и mutex.
- Не держать в `Api` публичных атрибутов-объектов: pywebview обходит их рекурсивно (окно хранится в `_window`).
- Установщики Forge/Fabric запускают java — в `game.py` подавлено консольное окно (`CREATE_NO_WINDOW`).
- Скриншот окна для проверки — через `PrintWindow` (флаг 2), а не `CopyFromScreen`.

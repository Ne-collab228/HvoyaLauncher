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
- `launcher/elyproxy.py` — локальный прокси Ely.by для authlib-injector (`-javaagent:...=http://127.0.0.1:порт`): параллельные повторы, кэш профилей на диске, без заголовка ALI. При запуске заранее кладёт свой скин в `assets/skins/xx/sha1(utf16le(имя))` — игра запрашивает профиль/скин один раз и при таймауте остаётся без скина до перезапуска. Работает, пока открыт лаунчер.
- `launcher/instances.py` — сборки: `data/instances/<id>/instance.json` + `.minecraft/`.
- `launcher/game.py` — установка версии/загрузчика (mll, до 20 повторов при сетевых ошибках), запуск, логи, kill. **Подменяет `download_file` и `get_requests_response_cache` во всех модулях mll на версии с повтором (до 10 раз на файл).**
- `launcher/sources.py` — Modrinth API v2 и CurseForge (без ключа через `api.curse.tools`, он умеет только GET; с ключом — официальный API).
- `launcher/content.py` — моды/ресурспаки/шейдеры в сборке, зависимости, обновления по sha1 (Modrinth), модпаки (.mrpack и CF .zip).
- `launcher/storage.py` — подсчёт места, что используется сборками, очистка; `version_ready()` проверяет версию + Java + индекс ассетов.
- `launcher/importer.py` — импорт из Prism/MultiMC/PineconeMC(ElyPrism), CurseForge, Modrinth App (app.db), ATLauncher, TLauncher/.minecraft.
- `launcher/updater.py` — самообновление: GitHub releases/latest (при лимите API — тег из редиректа страницы), замена exe через переименование в .old и перезапуск с `--after-update` (main.py ждёт mutex старой копии); если папка без записи — тихий запуск установщика.
- `launcher/worlds.py` — миры (чтение level.dat своим NBT-парсером), бэкапы в `data/backups/<id>/*.zip` (переживают удаление сборки; `session.lock` пропускается — его держит игра), восстановление/импорт zip под свободным именем, копирование в другую сборку, удаление в Корзину (`util.recycle`).
- `launcher/crash.py` — анализ вылета: журнал запуска + свежий краш-репорт + hs_err; правила для Fabric/Quilt (несовместимый набор, перевод на русский), Forge/NeoForge (Missing mandatory dependencies), дубликатов, Java, памяти, Mixin, OpenGL; статическая проверка mods/ (битые jar, мод под другой загрузчик; универсальные jar через META-INF/services считаются Forge). При вылете `game.py` сам вызывает анализ и шлёт результат в событии `game` (`analysis`), копия в `instances/<id>/last_crash.json`.
- `launcher/export.py` — экспорт в .mrpack (файлы из mods/resourcepacks/shaderpacks ищутся на Modrinth по sha1 → ссылками, остальное в overrides/) и .zip (тот же формат, всё в overrides — ставится без сети и импортируется обратно).
- `launcher/shots.py` — скриншоты; отдаются UI через свой http-сервер на 127.0.0.1 со случайным токеном в пути (base64 для мегабайтных PNG слишком медленно). Копирование в буфер — через PowerShell `Clipboard.SetImage`.
- `launcher/discord.py` — Rich Presence через `\\.\pipe\discord-ipc-N` без библиотек; нужен Application ID в настройках (`discordClientId`), ассет картинки — `logo`.
- `launcher/api.py` — все методы для JS; ответы `{ok, data}` / `{ok:false, error}`.
- `ui/app.js` — основной UI; `ui/extra.js` — Хранилище и импорт из лаунчеров; `ui/more.js` — Миры, Скриншоты, Экспорт, карточка анализа вылета, Discord; `ui/icons.js` — SVG и пиксельные иконки.

## Общие файлы
`data/minecraft/` (versions, libraries, assets, runtime) общие для всех сборок; у каждой сборки свой `.minecraft`.

## Сборка и релиз
- `run.bat` — запуск из исходников; `python main.py --debug` — с DevTools.
- `build.bat` — PyInstaller (`dist/HvoyaLauncher.exe`) + Inno Setup 6 (`installer.iss` → `dist/HvoyaLauncher-Setup-<ver>.exe`).
- Версию менять в двух местах: `launcher/util.py` (`APP_VERSION`) и `installer.iss` (`AppVersion`).
- **В каждый релиз класть файл с именем ровно `HvoyaLauncher.exe`** (по нему работает автообновление) и `HvoyaLauncher-Setup-X.Y.exe`.
- Релиз: `gh release create vX.Y dist/HvoyaLauncher-Setup-X.Y.exe dist/HvoyaLauncher.exe --title ... --notes-file ...`.

## Грабли
- pywebview с `private_mode=False` всегда берёт порт 42001 → вторая копия получает ошибку Edge/серый экран. Поэтому `http_port=_free_port()` и mutex.
- Не держать в `Api` публичных атрибутов-объектов: pywebview обходит их рекурсивно (окно хранится в `_window`).
- Установщики Forge/Fabric запускают java — в `game.py` подавлено консольное окно (`CREATE_NO_WINDOW`).
- mll качает ассеты пулом потоков: одна ошибка роняла всю установку, пул сперва дожидался остальных файлов (прогресс стоял), а повтор с нуля перехешировал всё — на рваной сети выглядело как зависание/«качает заново». Поэтому повтор на уровне файла.
- Скриншот окна для проверки — через `PrintWindow` (флаг 2), а не `CopyFromScreen`. Удобнее: запустить с `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333` и управлять UI/снимать скриншоты через CDP (`Runtime.evaluate`, `Page.captureScreenshot`).

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
- `launcher/optimize.py` — «Ускорить игру»: слоты (рендер Sodium/Embeddium/Rubidium, шейдеры Iris/Oculus, ModernFix, FerriteCore, Lithium/Canary/Radium, EntityCulling, ImmediatelyFast, Dynamic FPS), уже стоящие моды узнаются по id внутри jar (`content.installed_mod_ids`), OptiFine → конфликт.
- `launcher/skins.py` — скины: Ely.by (skinsystem, модель slim из textures), офлайн — свой png в `data/skins/<ник>.png` (+ `.slim`), при запуске копируется в `<game>/CustomSkinLoader/LocalSkin/skins/<ник>.png`. Без мода CustomSkinLoader офлайн-скин в игре не виден (id мода на Fabric — `customskinloader-bootstrap`).
- `launcher/memory.py` — проверка памяти перед запуском (много для системы / мало для числа модов / мало свободно сейчас); отключается настройкой `ramWarnings`.
- Обновление модпака (`content.update_modpack`): модпак хранит список своих файлов (`modpack.files`), старые удаляются, ручные моды/отключённые/options.txt/servers.dat/saves не трогаются, перед обновлением бэкап миров.
- `launcher/playtime.py` — время в игре: общий счётчик/`sessions` в instance.json, по дням в `data/playtime.json` (`days[дата][id]`, игра через полночь делится). `game.py` сохраняет время раз в минуту (событие `playtime` для живого счётчика в UI) и остаток при выходе.
- Обновления контента (`content.check_updates`): моды, ресурспаки, шейдеры; Modrinth по sha1 (`/version_files/update`), файлы с CurseForge, которых нет на Modrinth, — по id проекта из content.json. sha1 кэшируются в content.json (`sha1`), результат полной проверки — в памяти 6 ч, пока не изменились файлы (`cached=True`). UI проверяет сборку в фоне при выборе и показывает счётчики в боковой панели.
- `launcher/share.py` — код сборки `HVOYA1:` + base64url(zlib(json)): версия/загрузчик, id версий Modrinth, пары CF (проект, файл); у сборки из модпака — модпак + добавленное поверх. Ручные файлы ищутся на Modrinth по sha1, остальное — в `skipped`.
- `launcher/looks.py` — свои фоны в `data/backgrounds/`, отдаются через http-сервер shots.py (путь `__bg__`), фон из скриншотов.
- `launcher/api.py` — все методы для JS; ответы `{ok, data}` / `{ok:false, error}`.
- `ui/app.js` — основной UI; `ui/extra.js` — Хранилище и импорт из лаунчеров; `ui/more.js` — Миры, Скриншоты, Экспорт, карточка анализа вылета, Discord; `ui/v15.js` — Ускорить игру, обновление модпака, 3D-скин (`ui/vendor/skinview3d.bundle.js`), окно памяти; `ui/v16.js` — статистика времени, живой счётчик, окно обновлений, сортировка сборок (`instSort` в настройках); `ui/look.js` + `ui/themes.css` — темы (`data-theme` на html; правила без `:root`, чтобы работали в превью), акцент считается в JS, вид списка `data-layout`, фон `#bg` (пиксельные пейзажи рисуются на canvas); `ui/share.js` — код сборки и «Что нового» (`CHANGELOG`, показ по `lastSeenVersion`); `ui/fonts/` — Pixelify Sans (OFL) для темы «Пиксель»; `ui/icons.js` — SVG и пиксельные иконки 8x8 (`PIX`, русские названия в `PIX_NAMES`).

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
- Проверка из исходников, когда открыт установленный лаунчер: mutex не пустит вторую копию — запускать через обёртку, где `main._single_instance = lambda: True`.
- `el.append(null)` вставляет текст «null», а массив — строкой: передавать элементы через `...arr.filter(Boolean)`.
- Скриншот окна для проверки — через `PrintWindow` (флаг 2), а не `CopyFromScreen`. Удобнее: запустить с `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333` и управлять UI/снимать скриншоты через CDP (`Runtime.evaluate`, `Page.captureScreenshot`).

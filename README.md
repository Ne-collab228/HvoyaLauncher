# Hvoya Launcher

Лёгкий лаунчер Minecraft: офлайн и Ely.by аккаунты, моды/ресурспаки/шейдеры/модпаки с Modrinth и CurseForge.

## Запуск
- `HvoyaLauncher-Setup-1.2.exe` — установщик: выбор папки (по умолчанию `C:\HvoyaLauncher`), ярлыки, удаление через «Приложения».
- `HvoyaLauncher.exe` — портативная версия без установки. Всё хранится рядом, в папке `data\`.
- `run.bat` — запуск из исходников (нужен Python 3.10+).
- `build.bat` — собрать exe и установщик (результат в `dist\`, нужен Inno Setup 6).

## Папки
```
data\
  minecraft\     общие файлы: версии, библиотеки, ассеты, Java от Mojang
  instances\<сборка>\
     instance.json  настройки сборки
     .minecraft\    отдельная игровая папка: mods, saves, config, resourcepacks…
  accounts.json  аккаунты (для Ely.by хранится только токен)
  settings.json  настройки лаунчера
```

## Возможности
- Загрузчики: Vanilla, Fabric, Forge, NeoForge, Quilt (любая версия).
- Java скачивается автоматически под нужную версию игры.
- Моды из Modrinth и CurseForge с автоустановкой зависимостей, включение/выключение, проверка обновлений.
- Модпаки: установка из каталога или импорт `.mrpack` / CurseForge `.zip`.
- Ely.by через authlib-injector (скины, серверы с Ely.by авторизацией), поддержка 2FA.
- Журнал игры в реальном времени, учёт времени в игре, группы, иконки, копирование сборок.
- Импорт сборок из других лаунчеров: Prism / MultiMC / PineconeMC, CurseForge, Modrinth App, ATLauncher, TLauncher, любая `.minecraft`.
- Хранилище: сколько места занимает каждая сборка, версия и Java; очистка неиспользуемого.
- CurseForge работает без ключа через публичный прокси; свой ключ можно указать в настройках.

## Лицензия

MIT — см. [LICENSE](LICENSE).

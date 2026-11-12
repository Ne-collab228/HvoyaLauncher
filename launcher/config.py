"""Глобальные настройки лаунчера."""
import os
import threading

from . import util
from .util import DATA, read_json, total_ram_mb, write_json

PATH = os.path.join(DATA, "settings.json")
_lock = threading.Lock()


def _default_ram():
    total = total_ram_mb()
    if total >= 16000:
        return 6144
    if total >= 8000:
        return 4096
    return 2048


DEFAULTS = {
    "ramMax": None,           # МБ, None → вычислить
    "ramMin": 512,
    "javaPath": "",           # пусто → Java от Mojang скачивается автоматически
    "jvmArgs": "-XX:+UseG1GC -XX:+UnlockExperimentalVMOptions -XX:G1NewSizePercent=20 "
               "-XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M",
    "width": 1280,
    "height": 720,
    "afterLaunch": "minimize",  # minimize | keep | close
    "cfApiKey": "",
    "showSnapshots": False,
    "openLogOnCrash": True,
    "checkUpdates": True,
    "autoInstallUpdates": False,  # сам скачивать и ставить обновления лаунчера (не во время игры)
    "discordRpc": True,
    "ramWarnings": True,      # предупреждать о неудачном количестве памяти перед запуском
    "instSort": "name",       # name | recent | playtime | created
    "theme": "hvoya",         # см. ui/look.js THEMES
    "accent": "",             # пусто — цвет темы
    "layout": "tiles",        # tiles | list | cards
    "bg": {"kind": "none", "value": "", "blur": 0, "dim": 35},  # none | preset | image
    "sidePos": "right",
    "compactToolbar": False,
    "uiScale": 100,
    "lastSeenVersion": "",    # для окна «Что нового»
    "mirror": "auto",         # auto | always | off — зеркала при недоступных серверах (см. mirror.py)
    "discordClientId": "",    # пусто → встроенное приложение Hvoya Launcher (discord.APP_ID)
}


def load():
    with _lock:
        data = dict(DEFAULTS)
        data.update(read_json(PATH, {}) or {})
        if not data.get("ramMax"):
            data["ramMax"] = _default_ram()
        util.MIRROR_MODE = data.get("mirror") if data.get("mirror") in ("auto", "always", "off") else "auto"
        return data


def save(values):
    with _lock:
        data = dict(DEFAULTS)
        data.update(read_json(PATH, {}) or {})
        for k, v in values.items():
            if k in DEFAULTS:
                data[k] = v
        write_json(PATH, data)
    return load()

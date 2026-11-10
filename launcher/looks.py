"""Оформление: свои картинки для фона (data/backgrounds/), выбор из скриншотов."""
import os
import re
import shutil
import time
from urllib.parse import quote

from . import instances, shots
from .util import DATA, INSTANCES, recycle, safe_join

BG_DIR = os.path.join(DATA, "backgrounds")
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _url(name):
    p = os.path.join(BG_DIR, name)
    return f"{shots._base_url()}/__bg__/{quote(name)}?v={int(os.path.getmtime(p))}"  # noqa: SLF001


def list_backgrounds():
    os.makedirs(BG_DIR, exist_ok=True)
    items = [n for n in os.listdir(BG_DIR) if n.lower().endswith(EXTS)]
    items.sort(key=lambda n: -os.path.getmtime(os.path.join(BG_DIR, n)))
    return [{"name": n, "url": _url(n)} for n in items]


def _free_name(name):
    base, ext = os.path.splitext(os.path.basename(name))
    base = re.sub(r'[\\/:*?"<>|]+', "_", base).strip(" .") or "фон"
    cand, i = base + ext.lower(), 2
    while os.path.exists(os.path.join(BG_DIR, cand)):
        cand = f"{base}_{i}{ext.lower()}"
        i += 1
    return cand


def add(path):
    if not path.lower().endswith(EXTS):
        raise ValueError("Нужна картинка: png, jpg, webp или gif")
    os.makedirs(BG_DIR, exist_ok=True)
    name = _free_name(path)
    shutil.copy2(path, os.path.join(BG_DIR, name))
    os.utime(os.path.join(BG_DIR, name))
    return {"name": name, "url": _url(name)}


def remove(name):
    recycle(safe_join(BG_DIR, name))
    return list_backgrounds()


def url_of(name):
    p = safe_join(BG_DIR, name)
    return _url(name) if os.path.isfile(p) else None


def recent_screenshots(limit=60):
    out = []
    for inst_id in os.listdir(INSTANCES):
        if not os.path.isfile(os.path.join(INSTANCES, inst_id, "instance.json")):
            continue
        try:
            name = instances.get(inst_id)["name"]
            for s in shots.list_shots(inst_id):
                out.append({**s, "inst": inst_id, "instName": name})
        except Exception:  # noqa: BLE001
            continue
    out.sort(key=lambda s: -s["time"])
    return out[:limit]


def from_screenshot(inst_id, name):
    src = safe_join(shots._dir(inst_id), name)  # noqa: SLF001
    os.makedirs(BG_DIR, exist_ok=True)
    dst = _free_name(f"{instances.get(inst_id)['name']} {time.strftime('%Y-%m-%d')}{os.path.splitext(name)[1]}")
    shutil.copy2(src, os.path.join(BG_DIR, dst))
    os.utime(os.path.join(BG_DIR, dst))
    return {"name": dst, "url": _url(dst)}

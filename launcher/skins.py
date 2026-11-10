"""Скины аккаунтов: Ely.by (skinsystem) и свой файл для офлайн-аккаунтов.

Офлайн-скин в игре виден только с модом CustomSkinLoader: при запуске копируем png в
<game>/CustomSkinLoader/LocalSkin/skins/<ник>.png (загрузчик LocalSkin есть в его конфиге по умолчанию).
"""
import base64
import os
import shutil
import struct

from . import content
from .util import DATA, http

SKINS = os.path.join(DATA, "skins")
CSL_ID = "customskinloader"
CSL_SLUG = "customskinloader"


def _png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("Это не PNG-файл")
    return struct.unpack(">II", data[16:24])


def _data_url(data):
    return "data:image/png;base64," + base64.b64encode(data).decode()


def offline_path(name):
    return os.path.join(SKINS, name.lower() + ".png")


def offline_skin(name):
    p = offline_path(name)
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return f.read()


def model_path(name):
    return offline_path(name)[:-4] + ".slim"


def set_offline(name, src, slim=False):
    with open(src, "rb") as f:
        data = f.read()
    w, hgt = _png_size(data)
    if w % 64 or hgt not in (w, w // 2):
        raise ValueError(f"Скин должен быть 64×64 или 64×32 (или HD кратно 64), а этот {w}×{hgt}")
    os.makedirs(SKINS, exist_ok=True)
    with open(offline_path(name), "wb") as f:
        f.write(data)
    set_model(name, slim)
    return True


def set_model(name, slim):
    mp = model_path(name)
    if slim:
        open(mp, "w").close()
    elif os.path.exists(mp):
        os.remove(mp)


def remove_offline(name):
    for p in (offline_path(name), model_path(name)):
        if os.path.exists(p):
            os.remove(p)
    return True


def get(acc):
    """{'skin': data-url | None, 'slim': bool} для 3D-просмотра."""
    if acc["type"] == "offline":
        data = offline_skin(acc["name"])
        return {"skin": _data_url(data) if data else None, "slim": os.path.exists(model_path(acc["name"])),
                "custom": bool(data)}
    slim = False
    try:  # модель руки (slim/classic) знает только textures-эндпоинт
        t = http().get(f"http://skinsystem.ely.by/textures/{acc['name']}", timeout=(5, 10)).json()
        slim = ((t.get("SKIN") or {}).get("metadata") or {}).get("model") == "slim"
    except Exception:  # noqa: BLE001
        pass
    for _ in range(3):
        try:
            r = http().get(f"http://skinsystem.ely.by/skins/{acc['name']}.png", timeout=(5, 10))
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                return {"skin": _data_url(r.content), "slim": slim}
            break
        except Exception:  # noqa: BLE001
            continue
    return {"skin": None, "slim": slim}


def has_csl(inst_id):
    # на Fabric id мода — customskinloader-bootstrap, на Forge — customskinloader
    return any(i.lower().startswith(CSL_ID) for i in content.installed_mod_ids(inst_id, with_disabled=False))


def prepare_launch(inst_id, gd, acc):
    """Кладёт офлайн-скин для CustomSkinLoader. Возвращает строку для журнала или None."""
    if acc["type"] != "offline":
        return None
    src = offline_path(acc["name"])
    if not os.path.isfile(src):
        return None
    if not has_csl(inst_id):
        return ("[Hvoya] Свой скин задан, но в сборке нет мода CustomSkinLoader — в игре скин не появится. "
                "Установить его можно в окне «Аккаунты» → «Скин».")
    dst_dir = os.path.join(gd, "CustomSkinLoader", "LocalSkin", "skins")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copyfile(src, os.path.join(dst_dir, acc["name"] + ".png"))
    return f"[Hvoya] Офлайн-скин скопирован для CustomSkinLoader ({acc['name']}.png)"

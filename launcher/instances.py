"""Сборки (инстансы). Каждая — в своей папке data/instances/<id>/ с собственной .minecraft."""
import os
import shutil
import threading
import time

from .util import INSTANCES, read_json, slugify, write_json

_lock = threading.Lock()
LOADERS = ("vanilla", "fabric", "forge", "neoforge", "quilt")


def inst_dir(inst_id):
    p = os.path.abspath(os.path.join(INSTANCES, inst_id))
    if os.path.dirname(p) != os.path.abspath(INSTANCES):
        raise ValueError("Неверный id сборки")
    return p


def game_dir(inst_id):
    p = os.path.join(inst_dir(inst_id), ".minecraft")
    os.makedirs(p, exist_ok=True)
    return p


def _json_path(inst_id):
    return os.path.join(inst_dir(inst_id), "instance.json")


def get(inst_id):
    inst = read_json(_json_path(inst_id))
    if not inst:
        raise KeyError(f"Сборка не найдена: {inst_id}")
    inst["id"] = inst_id
    inst["hasIcon"] = os.path.isfile(os.path.join(inst_dir(inst_id), "icon.png"))
    return inst


def save(inst):
    data = {k: v for k, v in inst.items() if k not in ("id", "hasIcon")}
    write_json(_json_path(inst["id"]), data)


def list_all():
    out = []
    for name in os.listdir(INSTANCES):
        if os.path.isfile(os.path.join(INSTANCES, name, "instance.json")):
            try:
                out.append(get(name))
            except (KeyError, ValueError):
                pass
    out.sort(key=lambda i: (i.get("group") or "", i.get("name", "").lower()))
    return out


def _unique_id(name):
    base = slugify(name)
    cand, n = base, 2
    while os.path.exists(os.path.join(INSTANCES, cand)):
        cand = f"{base}_{n}"
        n += 1
    return cand


def create(name, mc, loader="vanilla", loader_version="", group="", icon="grass", extra=None):
    name = (name or "").strip() or f"Minecraft {mc}"
    if loader not in LOADERS:
        raise ValueError(f"Неизвестный загрузчик: {loader}")
    with _lock:
        inst_id = _unique_id(name)
        os.makedirs(os.path.join(INSTANCES, inst_id, ".minecraft"), exist_ok=True)
        inst = {
            "id": inst_id, "name": name, "group": group or "", "mc": mc, "loader": loader,
            "loaderVersion": loader_version or "", "icon": icon, "created": int(time.time()),
            "lastPlayed": 0, "playtime": 0, "ramMax": None, "javaPath": "", "jvmArgs": "",
            "width": None, "height": None, "notes": "", "versionId": "", "installed": False,
        }
        if extra:
            inst.update(extra)
        save(inst)
    return get(inst_id)


ALLOWED_UPDATE = {"name", "group", "mc", "loader", "loaderVersion", "icon", "ramMax", "javaPath",
                  "jvmArgs", "width", "height", "notes", "server"}


def update(inst_id, values):
    with _lock:
        inst = get(inst_id)
        version_changed = any(k in values and values[k] != inst.get(k) for k in ("mc", "loader", "loaderVersion"))
        for k, v in values.items():
            if k in ALLOWED_UPDATE:
                inst[k] = v
        if inst.get("loader") not in LOADERS:
            raise ValueError("Неизвестный загрузчик")
        if version_changed:
            inst["installed"] = False
            inst["versionId"] = ""
        save(inst)
    return get(inst_id)


def delete(inst_id):
    shutil.rmtree(inst_dir(inst_id), ignore_errors=True)


def copy(inst_id, new_name):
    src = get(inst_id)
    with _lock:
        new_id = _unique_id(new_name or src["name"] + " (копия)")
        shutil.copytree(inst_dir(inst_id), os.path.join(INSTANCES, new_id))
    inst = get(new_id)
    inst["name"] = new_name or src["name"] + " (копия)"
    inst["playtime"] = 0
    inst["lastPlayed"] = 0
    save(inst)
    return get(new_id)


def groups():
    return sorted({i.get("group") or "" for i in list_all()} - {""})

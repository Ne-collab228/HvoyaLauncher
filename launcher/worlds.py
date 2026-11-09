"""Миры сборки: список (из level.dat), бэкапы в zip, восстановление, копирование между сборками."""
import base64
import gzip
import io
import os
import shutil
import struct
import time
import zipfile

from . import instances
from .storage import dir_size
from .util import DATA, recycle, safe_join

BACKUPS = os.path.join(DATA, "backups")
GAME_MODES = {0: "Выживание", 1: "Творческий", 2: "Приключение", 3: "Наблюдатель"}


# ---------------------------------------------------------------- NBT (только чтение)
def _nbt_payload(f, tag):
    rd = f.read
    if tag == 1:
        return struct.unpack(">b", rd(1))[0]
    if tag == 2:
        return struct.unpack(">h", rd(2))[0]
    if tag == 3:
        return struct.unpack(">i", rd(4))[0]
    if tag == 4:
        return struct.unpack(">q", rd(8))[0]
    if tag == 5:
        return struct.unpack(">f", rd(4))[0]
    if tag == 6:
        return struct.unpack(">d", rd(8))[0]
    if tag == 7:
        n = struct.unpack(">i", rd(4))[0]
        rd(n)
        return None
    if tag == 8:
        n = struct.unpack(">H", rd(2))[0]
        return rd(n).decode("utf-8", "replace")
    if tag == 9:
        sub, n = struct.unpack(">bi", rd(5))
        return [_nbt_payload(f, sub) for _ in range(max(n, 0))]
    if tag == 10:
        out = {}
        while True:
            t = rd(1)
            if not t or t == b"\x00":
                return out
            n = struct.unpack(">H", rd(2))[0]
            name = rd(n).decode("utf-8", "replace")
            out[name] = _nbt_payload(f, t[0])
    if tag == 11:
        n = struct.unpack(">i", rd(4))[0]
        rd(4 * n)
        return None
    if tag == 12:
        n = struct.unpack(">i", rd(4))[0]
        rd(8 * n)
        return None
    raise ValueError(f"NBT: неизвестный тег {tag}")


def read_nbt(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    f = io.BytesIO(raw)
    tag = f.read(1)[0]
    n = struct.unpack(">H", f.read(2))[0]
    f.read(n)
    return _nbt_payload(f, tag)


# ---------------------------------------------------------------- list
def _saves(inst_id):
    p = os.path.join(instances.game_dir(inst_id), "saves")
    os.makedirs(p, exist_ok=True)
    return p


def _world_info(path):
    folder = os.path.basename(path)
    info = {"folder": folder, "name": folder, "mode": "", "hardcore": False, "cheats": False,
            "version": "", "lastPlayed": int(os.path.getmtime(path)), "seed": None, "icon": None}
    try:
        d = (read_nbt(os.path.join(path, "level.dat")) or {}).get("Data", {})
        info["name"] = d.get("LevelName") or folder
        info["hardcore"] = bool(d.get("hardcore"))
        info["cheats"] = bool(d.get("allowCommands"))
        gm = d.get("GameType")
        info["mode"] = "Хардкор" if info["hardcore"] else GAME_MODES.get(gm, "")
        info["version"] = (d.get("Version") or {}).get("Name", "")
        if d.get("LastPlayed"):
            info["lastPlayed"] = int(d["LastPlayed"] // 1000)
        seed = (d.get("WorldGenSettings") or {}).get("seed", d.get("RandomSeed"))
        info["seed"] = str(seed) if seed is not None else None
    except Exception:  # noqa: BLE001 — битый level.dat не должен ломать список
        info["broken"] = True
    icon = os.path.join(path, "icon.png")
    if os.path.isfile(icon) and os.path.getsize(icon) < 512 * 1024:
        with open(icon, "rb") as fh:
            info["icon"] = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    info["size"] = dir_size(path)
    return info


def list_worlds(inst_id):
    root = _saves(inst_id)
    out = []
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "level.dat")):
            out.append(_world_info(p))
    out.sort(key=lambda w: -w["lastPlayed"])
    return out


def _unique(root, name):
    cand, n = name, 2
    while os.path.exists(os.path.join(root, cand)):
        cand = f"{name} ({n})"
        n += 1
    return cand


def delete_world(inst_id, folder):
    recycle(safe_join(_saves(inst_id), folder))
    return list_worlds(inst_id)


def copy_world(inst_id, folder, target_id):
    src = safe_join(_saves(inst_id), folder)
    dst_root = _saves(target_id)
    name = _unique(dst_root, folder)
    shutil.copytree(src, os.path.join(dst_root, name), ignore=shutil.ignore_patterns("session.lock"))
    return name


# ---------------------------------------------------------------- backups
def backup_dir(inst_id):
    p = os.path.join(BACKUPS, os.path.basename(instances.inst_dir(inst_id)))
    os.makedirs(p, exist_ok=True)
    return p


def backup_world(inst_id, folder, task=None, note=""):
    src = safe_join(_saves(inst_id), folder)
    files = []
    for root, _, names in os.walk(src):
        for n in names:
            if n != "session.lock":  # игра держит его открытым
                files.append(os.path.join(root, n))
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    dest = os.path.join(backup_dir(inst_id), f"{folder}_{stamp}{('_' + note) if note else ''}.zip")
    tmp = dest + ".part"
    if task:
        task.set_max(len(files))
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for i, p in enumerate(files):
                try:
                    z.write(p, os.path.join(folder, os.path.relpath(p, src)))
                except PermissionError:
                    pass  # файл занят игрой — пропускаем, остальное сохраняем
                if task:
                    task.set_progress(i + 1)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return os.path.basename(dest)


def backup_all(inst_id, task=None, note=""):
    done = []
    for w in list_worlds(inst_id):
        if task:
            task.set_status(f"Бэкап мира «{w['name']}»")
        done.append(backup_world(inst_id, w["folder"], task, note))
    return done


def list_backups(inst_id):
    root = backup_dir(inst_id)
    out = []
    for n in os.listdir(root):
        p = os.path.join(root, n)
        if n.endswith(".zip") and os.path.isfile(p):
            st = os.stat(p)
            out.append({"file": n, "size": st.st_size, "time": int(st.st_mtime),
                        "world": _zip_world(p) or n.rsplit("_", 2)[0]})
    out.sort(key=lambda b: -b["time"])
    return out


def _zip_world(path):
    try:
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                parts = n.replace("\\", "/").split("/")
                if len(parts) == 2 and parts[1] == "level.dat":
                    return parts[0]
    except (OSError, zipfile.BadZipFile):
        pass
    return None


def delete_backup(inst_id, name):
    p = safe_join(backup_dir(inst_id), name)
    if os.path.isfile(p):
        os.remove(p)
    return list_backups(inst_id)


def restore_zip(inst_id, path, task=None):
    """Распаковывает мир из zip в saves/ под свободным именем (существующий мир не трогаем)."""
    root = _saves(inst_id)
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        level = sorted((n for n in names if n.replace("\\", "/").split("/")[-1] == "level.dat"),
                       key=lambda n: n.count("/"))
        if not level:
            raise ValueError("В архиве нет мира (не найден level.dat)")
        prefix = level[0][: -len("level.dat")]
        base = prefix.rstrip("/").split("/")[-1] or os.path.splitext(os.path.basename(path))[0]
        target_name = _unique(root, base)
        target = os.path.join(root, target_name)
        members = [n for n in names if n.startswith(prefix)]
        if task:
            task.set_max(len(members))
        for i, n in enumerate(members):
            out = safe_join(target, n[len(prefix):])
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(n) as s, open(out, "wb") as d:
                shutil.copyfileobj(s, d)
            if task:
                task.set_progress(i + 1)
    return target_name


def restore_backup(inst_id, name, task=None):
    return restore_zip(inst_id, safe_join(backup_dir(inst_id), name), task)

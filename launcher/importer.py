"""Импорт сборок из других лаунчеров: Prism/MultiMC/PolyMC/PineconeMC, CurseForge, Modrinth App,
ATLauncher, TLauncher и обычной папки .minecraft."""
import configparser
import os
import re
import shutil
import sqlite3

from . import instances
from .util import read_json

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
HOME = os.path.expanduser("~")

# что не копируем: это общие файлы лаунчера, у нас они свои
SKIP = {"versions", "libraries", "assets", "runtime", "natives", "logs", "crash-reports", "webcache",
        "webcache2", ".fabric", ".mixin.out", "launcher_profiles.json", "launcher_accounts.json",
        "usercache.json", "TlauncherProfiles.json", "tlauncher_profiles.json", "bin", "cache"}

PRISM_DIRS = ["PrismLauncher", "PineconeMC", "ElyPrismLauncher", "PolyMC", "MultiMC", "FjordLauncher"]


# ---------------------------------------------------------------- loader parsing
def _loader_from_version_id(vid, data=None):
    """Пытаемся понять загрузчик по id версии / её json (TLauncher, официальный лаунчер, ATLauncher)."""
    low = vid.lower()
    m = re.search(r"fabric-loader-([\d.]+)-([\w.\-]+)", low)
    if m:
        return "fabric", m.group(1), m.group(2)
    m = re.search(r"quilt-loader-([\w.\-]+?)-(\d[\w.\-]*)$", low)
    if m:
        return "quilt", m.group(1), m.group(2)
    m = re.search(r"neoforge-([\d.]+(?:-beta)?)", low)
    if m:
        return "neoforge", m.group(1), None
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)-forge-?([\d.]+)", low)
    if m:
        return "forge", m.group(2), m.group(1)
    if data:
        libs = " ".join(l.get("name", "") for l in data.get("libraries", []))
        for key, ld, rx in (("net.fabricmc:fabric-loader:", "fabric", r"net\.fabricmc:fabric-loader:([\d.]+)"),
                            ("org.quiltmc:quilt-loader:", "quilt", r"org\.quiltmc:quilt-loader:([\w.\-]+)"),
                            ("net.neoforged", "neoforge", r"net\.neoforged:neoforge:([\w.\-]+)"),
                            ("net.minecraftforge:forge:", "forge", r"net\.minecraftforge:forge:[\d.]+-([\d.]+)")):
            if key in libs:
                m = re.search(rx, libs)
                return ld, m.group(1) if m else "", data.get("inheritsFrom")
    return "vanilla", "", None


def _norm_loader(name):
    n = (name or "").lower()
    for k in ("neoforge", "forge", "fabric", "quilt"):
        if k in n:
            return k
    return "vanilla"


# ---------------------------------------------------------------- detectors
def _prism(folder, source):
    pack = read_json(os.path.join(folder, "mmc-pack.json"))
    if not pack:
        return None
    mc, loader, lv = "", "vanilla", ""
    uids = {"net.fabricmc.fabric-loader": "fabric", "net.minecraftforge": "forge",
            "net.neoforged": "neoforge", "org.quiltmc.quilt-loader": "quilt"}
    for c in pack.get("components", []):
        if c.get("uid") == "net.minecraft":
            mc = c.get("version") or c.get("cachedVersion", "")
        elif c.get("uid") in uids:
            loader, lv = uids[c["uid"]], c.get("version") or c.get("cachedVersion", "")
    name = os.path.basename(folder)
    cfg = os.path.join(folder, "instance.cfg")
    if os.path.isfile(cfg):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            with open(cfg, encoding="utf-8", errors="replace") as f:
                cp.read_string("[x]\n" + f.read())
            name = cp.get("x", "name", fallback=name)
        except configparser.Error:
            pass
    gd = next((os.path.join(folder, d) for d in (".minecraft", "minecraft") if os.path.isdir(os.path.join(folder, d))), None)
    if not mc or not gd:
        return None
    return {"name": name, "mc": mc, "loader": loader, "loaderVersion": lv, "gameDir": gd, "source": source}


def _curseforge(folder):
    d = read_json(os.path.join(folder, "minecraftinstance.json"))
    if not d:
        return None
    bml = d.get("baseModLoader") or {}
    loader, lv = "vanilla", ""
    if bml.get("name"):
        lname, _, lv = bml["name"].partition("-")
        loader = _norm_loader(lname)
    mc = d.get("gameVersion") or bml.get("minecraftVersion", "")
    if not mc:
        return None
    return {"name": d.get("name") or os.path.basename(folder), "mc": mc, "loader": loader, "loaderVersion": lv,
            "gameDir": folder, "source": "CurseForge"}


def _atlauncher(folder):
    d = read_json(os.path.join(folder, "instance.json"))
    if not d or "launcher" not in d:
        return None
    la = d["launcher"]
    lvr = la.get("loaderVersion") or {}
    return {"name": la.get("name") or os.path.basename(folder), "mc": d.get("id", ""),
            "loader": _norm_loader(lvr.get("type")), "loaderVersion": lvr.get("version", ""),
            "gameDir": folder, "source": "ATLauncher"}


def _modrinth_json(folder):
    d = read_json(os.path.join(folder, "profile.json"))
    if not d or "metadata" not in d:
        return None
    md = d["metadata"]
    lv = md.get("loader_version")
    return {"name": md.get("name") or os.path.basename(folder), "mc": md.get("game_version", ""),
            "loader": _norm_loader(md.get("loader")), "loaderVersion": (lv or {}).get("id", "") if isinstance(lv, dict) else (lv or ""),
            "gameDir": folder, "source": "Modrinth App"}


def _minecraft_dir(folder, source):
    """Обычная .minecraft (официальный лаунчер, TLauncher…): по сборке на каждую версию с модами/загрузчиком."""
    vdir = os.path.join(folder, "versions")
    if not (os.path.isdir(os.path.join(folder, "mods")) or os.path.isdir(os.path.join(folder, "saves")) or os.path.isdir(vdir)):
        return []
    out = []
    for vid in sorted(os.listdir(vdir)) if os.path.isdir(vdir) else []:
        data = read_json(os.path.join(vdir, vid, vid + ".json"))
        if not data:
            continue
        loader, lv, mc = _loader_from_version_id(data.get("id", vid), data)
        mc = mc or data.get("inheritsFrom") or (data.get("id") if loader == "vanilla" else "")
        if not mc or not re.match(r"^\d|^[ab]\d|^rd-|^c0|^inf-", mc):
            continue
        out.append({"name": f"{vid}", "mc": mc, "loader": loader, "loaderVersion": lv, "gameDir": folder, "source": source})
    if not out and os.path.isdir(os.path.join(folder, "mods")):
        out.append({"name": os.path.basename(folder), "mc": "", "loader": "vanilla", "loaderVersion": "",
                    "gameDir": folder, "source": source})
    return out


def detect_folder(folder):
    """Определяет, что за папка выбрана, и возвращает список найденных сборок."""
    folder = os.path.abspath(folder)
    for fn in (lambda f: _prism(f, "Prism / MultiMC"), _curseforge, _atlauncher, _modrinth_json):
        r = fn(folder)
        if r:
            return [r]
    found = []
    # папка со списком сборок (instances/, profiles/, Instances/)
    try:
        subs = [os.path.join(folder, d) for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
    except OSError:
        subs = []
    for sub in subs:
        for fn in (lambda f: _prism(f, "Prism / MultiMC"), _curseforge, _atlauncher, _modrinth_json):
            r = fn(sub)
            if r:
                found.append(r)
                break
    if found:
        return found
    return _minecraft_dir(folder, "Папка .minecraft")


def _modrinth_app():
    out = []
    for base in (os.path.join(APPDATA, "ModrinthApp"), os.path.join(APPDATA, "com.modrinth.theseus")):
        prof = os.path.join(base, "profiles")
        if not os.path.isdir(prof):
            continue
        db = os.path.join(base, "app.db")
        if os.path.isfile(db):
            try:
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cols = {r[1] for r in con.execute("PRAGMA table_info(profiles)")}
                lvcol = "mod_loader_version" if "mod_loader_version" in cols else "NULL"
                for path, name, gv, ml, lv in con.execute(
                        f"SELECT path, name, game_version, mod_loader, {lvcol} FROM profiles"):
                    gd = os.path.join(prof, path)
                    if os.path.isdir(gd):
                        out.append({"name": name or path, "mc": gv or "", "loader": _norm_loader(ml),
                                    "loaderVersion": lv or "", "gameDir": gd, "source": "Modrinth App"})
                con.close()
                continue
            except sqlite3.Error:
                pass
        for d in os.listdir(prof):
            r = _modrinth_json(os.path.join(prof, d))
            if r:
                out.append(r)
    return out


def scan_known():
    """Ищет сборки в стандартных местах популярных лаунчеров."""
    out = []
    for name in PRISM_DIRS:
        root = os.path.join(APPDATA, name, "instances")
        if os.path.isdir(root):
            for d in os.listdir(root):
                r = _prism(os.path.join(root, d), name)
                if r:
                    out.append(r)
    cf = os.path.join(HOME, "curseforge", "minecraft", "Instances")
    if os.path.isdir(cf):
        for d in os.listdir(cf):
            r = _curseforge(os.path.join(cf, d))
            if r:
                out.append(r)
    out += _modrinth_app()
    mc = os.path.join(APPDATA, ".minecraft")
    if os.path.isdir(mc):
        out += _minecraft_dir(mc, "TLauncher / официальный (.minecraft)")
    for r in out:
        r["name"] = r["name"].strip() or "Импорт"
    return out


# ---------------------------------------------------------------- import
def _files_to_copy(src):
    items = []
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        if rel_root == ".":
            dirs[:] = [d for d in dirs if d not in SKIP]
            files = [f for f in files if f not in SKIP]
        for f in files:
            items.append(os.path.join(root, f))
    return items


def import_instance(data, task):
    src = data["gameDir"]
    if not os.path.isdir(src):
        raise RuntimeError("Папка сборки не найдена")
    mc = (data.get("mc") or "").strip()
    if not mc:
        raise RuntimeError("Укажите версию Minecraft")
    inst = instances.create(data.get("name") or "Импорт", mc, data.get("loader") or "vanilla",
                            data.get("loaderVersion") or "", data.get("group", ""),
                            extra={"importedFrom": data.get("source", "")})
    dst = instances.game_dir(inst["id"])
    try:
        task.set_status("Подсчёт файлов")
        files = _files_to_copy(src)
        task.set_status(f"Копирование файлов ({len(files)})")
        for i, f in enumerate(files):
            rel = os.path.relpath(f, src)
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            try:
                shutil.copy2(f, target)
            except OSError:
                pass  # заблокированный файл (например, открытый лог) — пропускаем
            if i % 20 == 0 or i == len(files) - 1:
                task.counter(i + 1, len(files))
    except Exception:
        instances.delete(inst["id"])
        raise
    return {"inst": inst["id"]}


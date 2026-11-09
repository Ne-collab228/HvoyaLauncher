"""Экспорт сборки в .mrpack (моды с Modrinth — ссылками) или в .zip (всё внутри архива).

Оба формата — это modrinth.index.json + overrides/, поэтому оба импортируются обратно
(в Hvoya, Prism, Modrinth App); .zip просто не требует интернета при установке.
"""
import hashlib
import json
import os
import zipfile

from . import instances
from .util import http, safe_join

MR = "https://api.modrinth.com/v2"
# что всегда пропускаем — кэш, логи, личные данные
SKIP = {"logs", "crash-reports", ".fabric", ".cache", ".mixin.out", "natives", "assets", "libraries", "versions",
        "usercache.json", "usernamecache.json", "command_history.txt", "launcher_profiles.json", "debug",
        ".connector", "downloads", "webcache", "webcache2", "patchouli_data.json", "realms_persistence.json",
        ".replay_cache", "replay_recordings", "moddata", "local", "quark_options.json.bak"}
DEFAULT_ON = {"mods", "config", "defaultconfigs", "kubejs", "scripts", "resourcepacks", "shaderpacks",
              "global_packs", "openloader", "datapacks", "fancymenu_data", "options.txt"}
LABELS = {"mods": "Моды", "config": "Настройки модов", "resourcepacks": "Ресурспаки", "shaderpacks": "Шейдеры",
          "saves": "Миры", "screenshots": "Скриншоты", "options.txt": "Настройки игры (управление, графика)",
          "servers.dat": "Список серверов", "defaultconfigs": "Настройки модов по умолчанию",
          "kubejs": "KubeJS-скрипты", "schematics": "Схемы", "journeymap": "Карты JourneyMap",
          "xaero": "Карты Xaero", "XaeroWorldMap": "Карта мира Xaero", "XaeroWaypoints": "Метки Xaero"}
LOOKUP_DIRS = ("mods", "resourcepacks", "shaderpacks")
DEP_KEYS = {"fabric": "fabric-loader", "quilt": "quilt-loader", "forge": "forge", "neoforge": "neoforge"}


def _size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    total = 0
    for root, _, names in os.walk(p):
        for n in names:
            try:
                total += os.path.getsize(os.path.join(root, n))
            except OSError:
                pass
    return total


def entries(inst_id):
    gd = instances.game_dir(inst_id)
    out = []
    for n in sorted(os.listdir(gd), key=str.lower):
        if n in SKIP or n.startswith("hs_err") or n.endswith((".log", ".tmp", ".lock")):
            continue
        p = os.path.join(gd, n)
        out.append({"name": n, "label": LABELS.get(n, ""), "dir": os.path.isdir(p), "size": _size(p),
                    "on": n in DEFAULT_ON})
    out.sort(key=lambda e: (not e["on"], not e["dir"], e["name"].lower()))
    return out


def _walk(gd, names):
    """Все файлы выбранных записей: [(абсолютный путь, путь внутри .minecraft с '/')]"""
    files = []
    for n in names:
        p = safe_join(gd, n)
        if os.path.isfile(p):
            files.append((p, n))
        elif os.path.isdir(p):
            for root, dirs, fs in os.walk(p):
                dirs[:] = [d for d in dirs if d not in (".cache", ".index")]
                for f in fs:
                    if f.endswith((".part", ".tmp")) or f == "session.lock":
                        continue
                    ap = os.path.join(root, f)
                    files.append((ap, os.path.relpath(ap, gd).replace("\\", "/")))
    return files


def _hashes(path):
    h1, h512 = hashlib.sha1(), hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h1.update(chunk)
            h512.update(chunk)
    return h1.hexdigest(), h512.hexdigest()


def _modrinth_lookup(sha1s):
    """sha1 -> файл на Modrinth (url, размер, хэши)."""
    found = {}
    sha1s = list(sha1s)
    for i in range(0, len(sha1s), 400):
        part = sha1s[i:i + 400]
        r = http().post(f"{MR}/version_files", json={"hashes": part, "algorithm": "sha1"}, timeout=40)
        r.raise_for_status()
        for h, v in r.json().items():
            for f in v.get("files", []):
                if f.get("hashes", {}).get("sha1") == h:
                    found[h] = f
                    break
    return found


def export(inst_id, dest, opts, task):
    from . import game
    inst = instances.get(inst_id)
    gd = instances.game_dir(inst_id)
    embed_all = opts.get("format") == "zip"
    task.set_status("Сбор файлов")
    files = _walk(gd, opts.get("include") or [])
    if not opts.get("disabled", False):
        files = [f for f in files if not f[1].endswith(".disabled")]

    remote = {}
    if not embed_all:
        cand = [(ap, rel) for ap, rel in files
                if rel.count("/") == 1 and rel.split("/")[0] in LOOKUP_DIRS and rel.endswith((".jar", ".zip"))]
        if cand:
            task.set_status(f"Поиск файлов на Modrinth ({len(cand)})")
            task.set_max(len(cand))
            hashes = {}
            for i, (ap, rel) in enumerate(cand):
                hashes[rel] = _hashes(ap)
                task.set_progress(i + 1)
            try:
                found = _modrinth_lookup({h[0] for h in hashes.values()})
            except Exception as e:  # noqa: BLE001 — без сети просто кладём всё внутрь
                print("modrinth lookup failed", e)
                found = {}
            for ap, rel in cand:
                sha1, sha512 = hashes[rel]
                f = found.get(sha1)
                if f and f.get("url"):
                    remote[rel] = {"path": rel, "hashes": {"sha1": sha1, "sha512": sha512},
                                   "downloads": [f["url"]], "fileSize": os.path.getsize(ap)}

    loader = inst.get("loader", "vanilla")
    deps = {"minecraft": inst["mc"]}
    if loader in DEP_KEYS:
        lv = inst.get("loaderVersion") or (game.loader_versions(loader, inst["mc"]) or [""])[0]
        if lv:
            deps[DEP_KEYS[loader]] = lv
    index = {"formatVersion": 1, "game": "minecraft", "versionId": opts.get("version") or "1.0",
             "name": opts.get("name") or inst["name"], "files": list(remote.values()), "dependencies": deps}
    if opts.get("summary"):
        index["summary"] = opts["summary"]

    local = [(ap, rel) for ap, rel in files if rel not in remote]
    task.set_status("Упаковка")
    task.set_max(len(local))
    tmp = dest + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr("modrinth.index.json", json.dumps(index, ensure_ascii=False, indent=1))
            for i, (ap, rel) in enumerate(local):
                try:
                    z.write(ap, "overrides/" + rel)
                except PermissionError:
                    pass
                task.set_progress(i + 1)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return {"path": dest, "remote": len(remote), "local": len(local), "size": os.path.getsize(dest)}

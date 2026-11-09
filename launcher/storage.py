"""Хранилище: что сколько места занимает и очистка неиспользуемого."""
import os
import shutil

from minecraft_launcher_lib import runtime as mll_runtime

from . import instances
from .util import CACHE, DATA, SHARED, read_json

INST_PARTS = [("mods", "Моды"), ("saves", "Миры"), ("resourcepacks", "Ресурспаки"),
              ("shaderpacks", "Шейдеры"), ("screenshots", "Скриншоты"), ("logs", "Логи и краши")]
LOG_DIRS = ("logs", "crash-reports")


def dir_size(path):
    total = 0
    stack = [path]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def _size(path):
    if os.path.isdir(path):
        return dir_size(path)
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ---------------------------------------------------------------- versions
def version_json(vid):
    return read_json(os.path.join(SHARED, "versions", vid, vid + ".json"))


def merged_json(vid):
    """Версия вместе с родителями (inheritsFrom): нужны assetIndex и javaVersion."""
    out, chain, seen = {}, [], set()
    while vid and vid not in seen:
        seen.add(vid)
        data = version_json(vid)
        if data is None:
            return None, chain
        chain.append(vid)
        for k, v in data.items():
            out.setdefault(k, v)
        vid = data.get("inheritsFrom")
    return out, chain


def version_ready(vid):
    """Версия, её родители и нужная Java на месте — можно запускать без переустановки."""
    if not vid:
        return False
    data, _ = merged_json(vid)
    if data is None:
        return False
    comp = (data.get("javaVersion") or {}).get("component")
    if comp and mll_runtime.get_executable_path(comp, SHARED) is None:
        return False
    idx = (data.get("assetIndex") or {}).get("id")
    if idx and not os.path.isfile(os.path.join(SHARED, "assets", "indexes", idx + ".json")):
        return False
    return True


def _usage():
    """Какие версии / Java / индексы ассетов нужны существующим сборкам."""
    versions, runtimes, indexes = {}, set(), set()
    for inst in instances.list_all():
        vid = inst.get("versionId")
        if not vid:
            continue
        data, chain = merged_json(vid)
        for v in chain:
            versions.setdefault(v, []).append(inst["name"])
        if data:
            comp = (data.get("javaVersion") or {}).get("component")
            if comp:
                runtimes.add(comp)
            idx = (data.get("assetIndex") or {}).get("id")
            if idx:
                indexes.add(idx)
    return versions, runtimes, indexes


def _asset_objects(indexes):
    used = set()
    for idx in indexes:
        data = read_json(os.path.join(SHARED, "assets", "indexes", idx + ".json"), {}) or {}
        for obj in (data.get("objects") or {}).values():
            h = obj.get("hash")
            if h:
                used.add(h)
    return used


def _unused_assets(indexes):
    """[(path, size)] объектов, на которые не ссылается ни одна используемая версия."""
    used = _asset_objects(indexes)
    root = os.path.join(SHARED, "assets", "objects")
    out = []
    if os.path.isdir(root):
        for sub in os.listdir(root):
            d = os.path.join(root, sub)
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                if name not in used:
                    p = os.path.join(d, name)
                    out.append((p, _size(p)))
    return out


# ---------------------------------------------------------------- scan
def scan():
    used_versions, used_runtimes, used_indexes = _usage()

    insts = []
    for inst in instances.list_all():
        gd = instances.game_dir(inst["id"])
        total = dir_size(instances.inst_dir(inst["id"]))
        parts, known = [], 0
        for key, label in INST_PARTS:
            dirs = LOG_DIRS if key == "logs" else (key,)
            s = sum(_size(os.path.join(gd, d)) for d in dirs)
            known += s
            if s:
                parts.append({"key": key, "label": label, "size": s})
        if total - known > 0:
            parts.append({"key": "other", "label": "Прочее (config, кэш модов…)", "size": total - known})
        parts.sort(key=lambda p: -p["size"])
        insts.append({"id": inst["id"], "name": inst["name"], "mc": inst["mc"], "loader": inst["loader"],
                      "size": total, "parts": parts})
    insts.sort(key=lambda i: -i["size"])

    versions = []
    vdir = os.path.join(SHARED, "versions")
    for vid in sorted(os.listdir(vdir)) if os.path.isdir(vdir) else []:
        p = os.path.join(vdir, vid)
        if os.path.isdir(p):
            versions.append({"id": vid, "size": dir_size(p), "usedBy": sorted(set(used_versions.get(vid, [])))})
    versions.sort(key=lambda v: -v["size"])

    runtimes = []
    rdir = os.path.join(SHARED, "runtime")
    for name in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        p = os.path.join(rdir, name)
        if os.path.isdir(p):
            runtimes.append({"id": name, "size": dir_size(p), "used": name in used_runtimes})

    unused_assets = _unused_assets(used_indexes)
    assets_unused = sum(s for _, s in unused_assets)
    shared = {
        "versions": sum(v["size"] for v in versions),
        "libraries": dir_size(os.path.join(SHARED, "libraries")),
        "assets": dir_size(os.path.join(SHARED, "assets")),
        "runtime": sum(r["size"] for r in runtimes),
        "cache": dir_size(CACHE),
    }
    reclaim = (sum(v["size"] for v in versions if not v["usedBy"]) +
               sum(r["size"] for r in runtimes if not r["used"]) + assets_unused + shared["cache"])
    return {
        "instances": insts, "versions": versions, "runtimes": runtimes, "shared": shared,
        "assetsUnused": assets_unused,
        "instancesTotal": sum(i["size"] for i in insts),
        "total": sum(i["size"] for i in insts) + sum(shared.values()),
        "reclaimable": reclaim, "dataDir": DATA,
    }


# ---------------------------------------------------------------- clean
def _rm(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def clean(what, arg=None):
    """what: unused | version | runtime | cache | logs (arg = id сборки)."""
    used_versions, used_runtimes, used_indexes = _usage()
    freed = 0
    if what in ("version", "unused"):
        vdir = os.path.join(SHARED, "versions")
        targets = [arg] if what == "version" else (os.listdir(vdir) if os.path.isdir(vdir) else [])
        for vid in targets:
            if vid in used_versions:
                if what == "version":
                    raise RuntimeError("Версия используется сборками: " + ", ".join(sorted(set(used_versions[vid]))))
                continue
            p = os.path.join(vdir, os.path.basename(vid))
            freed += _size(p)
            _rm(p)
    if what in ("runtime", "unused"):
        rdir = os.path.join(SHARED, "runtime")
        targets = [arg] if what == "runtime" else (os.listdir(rdir) if os.path.isdir(rdir) else [])
        for name in targets:
            if name in used_runtimes:
                if what == "runtime":
                    raise RuntimeError("Эта Java нужна установленным сборкам")
                continue
            p = os.path.join(rdir, os.path.basename(name))
            freed += _size(p)
            _rm(p)
    if what == "unused":
        for p, s in _unused_assets(used_indexes):
            freed += s
            _rm(p)
        idir = os.path.join(SHARED, "assets", "indexes")
        for name in os.listdir(idir) if os.path.isdir(idir) else []:
            if name[:-5] not in used_indexes:
                _rm(os.path.join(idir, name))
    if what in ("cache", "unused"):
        for name in os.listdir(CACHE) if os.path.isdir(CACHE) else []:
            p = os.path.join(CACHE, name)
            freed += _size(p)
            _rm(p)
    if what == "logs":
        gd = instances.game_dir(arg)
        for d in LOG_DIRS:
            p = os.path.join(gd, d)
            freed += _size(p)
            _rm(p)
    return {"freed": freed}

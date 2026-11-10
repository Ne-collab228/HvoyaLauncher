"""Код сборки: короткая строка HVOYA1:..., по которой друг ставит такую же сборку.

Внутри (zlib + base64url) — версия игры, загрузчик и ссылки на файлы:
Modrinth — id версий, CurseForge — пары (проект, файл). Если сборка из модпака,
в код идёт сам модпак и только то, что добавлено поверх него. Файлы, которых нет
ни на Modrinth, ни на CurseForge, в код не попадают (их список показывается).
Конфиги и миры в код не помещаются — для этого есть экспорт в .zip.
"""
import base64
import json
import os
import re
import zlib

from . import content, instances, sources
from .sources import MR
from .util import download_many, get_json, http, safe_join, sha1_file

PREFIX = "HVOYA1:"
KINDS = ("mods", "resourcepacks", "shaderpacks")
SHORT = {"mods": "m", "resourcepacks": "r", "shaderpacks": "s"}
LONG = {v: k for k, v in SHORT.items()}


def _files(gd, kind):
    folder = os.path.join(gd, kind)
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        p = os.path.join(folder, name)
        if os.path.isfile(p) and not name.endswith((".disabled", ".part", ".tmp")) and not name.startswith("."):
            out.append(name)
    return out


# ---------------------------------------------------------------- создание кода
def _mr_by_sha1(hashes):
    """sha1 -> id версии на Modrinth (файлы, добавленные вручную)."""
    out = {}
    for i in range(0, len(hashes), 400):
        r = http().post(f"{MR}/version_files", json={"hashes": hashes[i:i + 400], "algorithm": "sha1"}, timeout=40)
        r.raise_for_status()
        out.update({h: v["id"] for h, v in r.json().items()})
    return out


def make_code(inst_id):
    inst = instances.get(inst_id)
    gd = instances.game_dir(inst_id)
    meta = content.load_meta(inst_id)
    mp = inst.get("modpack") or {}
    pack_files = set(mp.get("files") or []) if mp.get("source") and mp.get("version") else set()

    data = {"n": inst["name"], "v": inst["mc"], "l": inst["loader"], "lv": inst.get("loaderVersion") or "",
            "i": inst.get("icon") or "grass"}
    if pack_files:
        data["p"] = [mp["source"][0], str(mp["project"]), str(mp["version"])]

    mr, cf, unknown, lookup = {}, {}, [], {}
    for kind in KINDS:
        for name in _files(gd, kind):
            rel = f"{kind}/{name}"
            if rel in pack_files:
                continue
            m = meta["files"].get(rel) or {}
            if m.get("source") == "modrinth" and m.get("version"):
                mr.setdefault(SHORT[kind], []).append(m["version"])
            elif m.get("source") == "curseforge" and m.get("version"):
                cf.setdefault(SHORT[kind], []).append([int(m["project"]), int(m["version"])])
            else:
                lookup[sha1_file(os.path.join(gd, kind, name))] = (kind, name)
    if lookup:
        try:
            found = _mr_by_sha1(list(lookup))
        except Exception:  # noqa: BLE001
            found = {}
        for h, (kind, name) in lookup.items():
            if found.get(h):
                mr.setdefault(SHORT[kind], []).append(found[h])
            else:
                unknown.append(f"{kind}/{name}")
    if mr:
        data["mr"] = mr
    if cf:
        data["cf"] = cf
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    code = PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode().rstrip("=")
    count = sum(len(v) for v in mr.values()) + sum(len(v) for v in cf.values())
    return {"code": code, "count": count, "skipped": unknown, "modpack": mp.get("name") if pack_files else None}


# ---------------------------------------------------------------- чтение кода
def decode(code):
    code = re.sub(r"\s+", "", code or "")
    i = code.find(PREFIX)
    if i < 0:
        raise ValueError("Это не код сборки Hvoya (он начинается с HVOYA1:)")
    body = code[i + len(PREFIX):]
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValueError("Код повреждён — скопируйте его целиком") from e
    if not data.get("v") or data.get("l") not in instances.LOADERS:
        raise ValueError("В коде нет версии игры")
    return data


def preview(code):
    d = decode(code)
    out = {"name": d.get("n") or f"Minecraft {d['v']}", "mc": d["v"], "loader": d["l"], "loaderVersion": d.get("lv", ""),
           "icon": d.get("i") or "grass", "counts": {}, "modpack": None}
    for src in ("mr", "cf"):
        for k, items in (d.get(src) or {}).items():
            kind = LONG.get(k)
            if kind:
                out["counts"][kind] = out["counts"].get(kind, 0) + len(items)
    if d.get("p"):
        source = "modrinth" if d["p"][0] == "m" else "curseforge"
        try:
            proj = sources.project(source, d["p"][1])
            out["modpack"] = {"title": proj["title"], "icon": proj["icon"], "source": source}
        except Exception:  # noqa: BLE001
            out["modpack"] = {"title": "модпак", "icon": "", "source": source}
    return out


# ---------------------------------------------------------------- установка
def _mr_bulk(path, ids):
    out = []
    for i in range(0, len(ids), 100):
        out += get_json(f"{MR}/{path}", params={"ids": json.dumps(ids[i:i + 100])})
    return out


def install(code, name, task):
    from . import game
    d = decode(code)
    name = (name or "").strip() or d.get("n") or f"Minecraft {d['v']}"
    if d.get("p"):
        source = "modrinth" if d["p"][0] == "m" else "curseforge"
        task.set_status("Установка модпака")
        inst_id = content.install_modpack(source, d["p"][1], d["p"][2], name, task)["inst"]
    else:
        inst_id = instances.create(name, d["v"], d["l"], d.get("lv", ""), icon=d.get("i") or "grass")["id"]
    try:
        _install_files(inst_id, d, task)
    except Exception:
        if not d.get("p"):
            instances.delete(inst_id)
        raise
    inst = instances.get(inst_id)
    game.ensure_installed(inst, task)
    return {"inst": inst_id}


def _install_files(inst_id, d, task):
    gd = instances.game_dir(inst_id)
    items, metas = [], {}
    task.set_status("Поиск файлов")
    mr = {LONG[k]: v for k, v in (d.get("mr") or {}).items() if k in LONG}
    ids = [vid for v in mr.values() for vid in v]
    if ids:
        versions = {v["id"]: v for v in _mr_bulk("versions", ids)}
        projects = {p["id"]: p for p in _mr_bulk("projects", list({v["project_id"] for v in versions.values()}))}
        for kind, vids in mr.items():
            for vid in vids:
                v = versions.get(vid)
                if not v:
                    continue
                f = next((x for x in v["files"] if x.get("primary")), v["files"][0] if v["files"] else None)
                if not f:
                    continue
                dest = safe_join(os.path.join(gd, kind), f["filename"])
                items.append((f["url"], dest, f["hashes"].get("sha1")))
                p = projects.get(v["project_id"], {})
                metas[f"{kind}/{f['filename']}"] = {"source": "modrinth", "project": v["project_id"], "version": vid,
                                                    "versionName": v.get("version_number"), "title": p.get("title") or f["filename"],
                                                    "icon": p.get("icon_url") or ""}
    cf = {LONG[k]: v for k, v in (d.get("cf") or {}).items() if k in LONG}
    pairs = [(int(p), int(f)) for v in cf.values() for p, f in v]
    if pairs:
        raw = sources.cf_files_bulk(pairs)
        mods = sources.cf_mods_bulk(list({p for p, _ in pairs}))
        for kind, lst in cf.items():
            for pid, fid in lst:
                f = raw.get(int(fid))
                if not f:
                    continue
                v = sources._cf_version(f)  # noqa: SLF001
                dest = safe_join(os.path.join(gd, kind), v["file"]["filename"])
                items.append((v["file"]["url"], dest, v["file"].get("sha1")))
                m = mods.get(int(pid), {})
                metas[f"{kind}/{v['file']['filename']}"] = {
                    "source": "curseforge", "project": str(pid), "version": str(fid), "versionName": v["number"],
                    "title": m.get("name") or v["file"]["filename"], "icon": (m.get("logo") or {}).get("thumbnailUrl") or ""}
    if not items:
        return
    task.set_status(f"Загрузка файлов: {len(items)}")
    download_many(items, lambda done, total: (task.set_max(total), task.set_progress(done)))
    with content._lock:  # noqa: SLF001
        meta = content.load_meta(inst_id)
        meta["files"].update(metas)
        content.save_meta(inst_id, meta)


def save_to_file(code, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    return path


def read_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


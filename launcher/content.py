"""Моды/ресурспаки/шейдеры внутри сборки и установка модпаков."""
import json
import os
import re
import shutil
import threading
import zipfile

from . import instances, sources
from .util import CACHE, download, download_many, read_json, safe_join, sha1_file, write_json

KINDS = {"mods": "mod", "resourcepacks": "resourcepack", "shaderpacks": "shader"}
_lock = threading.Lock()


# ---------------------------------------------------------------- meta
def _meta_path(inst_id):
    return os.path.join(instances.inst_dir(inst_id), "content.json")


def load_meta(inst_id):
    m = read_json(_meta_path(inst_id), {}) or {}
    m.setdefault("files", {})
    m.setdefault("jar", {})
    return m


def save_meta(inst_id, meta):
    write_json(_meta_path(inst_id), meta)


def _base(name):
    return name[:-9] if name.endswith(".disabled") else name


def _jar_info(path):
    info = {}
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "fabric.mod.json" in names:
                d = json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
                info = {"name": d.get("name") or d.get("id"), "version": d.get("version"),
                        "description": d.get("description", "")}
            elif "quilt.mod.json" in names:
                d = json.loads(z.read("quilt.mod.json").decode("utf-8", "replace"), strict=False)
                ql = d.get("quilt_loader", {})
                info = {"name": ql.get("metadata", {}).get("name") or ql.get("id"), "version": ql.get("version")}
            else:
                for toml in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
                    if toml in names:
                        t = z.read(toml).decode("utf-8", "replace")
                        n = re.search(r'displayName\s*=\s*"([^"]+)"', t)
                        v = re.search(r'^\s*version\s*=\s*"([^"]+)"', t, re.M)
                        info = {"name": n and n.group(1), "version": v and v.group(1)}
                        break
                else:
                    if "mcmod.info" in names:
                        d = json.loads(z.read("mcmod.info").decode("utf-8", "replace"), strict=False)
                        d = d[0] if isinstance(d, list) else d.get("modList", [{}])[0]
                        info = {"name": d.get("name"), "version": d.get("version")}
    except Exception:  # noqa: BLE001
        pass
    if info.get("version", "") and "${" in str(info["version"]):
        info["version"] = ""
    return info


def list_content(inst_id, kind):
    if kind not in KINDS:
        raise ValueError(kind)
    folder = os.path.join(instances.game_dir(inst_id), kind)
    os.makedirs(folder, exist_ok=True)
    meta = load_meta(inst_id)
    changed = False
    out = []
    for name in os.listdir(folder):
        if name.startswith(".") or name.endswith((".part", ".tmp")):
            continue
        path = os.path.join(folder, name)
        base = _base(name)
        m = meta["files"].get(f"{kind}/{base}", {})
        item = {"file": name, "base": base, "enabled": not name.endswith(".disabled"),
                "isDir": os.path.isdir(path), "size": os.path.getsize(path) if os.path.isfile(path) else 0,
                "title": m.get("title"), "icon": m.get("icon", ""), "source": m.get("source", ""),
                "project": m.get("project", ""), "version": m.get("versionName", "")}
        if kind == "mods" and not item["title"] and os.path.isfile(path):
            st = os.stat(path)
            key = f"{base}:{st.st_size}:{int(st.st_mtime)}"
            ji = meta["jar"].get(key)
            if ji is None:
                ji = _jar_info(path)
                meta["jar"][key] = ji
                changed = True
            item["title"] = ji.get("name")
            item["version"] = item["version"] or ji.get("version") or ""
        item["title"] = item["title"] or base
        out.append(item)
    if changed:
        save_meta(inst_id, meta)
    out.sort(key=lambda x: x["title"].lower())
    return out


def toggle(inst_id, kind, name, enabled):
    folder = os.path.join(instances.game_dir(inst_id), kind)
    src = safe_join(folder, name)
    base = _base(name)
    dst = safe_join(folder, base if enabled else base + ".disabled")
    if src != dst:
        os.replace(src, dst)
    return list_content(inst_id, kind)


def delete(inst_id, kind, names):
    folder = os.path.join(instances.game_dir(inst_id), kind)
    with _lock:
        meta = load_meta(inst_id)
        for name in names:
            p = safe_join(folder, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
            meta["files"].pop(f"{kind}/{_base(name)}", None)
        save_meta(inst_id, meta)
    return list_content(inst_id, kind)


def add_files(inst_id, kind, paths):
    folder = os.path.join(instances.game_dir(inst_id), kind)
    os.makedirs(folder, exist_ok=True)
    for p in paths:
        shutil.copy2(p, os.path.join(folder, os.path.basename(p)))
    return list_content(inst_id, kind)


def installed_projects(inst_id):
    meta = load_meta(inst_id)
    gd = instances.game_dir(inst_id)
    out = []
    for key, m in meta["files"].items():
        p = os.path.join(gd, key)
        if os.path.exists(p) or os.path.exists(p + ".disabled"):
            out.append(f"{m.get('source')}:{m.get('project')}")
    return out


# ---------------------------------------------------------------- install project
def _pick(versions_list):
    for t in ("release", "beta", "alpha"):
        for v in versions_list:
            if v["type"] == t and v["file"]:
                return v
    return None


def install_project(source, ptype, inst_id, project_id, version_id=None, task=None, _seen=None):
    """Ставит проект (и обязательные зависимости) в сборку."""
    inst = instances.get(inst_id)
    folder = sources.FOLDERS[ptype]
    if folder is None:
        raise ValueError("Модпак ставится как новая сборка")
    _seen = _seen if _seen is not None else set()
    if project_id in _seen:
        return
    _seen.add(project_id)

    if version_id:
        v = sources.mr_version(version_id) if source == "modrinth" else sources.cf_version(project_id, version_id)
    else:
        v = _pick(sources.versions(source, project_id, ptype, inst["mc"], inst["loader"]))
    if not v or not v["file"]:
        raise RuntimeError(f"Нет подходящей версии для {inst['mc']} {inst['loader']}")
    proj = sources.project(source, project_id)
    if task:
        task.set_status(f"Загрузка {proj['title']}")

    gd = instances.game_dir(inst_id)
    target_dir = os.path.join(gd, folder)
    dest = safe_join(target_dir, v["file"]["filename"])

    with _lock:
        meta = load_meta(inst_id)
        # удалить старые файлы этого же проекта (обновление/смена версии)
        for key, m in list(meta["files"].items()):
            if m.get("source") == source and str(m.get("project")) == str(project_id) and key.startswith(folder + "/"):
                for p in (os.path.join(gd, key), os.path.join(gd, key) + ".disabled"):
                    if os.path.exists(p) and os.path.abspath(p) != dest:
                        os.remove(p)
                del meta["files"][key]
        save_meta(inst_id, meta)

    download(v["file"]["url"], dest, v["file"].get("sha1"))

    with _lock:
        meta = load_meta(inst_id)
        meta["files"][f"{folder}/{v['file']['filename']}"] = {
            "source": source, "project": str(project_id), "version": v["id"], "versionName": v["number"],
            "title": proj["title"], "icon": proj["icon"]}
        save_meta(inst_id, meta)

    if ptype == "mod":
        have = set(installed_projects(inst_id))
        mod_ids = None
        for d in v["deps"]:
            pid = d.get("project")
            if not pid and d.get("version") and source == "modrinth":
                pid = sources.mr_version(d["version"])["project"]
            if not pid or f"{source}:{pid}" in have:
                continue
            # зависимость могла быть добавлена вручную файлом — сверяем по id модов в jar
            if mod_ids is None:
                mod_ids = {_norm(i) for i in installed_mod_ids(inst_id)}
            try:
                dp = sources.project(source, pid)
                if {_norm(dp.get("slug") or ""), _norm(dp["title"])} & mod_ids:
                    continue
            except Exception:  # noqa: BLE001
                pass
            try:
                install_project(source, "mod", inst_id, pid, None, task, _seen)
            except Exception as e:  # noqa: BLE001 — зависимость без версии не должна ронять установку
                print("dependency failed", pid, e)
    return {"title": proj["title"]}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _toml_mod_ids(text):
    """modId только из секций [[mods]] (в [[dependencies.*]] тоже есть modId — это не наши моды)."""
    ids, section = set(), None
    for line in text.splitlines():
        st = line.split("#", 1)[0].strip()
        if st.startswith("["):
            section = st.strip("[] ").split(".")[0]
            continue
        m = re.match(r'modId\s*=\s*"([^"]+)"', st)
        if m and section == "mods":
            ids.add(m.group(1))
    return ids


def jar_mod_ids(path):
    """id модов внутри jar (fabric/quilt/forge/neoforge)."""
    ids = set()
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "fabric.mod.json" in names:
                d = json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
                ids.add(d.get("id", ""))
                ids.update(d.get("provides") or [])
            if "quilt.mod.json" in names:
                d = json.loads(z.read("quilt.mod.json").decode("utf-8", "replace"), strict=False)
                ids.add((d.get("quilt_loader") or {}).get("id", ""))
            for toml in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
                if toml in names:
                    ids.update(_toml_mod_ids(z.read(toml).decode("utf-8", "replace")))
    except Exception:  # noqa: BLE001
        pass
    ids.discard("")
    return ids


def installed_mod_ids(inst_id, with_disabled=True):
    """Все id модов в папке mods (по содержимому jar) + 'optifine', если он лежит там."""
    folder = os.path.join(instances.game_dir(inst_id), "mods")
    out = set()
    for n in os.listdir(folder) if os.path.isdir(folder) else []:
        if not (n.endswith(".jar") or (with_disabled and n.endswith(".jar.disabled"))):
            continue
        if "optifine" in n.lower():
            out.add("optifine")
        out |= jar_mod_ids(os.path.join(folder, n))
    return out


# ---------------------------------------------------------------- updates (Modrinth по хэшу)
def check_updates(inst_id):
    inst = instances.get(inst_id)
    folder = os.path.join(instances.game_dir(inst_id), "mods")
    files = {}
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        if name.endswith(".jar"):
            files[sha1_file(os.path.join(folder, name))] = name
    if not files:
        return []
    found = sources.mr_updates(list(files), inst["loader"], inst["mc"])
    meta = load_meta(inst_id)
    out = []
    for h, v in found.items():
        if v["file"] and v["file"]["sha1"] != h:
            name = files[h]
            m = meta["files"].get(f"mods/{name}", {})
            out.append({"file": name, "title": m.get("title") or name, "project": v["project"],
                        "version": v["id"], "versionName": v["number"]})
    return out


def apply_updates(inst_id, updates, task):
    gd = instances.game_dir(inst_id)
    task.set_max(len(updates))
    for i, u in enumerate(updates):
        old = safe_join(os.path.join(gd, "mods"), u["file"])
        install_project("modrinth", "mod", inst_id, u["project"], u["version"], task, _seen={"__"})
        v = sources.mr_version(u["version"])
        if os.path.exists(old) and os.path.basename(old) != v["file"]["filename"]:
            os.remove(old)
        task.set_progress(i + 1)


# ---------------------------------------------------------------- modpacks
LOADER_KEYS = (("fabric-loader", "fabric"), ("quilt-loader", "quilt"), ("neoforge", "neoforge"), ("forge", "forge"))
MANAGED_DIRS = ("mods/", "resourcepacks/", "shaderpacks/")
# при обновлении модпака не перезаписываем личные настройки игрока
KEEP_ON_UPDATE = ("options.txt", "optionsof.txt", "optionsshaders.txt", "servers.dat", "saves/")


def _read_pack(zf, task=None):
    """Разбирает .mrpack / .zip CurseForge: версия, загрузчик, файлы для скачивания, префиксы overrides."""
    names = set(zf.namelist())
    if "modrinth.index.json" in names:
        index = json.loads(zf.read("modrinth.index.json"))
        deps = index["dependencies"]
        loader, lv = "vanilla", ""
        for key, ld in LOADER_KEYS:
            if key in deps:
                loader, lv = ld, deps[key]
                break
        files = [(f["downloads"], f["path"].replace("\\", "/"), f["hashes"].get("sha1"))
                 for f in index["files"] if (f.get("env") or {}).get("client") != "unsupported"]
        return {"name": index.get("name", "Modpack"), "mc": deps["minecraft"], "loader": loader, "lv": lv,
                "files": files, "prefixes": ("overrides/", "client-overrides/")}
    if "manifest.json" in names:
        man = json.loads(zf.read("manifest.json"))
        mcv = man["minecraft"]["version"]
        loaders = man["minecraft"].get("modLoaders", [])
        primary = next((l for l in loaders if l.get("primary")), loaders[0] if loaders else None)
        loader, lv = "vanilla", ""
        if primary:
            lname, _, lv = primary["id"].partition("-")
            loader = lname.lower()
            if loader == "neoforge" and lv.startswith(mcv + "-"):
                loader, lv = "forge", lv[len(mcv) + 1:]   # NeoForge 1.20.1 — форк Forge
        pairs = [(f["projectID"], f["fileID"]) for f in man.get("files", []) if f.get("required", True)]
        if task:
            task.set_status(f"Получение списка файлов ({len(pairs)})")
        cf_files = sources.cf_files_bulk(pairs) if pairs else {}
        mods = sources.cf_mods_bulk(sorted({p for p, _ in pairs})) if pairs else {}
        files = []
        for pid, fid in pairs:
            f = cf_files.get(fid)
            if not f:
                continue
            folder = sources.CF_CLASS_FOLDER.get((mods.get(pid) or {}).get("classId"), "mods")
            sha1 = next((h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), None)
            files.append(([sources.cf_file_url(f), sources.cf_file_url({**f, "downloadUrl": None})],
                          f"{folder}/{f['fileName']}", sha1))
        return {"name": man.get("name", "Modpack"), "mc": mcv, "loader": loader, "lv": lv, "files": files,
                "prefixes": (man.get("overrides", "overrides") + "/",)}
    raise ValueError("Это не модпак Modrinth (.mrpack) и не CurseForge (.zip)")


def _override_paths(zf, prefixes):
    out = []
    for zi in zf.infolist():
        if zi.is_dir():
            continue
        for pref in prefixes:
            if zi.filename.startswith(pref) and len(zi.filename) > len(pref):
                out.append((zi, zi.filename[len(pref):]))
                break
    return out


def _managed(zf, pack):
    """Файлы, которые принадлежат модпаку (их можно удалять при обновлении)."""
    rels = {rel for _, rel, _ in pack["files"]}
    rels |= {rel for _, rel in _override_paths(zf, pack["prefixes"]) if rel.startswith(MANAGED_DIRS)}
    return sorted(rels)


def _extract_overrides(zf, prefixes, gd, keep=()):
    keep_dirs = tuple(k for k in keep if k.endswith("/"))
    for zi, rel in _override_paths(zf, prefixes):
        target = safe_join(gd, rel)
        if keep and (rel in keep or (keep_dirs and rel.startswith(keep_dirs))) and os.path.exists(target):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(zi) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)


def _download_pack_files(pack, gd, task, skip_disabled=False):
    items = []
    for urls, rel, sha1 in pack["files"]:
        dest = safe_join(gd, rel)
        if skip_disabled and os.path.exists(dest + ".disabled"):
            continue  # игрок отключил этот мод — не включаем его обратно
        items.append((urls, dest, sha1))
    task.set_status(f"Загрузка файлов модпака ({len(items)})")
    download_many(items, task.counter)


def _save_icon(inst_id, url):
    if url:
        try:
            download(url, os.path.join(instances.inst_dir(inst_id), "icon.png"))
        except Exception:  # noqa: BLE001
            pass


def install_pack_file(path, name, task, icon_url="", source_info=None):
    """Создаёт сборку из .mrpack или .zip CurseForge."""
    from . import game
    with zipfile.ZipFile(path) as zf:
        pack = _read_pack(zf, task)
        mp = dict(source_info or {"name": pack["name"]})
        mp["files"] = _managed(zf, pack)
        inst = instances.create(name or pack["name"], pack["mc"], pack["loader"], pack["lv"], extra={"modpack": mp})
        try:
            gd = instances.game_dir(inst["id"])
            _download_pack_files(pack, gd, task)
            task.set_status("Распаковка")
            _extract_overrides(zf, pack["prefixes"], gd)
        except Exception:
            instances.delete(inst["id"])
            raise
    _save_icon(inst["id"], icon_url)
    inst = instances.get(inst["id"])
    game.ensure_installed(inst, task)
    return {"inst": inst["id"]}


def _fetch_pack(source, project_id, version_id, task=None):
    v = sources.mr_version(version_id) if source == "modrinth" else sources.cf_version(project_id, version_id)
    os.makedirs(os.path.join(CACHE, "packs"), exist_ok=True)
    path = os.path.join(CACHE, "packs", f"{version_id}_{v['file']['filename']}")
    if task:
        task.set_status(f"Загрузка модпака {v['number'] or ''}".strip())
    download(v["file"]["url"], path, v["file"].get("sha1"))
    return path, v


def install_modpack(source, project_id, version_id, name, task):
    proj = sources.project(source, project_id)
    path, v = _fetch_pack(source, project_id, version_id, task)
    try:
        return install_pack_file(path, name or proj["title"], task, proj["icon"],
                                 {"source": source, "project": project_id, "version": version_id,
                                  "name": proj["title"], "versionName": v["number"]})
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------- modpack updates
def modpack_versions(inst_id):
    inst = instances.get(inst_id)
    mp = inst.get("modpack") or {}
    if not mp.get("source") or not mp.get("project"):
        raise ValueError("Сборка установлена не с Modrinth/CurseForge — обновлять нечего")
    vers = [v for v in sources.versions(mp["source"], mp["project"], "modpack", "", "") if v.get("file")]
    vers.sort(key=lambda v: v.get("date") or "", reverse=True)
    cur = str(mp.get("version"))
    cur_date = next((v.get("date") for v in vers if str(v["id"]) == cur), "")
    out = [{"id": v["id"], "number": v["number"] or v["name"], "type": v["type"], "date": v.get("date", ""),
            "mc": v["mc"][:3], "current": str(v["id"]) == cur, "sameMc": inst["mc"] in v["mc"],
            "newer": bool(cur_date) and (v.get("date") or "") > cur_date} for v in vers]
    return {"current": mp.get("versionName"), "mc": inst["mc"], "versions": out,
            "hasUpdate": any(v["newer"] and v["sameMc"] for v in out)}


def update_modpack(inst_id, version_id, backup, task):
    from . import game, worlds
    if game.is_running(inst_id):
        raise RuntimeError("Сначала закройте игру")
    inst = instances.get(inst_id)
    mp = dict(inst.get("modpack") or {})
    source, project = mp.get("source"), mp.get("project")
    if not source or not project:
        raise ValueError("Сборка установлена не с Modrinth/CurseForge")
    gd = instances.game_dir(inst_id)

    if backup and worlds.list_worlds(inst_id):
        worlds.backup_all(inst_id, task, note="перед_обновлением")

    old = mp.get("files")
    warn = None
    if old is None and mp.get("version"):
        # сборки до 1.5 не запоминали свои файлы — узнаём их из старой версии модпака
        try:
            task.set_status("Сравнение со старой версией")
            opath, _ = _fetch_pack(source, project, mp["version"])
            try:
                with zipfile.ZipFile(opath) as zf:
                    old = _managed(zf, _read_pack(zf))
            finally:
                os.remove(opath)
        except Exception as e:  # noqa: BLE001
            print("old pack unavailable", e)
            warn = "Старая версия модпака недоступна — старые моды могли остаться, проверьте папку mods"

    path, v = _fetch_pack(source, project, version_id, task)
    removed = 0
    try:
        with zipfile.ZipFile(path) as zf:
            pack = _read_pack(zf, task)
            new = _managed(zf, pack)
            for rel in set(old or []) - set(new):
                for p in (safe_join(gd, rel), safe_join(gd, rel) + ".disabled"):
                    if os.path.isfile(p):
                        os.remove(p)
                        removed += 1
            _download_pack_files(pack, gd, task, skip_disabled=True)
            task.set_status("Распаковка")
            _extract_overrides(zf, pack["prefixes"], gd, keep=KEEP_ON_UPDATE)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    mp.update(version=version_id, versionName=v["number"], files=new)
    instances.update(inst_id, {"mc": pack["mc"], "loader": pack["loader"], "loaderVersion": pack["lv"]})
    fresh = instances.get(inst_id)
    fresh["modpack"] = mp
    instances.save(fresh)
    game.ensure_installed(instances.get(inst_id), task)
    return {"version": v["number"], "removed": removed, "warning": warn}

"""Поиск и версии контента на Modrinth и CurseForge — единый формат ответа."""
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from . import config
from .util import get_json, http

FOLDERS = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks", "modpack": None}

# ================================================================ Modrinth
MR = "https://api.modrinth.com/v2"
MR_SORT = {"relevance": "relevance", "downloads": "downloads", "updated": "updated", "newest": "newest"}


def _mr_loaders(loader):
    if loader == "quilt":
        return ["quilt", "fabric"]
    return [loader]


def mr_search(query, ptype, mc, loader, offset, sort):
    facets = [[f"project_type:{ptype}"]]
    if mc:
        facets.append([f"versions:{mc}"])
    if loader and loader != "vanilla" and ptype in ("mod", "modpack"):
        facets.append([f"categories:{l}" for l in _mr_loaders(loader)])
    res = get_json(f"{MR}/search", params={
        "query": query or "", "facets": json.dumps(facets), "offset": offset, "limit": 20,
        "index": MR_SORT.get(sort, "relevance")})
    hits = [{
        "id": h["project_id"], "slug": h["slug"], "title": h["title"], "description": h["description"],
        "icon": h.get("icon_url") or "", "downloads": h.get("downloads", 0), "author": h.get("author", ""),
        "url": f"https://modrinth.com/{h['project_type']}/{h['slug']}",
        "categories": h.get("display_categories") or h.get("categories", []),
    } for h in res["hits"]]
    return {"hits": hits, "total": res.get("total_hits", len(hits))}


def _mr_version(v):
    files = v.get("files") or []
    f = next((x for x in files if x.get("primary")), files[0] if files else None)
    return {
        "id": v["id"], "name": v.get("name") or v.get("version_number"), "number": v.get("version_number"),
        "type": v.get("version_type", "release"), "mc": v.get("game_versions", []),
        "loaders": v.get("loaders", []), "date": (v.get("date_published") or "")[:10],
        "file": f and {"url": f["url"], "filename": f["filename"], "sha1": f["hashes"].get("sha1"),
                       "size": f.get("size", 0)},
        "deps": [{"project": d.get("project_id"), "version": d.get("version_id")}
                 for d in v.get("dependencies", []) if d.get("dependency_type") == "required"],
        "project": v.get("project_id"),
    }


def mr_versions(project_id, ptype, mc, loader):
    params = {}
    if mc:
        params["game_versions"] = json.dumps([mc])
    if ptype == "mod" and loader and loader != "vanilla":
        params["loaders"] = json.dumps(_mr_loaders(loader))
    return [_mr_version(v) for v in get_json(f"{MR}/project/{project_id}/version", params=params)]


def mr_version(version_id):
    return _mr_version(get_json(f"{MR}/version/{version_id}"))


def mr_project(project_id):
    p = get_json(f"{MR}/project/{project_id}")
    return {"id": p["id"], "title": p["title"], "icon": p.get("icon_url") or "", "body": p.get("body", ""),
            "description": p.get("description", ""), "type": p.get("project_type")}


def mr_updates(hashes, loader, mc):
    """sha1 -> новая версия (Modrinth знает файлы по хэшу)."""
    body = {"hashes": hashes, "algorithm": "sha1", "game_versions": [mc]}
    if loader and loader != "vanilla":
        body["loaders"] = _mr_loaders(loader)
    r = http().post(f"{MR}/version_files/update", json=body, timeout=30)
    r.raise_for_status()
    return {h: _mr_version(v) for h, v in r.json().items()}


# ================================================================ CurseForge
CF_CLASS = {"mod": 6, "resourcepack": 12, "shader": 6552, "modpack": 4471}
CF_CLASS_FOLDER = {6: "mods", 12: "resourcepacks", 6552: "shaderpacks", 6945: "datapacks"}
CF_LOADER = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
CF_SORT = {"relevance": 1, "downloads": 6, "updated": 3, "newest": 11, "popularity": 2}
CF_RELEASE = {1: "release", 2: "beta", 3: "alpha"}


def _cf():
    key = (config.load().get("cfApiKey") or "").strip()
    if key:
        return "https://api.curseforge.com/v1", {"x-api-key": key}
    return "https://api.curse.tools/v1/cf", {}


def cf_get(path, **params):
    base, headers = _cf()
    return get_json(base + path, params=params or None, headers=headers)


def cf_post(path, body):
    base, headers = _cf()
    r = http().post(base + path, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def cf_search(query, ptype, mc, loader, offset, sort):
    params = {"gameId": 432, "classId": CF_CLASS[ptype], "searchFilter": query or "", "index": offset,
              "pageSize": 20, "sortField": CF_SORT.get(sort, 2), "sortOrder": "desc"}
    if not query and sort == "relevance":
        params["sortField"] = 2
    if mc:
        params["gameVersion"] = mc
    if loader in CF_LOADER and ptype in ("mod", "modpack"):
        params["modLoaderType"] = CF_LOADER[loader]
    res = cf_get("/mods/search", **params)
    hits = [{
        "id": str(m["id"]), "slug": m["slug"], "title": m["name"], "description": m.get("summary", ""),
        "icon": (m.get("logo") or {}).get("thumbnailUrl") or "", "downloads": int(m.get("downloadCount", 0)),
        "author": (m.get("authors") or [{}])[0].get("name", ""),
        "url": (m.get("links") or {}).get("websiteUrl") or "",
        "categories": [c["name"] for c in m.get("categories", [])][:3],
    } for m in res["data"]]
    total = min(res.get("pagination", {}).get("totalCount", len(hits)), 10000)
    return {"hits": hits, "total": total}


def cf_file_url(f):
    if f.get("downloadUrl"):
        return f["downloadUrl"]
    fid = int(f["id"])
    return f"https://edge.forgecdn.net/files/{fid // 1000}/{fid % 1000}/{quote(f['fileName'])}"


def _cf_version(f):
    sha1 = next((h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), None)
    gv = f.get("gameVersions", [])
    return {
        "id": str(f["id"]), "name": f.get("displayName") or f["fileName"], "number": f["fileName"],
        "type": CF_RELEASE.get(f.get("releaseType"), "release"),
        "mc": [g for g in gv if g[:1].isdigit()],
        "loaders": [g.lower() for g in gv if g.lower() in CF_LOADER],
        "date": (f.get("fileDate") or "")[:10],
        "file": {"url": cf_file_url(f), "filename": f["fileName"], "sha1": sha1, "size": f.get("fileLength", 0)},
        "deps": [{"project": str(d["modId"]), "version": None}
                 for d in f.get("dependencies", []) if d.get("relationType") == 3],
        "project": str(f.get("modId")),
    }


def cf_versions(project_id, ptype, mc, loader):
    params = {"pageSize": 50}
    if mc:
        params["gameVersion"] = mc
    if ptype == "mod" and loader in CF_LOADER:
        params["modLoaderType"] = CF_LOADER[loader]
    return [_cf_version(f) for f in cf_get(f"/mods/{project_id}/files", **params)["data"]]


def cf_version(project_id, file_id):
    return _cf_version(cf_get(f"/mods/{project_id}/files/{file_id}")["data"])


def cf_project(project_id):
    m = cf_get(f"/mods/{project_id}")["data"]
    return {"id": str(m["id"]), "title": m["name"], "icon": (m.get("logo") or {}).get("thumbnailUrl") or "",
            "description": m.get("summary", ""), "classId": m.get("classId"), "body": ""}


def cf_files_bulk(pairs):
    """pairs: [(projectID, fileID)] -> {fileID: raw file}. Пробуем POST, иначе параллельные GET."""
    ids = [fid for _, fid in pairs]
    try:
        data = cf_post("/mods/files", {"fileIds": ids})["data"]
        return {f["id"]: f for f in data}
    except Exception:  # noqa: BLE001
        pass
    base, headers = _cf()

    def one(p):
        return get_json(f"{base}/mods/{p[0]}/files/{p[1]}", headers=headers)["data"]
    with ThreadPoolExecutor(8) as pool:
        return {f["id"]: f for f in pool.map(one, pairs)}


def cf_mods_bulk(mod_ids):
    try:
        data = cf_post("/mods", {"modIds": mod_ids})["data"]
        return {m["id"]: m for m in data}
    except Exception:  # noqa: BLE001
        pass
    base, headers = _cf()

    def one(mid):
        try:
            return get_json(f"{base}/mods/{mid}", headers=headers)["data"]
        except Exception:  # noqa: BLE001
            return {"id": mid, "classId": 6}
    with ThreadPoolExecutor(8) as pool:
        return {m["id"]: m for m in pool.map(one, mod_ids)}


# ================================================================ общий вход
def search(source, query, ptype, mc, loader, offset=0, sort="relevance"):
    fn = mr_search if source == "modrinth" else cf_search
    return fn(query, ptype, mc, loader, int(offset or 0), sort)


def versions(source, project_id, ptype, mc, loader):
    fn = mr_versions if source == "modrinth" else cf_versions
    return fn(project_id, ptype, mc, loader)


def project(source, project_id):
    return mr_project(project_id) if source == "modrinth" else cf_project(project_id)

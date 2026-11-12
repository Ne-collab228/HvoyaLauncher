"""Проверка папки mods: битые jar, чужой загрузчик/версия игры, дубликаты, недостающие зависимости, конфликты."""
import io
import json
import os
import re
import tomllib
import zipfile

from . import instances

BUILTIN = {"minecraft", "java", "forge", "neoforge", "fabricloader", "fabric-loader", "quilt_loader",
           "quilt-loader", "fml", "javafml", "lowcodefml", "mclanguage", "fabric"}   # "fabric" ниже подменяется provides
_FABRIC_API_ALIAS = {"fabric": "fabric-api"}
CONFLICTS = [({"optifine"}, {"sodium", "embeddium", "rubidium", "iris", "oculus", "indium"},
              "OptiFine конфликтует с Sodium/Embeddium/Iris — оставьте что-то одно."),
             ({"sodium"}, {"embeddium", "rubidium"}, "Sodium и Embeddium/Rubidium — одно и то же для разных загрузчиков, нужен только один."),
             ({"optifine"}, {"optifabric"}, "")]
_LNAMES = {"fabric": "Fabric", "quilt": "Quilt", "forge": "Forge", "neoforge": "NeoForge"}
_COMPAT = {"fabric": {"fabric"}, "quilt": {"quilt", "fabric"}, "forge": {"forge"}, "neoforge": {"neoforge", "forge"}}
_cache = {}


# ---------------------------------------------------------------- версии
def _vt(s):
    return tuple(int(x) for x in re.findall(r"\d+", str(s))[:4])


def _cmp(a, b):
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def fabric_match(rng, v):
    """Диапазон версий Fabric/Quilt (упрощённо). None — не удалось разобрать."""
    try:
        if isinstance(rng, list):
            return any(fabric_match(r, v) for r in rng)
        rng = str(rng).strip()
        if rng in ("", "*"):
            return True
        if "||" in rng:
            return any(fabric_match(r, v) for r in rng.split("||"))
        for c in rng.split():
            m = re.match(r"^(>=|<=|>|<|=|~|\^)?\s*(.+)$", c)
            op, val = m.group(1) or "=", m.group(2)
            if re.search(r"[xX*]", val):
                base = _vt(val.replace("x", "0").replace("X", "0").replace("*", "0"))
                parts = val.split(".")
                k = next((i for i, p in enumerate(parts) if p in ("x", "X", "*")), len(parts))
                lo = base[:k]
                hi = lo[:-1] + (lo[-1] + 1,) if lo else (999,)
                ok = _cmp(v, lo) >= 0 and _cmp(v, hi) < 0
            else:
                t = _vt(val)
                if op == ">=": ok = _cmp(v, t) >= 0
                elif op == "<=": ok = _cmp(v, t) <= 0
                elif op == ">": ok = _cmp(v, t) > 0
                elif op == "<": ok = _cmp(v, t) < 0
                elif op == "~": ok = _cmp(v, t) >= 0 and _cmp(v, (t[0], (t[1] if len(t) > 1 else 0) + 1)) < 0
                elif op == "^": ok = _cmp(v, t) >= 0 and _cmp(v, (t[0] + 1,)) < 0
                else: ok = _cmp(v, t) == 0
            if not ok:
                return False
        return True
    except Exception:  # noqa: BLE001
        return None


def maven_match(rng, v):
    """Диапазон версий Forge/NeoForge: [1.20,1.21) и т.п."""
    try:
        parts = re.findall(r"([\[(])\s*([^,\])]*?)\s*(?:,\s*([^\])]*?)\s*)?([\])])", str(rng))
        if not parts:
            return True
        for lb, lo, hi, rb in parts:
            if hi is None or (hi == "" and "," not in rng):
                ok = _cmp(v, _vt(lo)) == 0
            else:
                ok = True
                if lo:
                    c = _cmp(v, _vt(lo))
                    ok = c > 0 or (c == 0 and lb == "[")
                if ok and hi:
                    c = _cmp(v, _vt(hi))
                    ok = c < 0 or (c == 0 and rb == "]")
            if ok:
                return True
        return False
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- разбор jar
def _scan(z, depth=0):
    names = set(z.namelist())
    res = {"kinds": set(), "mods": [], "nested": set()}
    if "fabric.mod.json" in names:
        res["kinds"].add("fabric")
        d = json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
        deps = [{"id": k, "range": v, "req": True} for k, v in (d.get("depends") or {}).items()]
        prov = [p if isinstance(p, str) else p.get("id", "") for p in (d.get("provides") or [])]
        res["mods"].append({"id": d.get("id", ""), "version": str(d.get("version", "")), "name": d.get("name"),
                            "deps": deps, "provides": prov, "kind": "fabric"})
        jars = [j.get("file") for j in (d.get("jars") or []) if isinstance(j, dict)]
    else:
        jars = []
    if "quilt.mod.json" in names:
        res["kinds"].add("quilt")
        d = json.loads(z.read("quilt.mod.json").decode("utf-8", "replace"), strict=False)
        ql = d.get("quilt_loader") or {}
        deps = []
        for x in ql.get("depends") or []:
            if isinstance(x, str):
                deps.append({"id": x, "range": "*", "req": True})
            elif not x.get("optional"):
                deps.append({"id": x.get("id", ""), "range": x.get("versions", "*"), "req": True})
        prov = [p if isinstance(p, str) else p.get("id", "") for p in (ql.get("provides") or [])]
        res["mods"].append({"id": ql.get("id", ""), "version": str(ql.get("version", "")), "name": (ql.get("metadata") or {}).get("name"),
                            "deps": deps, "provides": prov, "kind": "quilt"})
        jars += [j if isinstance(j, str) else j.get("file") for j in (ql.get("jars") or [])]
    for t, kind in (("META-INF/neoforge.mods.toml", "neoforge"), ("META-INF/mods.toml", "forge")):
        if t not in names:
            continue
        res["kinds"].add(kind)
        try:
            d = tomllib.loads(z.read(t).decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            from .content import _toml_mod_ids
            for i in _toml_mod_ids(z.read(t).decode("utf-8", "replace")):
                res["mods"].append({"id": i, "version": "", "name": None, "deps": [], "provides": [], "kind": kind})
            continue
        for m in d.get("mods") or []:
            mid = m.get("modId", "")
            deps = []
            for dp in (d.get("dependencies") or {}).get(mid, []):
                if str(dp.get("side", "BOTH")).upper() == "SERVER":
                    continue
                req = dp.get("mandatory") is True or str(dp.get("type", "")).lower() == "required"
                deps.append({"id": dp.get("modId", ""), "range": dp.get("versionRange", ""), "req": req})
            res["mods"].append({"id": mid, "version": str(m.get("version", "")), "name": m.get("displayName"),
                                "deps": deps, "provides": [], "kind": kind})
    if "mcmod.info" in names:
        res["kinds"].add("forge")
    for n in names:
        if n.startswith("META-INF/services/"):
            if "minecraftforge" in n or "cpw.mods" in n:
                res["kinds"].add("forge")
            if "neoforged" in n:
                res["kinds"].add("neoforge")
    if depth < 2:
        for n in names:
            if (n.startswith("META-INF/jarjar/") or n.startswith("META-INF/jars/")) and n.endswith(".jar"):
                jars.append(n)
        for j in set(jars):
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(j))) as zz:
                    sub = _scan(zz, depth + 1)
                for m in sub["mods"]:
                    res["nested"].add(m["id"])
                    res["nested"].update(m["provides"])
                res["nested"] |= sub["nested"]
            except Exception:  # noqa: BLE001
                pass
    return res


def _scan_file(path):
    st = os.stat(path)
    key = (path, st.st_size, int(st.st_mtime))
    if key not in _cache:
        try:
            with zipfile.ZipFile(path) as z:
                _cache[key] = _scan(z)
        except (zipfile.BadZipFile, OSError):
            _cache[key] = None
        except Exception:  # noqa: BLE001 — нечитаемый манифест не считаем поломкой
            _cache[key] = {"kinds": set(), "mods": [], "nested": set()}
    return _cache[key]


def _issue(level, title, text, files=None, dep=None):
    return {"level": level, "title": title, "text": text, "files": files or [], "dep": dep}


# ---------------------------------------------------------------- проверка
def check(inst_id):
    inst = instances.get(inst_id)
    folder = os.path.join(instances.game_dir(inst_id), "mods")
    loader, mc = inst.get("loader", "vanilla"), inst.get("mc", "")
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    jars = [n for n in names if n.endswith(".jar")]
    disabled = [n for n in names if n.endswith(".jar.disabled")]
    out = []
    stats = {"jars": len(jars), "disabled": len(disabled), "mods": 0}
    if loader == "vanilla":
        if jars:
            out.append(_issue("error", "Моды в сборке без загрузчика",
                              f"В папке mods {len(jars)} модов, но сборка на Vanilla — они не загрузятся. Выберите загрузчик на вкладке «Версия»."))
        return {"issues": out, "stats": stats}
    connector = any("connector" in n.lower() for n in jars)
    allowed = set(_COMPAT.get(loader, set())) | ({"fabric"} if connector else set())
    mcv = _vt(mc) if re.match(r"^\d+(\.\d+)*$", mc or "") else None

    scans, broken, wrong = {}, [], []
    for n in jars:
        s = _scan_file(os.path.join(folder, n))
        if s is None:
            broken.append(n)
            continue
        scans[n] = s
        if s["kinds"] and not (s["kinds"] & allowed):
            wrong.append(n)
    if broken:
        out.append(_issue("error", "Повреждённые файлы",
                          "Не открываются как архив (недокачаны или битые) — удалите и скачайте заново.", broken))
    if wrong:
        out.append(_issue("error", f"Моды для другого загрузчика (сборка на {_LNAMES.get(loader, loader)})",
                          "Не будут работать в этой сборке — отключите или поставьте версию под ваш загрузчик.", wrong))

    have = set(BUILTIN)
    owners = {}
    for n, s in scans.items():
        top = [m for m in s["mods"] if m["id"]]
        stats["mods"] += len(top)
        for m in top:
            have.add(m["id"])
            have.update(p for p in m["provides"] if p)
            owners.setdefault(m["id"], []).append((n, m))
        have |= s["nested"]
    # дубликаты
    for mid, lst in sorted(owners.items()):
        files = sorted({n for n, _ in lst})
        if len(files) > 1:
            vers = ", ".join(f"{n} ({m['version'] or '?'})" for n, m in lst)
            out.append(_issue("error", f"Дубликат мода «{mid}»", f"Один и тот же мод лежит в нескольких файлах: {vers}. Оставьте один.", files))
    # версия игры
    bad_mc = []
    for n, s in scans.items():
        if mcv is None or n in wrong:
            continue
        for m in s["mods"]:
            for d in m["deps"]:
                if d["id"] == "minecraft" and d["req"] and d["range"] not in ("", "*"):
                    f = maven_match if m["kind"] in ("forge", "neoforge") else fabric_match
                    if f(d["range"], mcv) is False:
                        bad_mc.append(f"{n} — нужна Minecraft {d['range']}")
                        break
    if bad_mc:
        out.append(_issue("error", f"Моды для другой версии Minecraft (сборка на {mc})",
                          "Эти моды объявляют несовместимую версию игры — скачайте версию под вашу.",
                          [x.split(" — ")[0] for x in bad_mc]))
        out[-1]["text"] += "\n" + "\n".join(bad_mc)
    # зависимости
    missing = {}
    for n, s in scans.items():
        if n in wrong or (connector and s["kinds"] == {"fabric"}):
            continue
        for m in s["mods"]:
            for d in m["deps"]:
                if d["req"] and d["id"] and d["id"] not in have and _FABRIC_API_ALIAS.get(d["id"], d["id"]) not in have:
                    missing.setdefault(d["id"], set()).add(m["name"] or m["id"] or n)
    for dep, by in sorted(missing.items()):
        out.append(_issue("error", f"Не хватает мода «{dep}»", "Нужен для: " + ", ".join(sorted(by)[:6]), dep=_FABRIC_API_ALIAS.get(dep, dep)))
    # конфликты
    ids = {i.lower() for i in have} | ({"optifine"} if any("optifine" in n.lower() for n in jars) else set())
    for a, b, text in CONFLICTS:
        if text and a & ids and b & ids:
            out.append(_issue("warn", "Возможный конфликт модов", text))
    if disabled:
        out.append(_issue("info", f"Отключённых модов: {len(disabled)}", "Файлы .jar.disabled в игре не участвуют.", disabled))
    return {"issues": out, "stats": stats}

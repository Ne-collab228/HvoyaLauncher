"""«Ускорить игру»: набор модов оптимизации под версию и загрузчик сборки (всё с Modrinth).

Fabric/Quilt/NeoForge 1.21+: Sodium + Iris + ModernFix + …
Forge: Embeddium (или Rubidium на старых версиях) + Oculus + ModernFix + …
Зависимости (Fabric API и т.п.) ставит content.install_project.
"""
from concurrent.futures import ThreadPoolExecutor

from . import content, instances, sources

# slug на Modrinth -> id мода внутри jar
MOD_IDS = {"sodium": "sodium", "embeddium": "embeddium", "rubidium": "rubidium", "iris": "iris", "oculus": "oculus",
           "modernfix": "modernfix", "ferrite-core": "ferritecore", "lithium": "lithium", "canary": "canary",
           "radium": "radium", "entityculling": "entityculling", "immediatelyfast": "immediatelyfast",
           "dynamic-fps": "dynamic_fps", "moreculling": "moreculling"}

SLOTS = [
    {"key": "render", "label": "Быстрый рендер", "desc": "Главный прирост FPS: переписанный движок отрисовки",
     "cands": ["sodium", "embeddium", "rubidium"], "same": {"sodium", "embeddium", "rubidium", "optifine"}, "core": True},
    {"key": "shaders", "label": "Шейдеры", "desc": "Поддержка шейдерпаков (вместо OptiFine)",
     "cands": None, "same": {"iris", "oculus", "optifine"}, "core": True},
    {"key": "modernfix", "label": "Быстрая загрузка", "desc": "Быстрее запуск игры и меньше расход памяти",
     "cands": ["modernfix"], "same": {"modernfix"}, "core": True},
    {"key": "memory", "label": "Меньше памяти", "desc": "Сильно снижает расход оперативной памяти",
     "cands": ["ferrite-core"], "same": {"ferritecore"}},
    {"key": "logic", "label": "Быстрая логика мира", "desc": "Оптимизация мобов, физики и тиков сервера",
     "cands": ["lithium", "canary", "radium"], "same": {"lithium", "canary", "radium"}},
    {"key": "culling", "label": "Отсечение невидимого", "desc": "Не рисует мобов и сундуки за стенами",
     "cands": ["entityculling"], "same": {"entityculling"}},
    {"key": "fastrender", "label": "Быстрый интерфейс", "desc": "Ускоряет отрисовку текста, HUD и частиц",
     "cands": ["immediatelyfast"], "same": {"immediatelyfast"}},
    {"key": "dynfps", "label": "Экономия в фоне", "desc": "Снижает FPS, когда окно свёрнуто или неактивно",
     "cands": ["dynamic-fps"], "same": {"dynamic_fps"}},
]
SHADERS_FOR = {"sodium": "iris", "embeddium": "oculus", "rubidium": "oculus"}


def _first_version(slug, mc, loader):
    try:
        vers = sources.mr_versions(slug, "mod", mc, loader)
    except Exception:  # noqa: BLE001 — нет проекта/версии/сети
        return None
    return content._pick(vers)  # noqa: SLF001


def plan(inst_id):
    inst = instances.get(inst_id)
    loader, mc = inst.get("loader", "vanilla"), inst["mc"]
    if loader == "vanilla":
        return {"loader": loader, "items": [], "needLoader": True}
    have = {i.lower() for i in content.installed_mod_ids(inst_id)}

    # кандидаты всех слотов проверяем параллельно
    all_slugs = {s for slot in SLOTS for s in (slot["cands"] or [])} | {"iris", "oculus"}
    with ThreadPoolExecutor(8) as pool:
        found = dict(zip(all_slugs, pool.map(lambda s: _first_version(s, mc, loader), all_slugs)))

    items, render_slug = [], None
    for slot in SLOTS:
        cands = slot["cands"]
        if slot["key"] == "shaders":
            if render_slug:
                cands = [SHADERS_FOR[render_slug]]
            else:  # рендер уже стоит — подбираем шейдеры под него
                cands = ["iris"] if "sodium" in have else ["oculus"] if have & {"embeddium", "rubidium"} else ["iris", "oculus"]
        item = {"key": slot["key"], "label": slot["label"], "desc": slot["desc"], "core": slot.get("core", False)}
        present = have & slot["same"]
        if "optifine" in have and slot["key"] in ("render", "shaders"):
            item.update(status="conflict", reason="Стоит OptiFine — он несовместим с этими модами. Удалите OptiFine, чтобы поставить их.")
        elif present:
            item.update(status="installed", reason="Уже установлено: " + ", ".join(sorted(present)))
            if slot["key"] == "render":
                render_slug = None
        else:
            pick = next(((s, found.get(s)) for s in cands if found.get(s)), None)
            if pick:
                slug, v = pick
                if slot["key"] == "render":
                    render_slug = slug
                item.update(status="install", slug=slug, version={"id": v["id"], "number": v["number"]},
                            project=v["project"])
            else:
                item.update(status="unavailable", reason=f"Нет версии для Minecraft {mc} ({loader})")
        items.append(item)

    # названия и иконки проектов
    slugs = [i["slug"] for i in items if i.get("slug")]
    with ThreadPoolExecutor(8) as pool:
        projs = dict(zip(slugs, pool.map(lambda s: _safe_project(s), slugs)))
    for i in items:
        p = projs.get(i.get("slug"))
        if p:
            i["title"], i["icon"], i["project"] = p["title"], p["icon"], p["id"]
    return {"loader": loader, "mc": mc, "items": items}


def _safe_project(slug):
    try:
        return sources.mr_project(slug)
    except Exception:  # noqa: BLE001
        return None


def install(inst_id, items, task):
    """items: [{project, version, title}] из plan(); ставит по очереди (с зависимостями)."""
    task.set_max(len(items))
    done, failed = [], []
    seen = set()
    for n, it in enumerate(items):
        task.set_status(f"Установка {it.get('title') or it['project']}")
        try:
            content.install_project("modrinth", "mod", inst_id, it["project"], it["version"], task, _seen=seen)
            done.append(it.get("title"))
        except Exception as e:  # noqa: BLE001 — один мод не должен ронять остальные
            failed.append(f"{it.get('title')}: {e}")
        task.set_progress(n + 1)
    if failed and not done:
        raise RuntimeError("; ".join(failed))
    return {"installed": done, "failed": failed}

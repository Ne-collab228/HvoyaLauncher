"""Проверка выделенной памяти перед запуском: слишком много для системы, мало для модов, мало свободно сейчас."""
import os

from . import config, instances
from .util import mem_status


def recommended(mods):
    if mods == 0:
        return 2048
    if mods < 50:
        return 3072
    if mods < 120:
        return 4096
    if mods < 250:
        return 6144
    return 8192


def _count_mods(inst_id):
    folder = os.path.join(instances.game_dir(inst_id), "mods")
    return sum(1 for n in os.listdir(folder) if n.endswith(".jar")) if os.path.isdir(folder) else 0


def gb(mb):
    return f"{mb / 1024:.1f}".replace(".0", "") + " ГБ"


def system_limit(total):
    """Сколько можно отдать игре, не задушив Windows."""
    return max(1024, total - (3072 if total > 8192 else 2048))


def check(inst_id):
    settings = config.load()
    inst = instances.get(inst_id)
    ram = int(inst.get("ramMax") or settings["ramMax"])
    total, avail = mem_status()
    mods = _count_mods(inst_id) if inst.get("loader", "vanilla") != "vanilla" else 0
    rec = min(recommended(mods), system_limit(total))
    limit = system_limit(total)
    issues = []
    if ram > limit:
        issues.append({"level": "bad", "key": "high",
                       "text": f"Игре выделено {gb(ram)} из {gb(total)} — Windows останется слишком мало, "
                               f"компьютер начнёт тормозить или игра вылетит. Лучше не больше {gb(limit)}."})
    if ram < rec:
        issues.append({"level": "bad" if ram < rec * 0.7 else "warn", "key": "low",
                       "text": f"Для {mods} модов выделено мало памяти ({gb(ram)}) — возможны лаги и вылеты "
                               f"«OutOfMemoryError». Рекомендуется {gb(rec)}."})
    if avail < ram * 0.8 and ram <= limit:
        issues.append({"level": "warn", "key": "free",
                       "text": f"Сейчас свободно только {gb(avail)} — закройте браузер и другие программы, "
                               f"иначе игре не хватит памяти."})
    return {"ram": ram, "total": total, "avail": avail, "mods": mods, "recommended": rec, "limit": limit,
            "issues": issues, "own": bool(inst.get("ramMax"))}

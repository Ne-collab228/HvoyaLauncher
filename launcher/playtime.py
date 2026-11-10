"""Учёт времени в игре.

Общий счётчик — в instance.json (playtime, lastPlayed, sessions), разбивка по дням —
в data/playtime.json: {"days": {"2026-11-10": {"<id>": секунды}}}.
Пока игра идёт, game.py сохраняет время раз в минуту — если закрыть лаунчер,
наигранное не пропадёт.
"""
import datetime
import os
import threading

from . import instances
from .util import DATA, read_json, write_json

PATH = os.path.join(DATA, "playtime.json")
_lock = threading.Lock()


def _split_days(start, end):
    """Разбивает отрезок времени по календарным дням (игра через полночь)."""
    out = {}
    t = start
    while t < end:
        d = datetime.date.fromtimestamp(t)
        midnight = datetime.datetime.combine(d + datetime.timedelta(days=1), datetime.time()).timestamp()
        seg = min(end, midnight)
        out[d.isoformat()] = out.get(d.isoformat(), 0) + (seg - t)
        t = seg
    return out


def _update_instance(inst_id, fn):
    with instances._lock:  # noqa: SLF001 — тот же замок, что у instances.update
        try:
            inst = instances.get(inst_id)
        except (KeyError, ValueError):
            return None
        fn(inst)
        instances.save(inst)
        return inst


def session_started(inst_id, ts):
    def f(inst):
        inst["sessions"] = int(inst.get("sessions") or 0) + 1
        inst["lastPlayed"] = int(ts)
    _update_instance(inst_id, f)


def add(inst_id, start, end):
    """Добавляет отрезок игры. Возвращает новый общий счётчик сборки."""
    if end <= start:
        return None
    parts = _split_days(start, end)
    with _lock:
        data = read_json(PATH, {}) or {}
        days = data.setdefault("days", {})
        for d, secs in parts.items():
            day = days.setdefault(d, {})
            day[inst_id] = round(day.get(inst_id, 0) + secs, 1)
        write_json(PATH, data)

    def f(inst):
        inst["_acc"] = float(inst.get("_acc") or 0) + (end - start)  # дробные секунды между сохранениями
        whole = int(inst["_acc"])
        inst["_acc"] = round(inst["_acc"] - whole, 3)
        inst["playtime"] = int(inst.get("playtime") or 0) + whole
        inst["lastPlayed"] = int(end)
    inst = _update_instance(inst_id, f)
    return inst and inst["playtime"]


def stats():
    data = read_json(PATH, {}) or {}
    days = {d: {k: int(v) for k, v in m.items()} for d, m in (data.get("days") or {}).items()}
    return {"days": days}


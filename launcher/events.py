"""Отправка событий в UI и фоновые задачи с прогрессом."""
import itertools
import json
import threading
import time
import traceback

_window = None
_lock = threading.Lock()


def set_window(w):
    global _window
    _window = w


def emit(kind, **data):
    data["type"] = kind
    w = _window
    if w is None:
        return
    try:
        w.evaluate_js("window.hvEvent && window.hvEvent(%s)" % json.dumps(data))
    except Exception:  # noqa: BLE001 — окно могло закрыться
        pass


_STATUS_RU = [
    ("Download Libraries", "Загрузка библиотек"),
    ("Download Assets", "Загрузка ресурсов"),
    ("Install java runtime", "Установка Java"),
    ("Download Java", "Загрузка Java"),
    ("Running fabric installer", "Установка Fabric"),
    ("Running quilt installer", "Установка Quilt"),
    ("Running Forge installer", "Установка Forge"),
    ("Running NeoForge installer", "Установка NeoForge"),
    ("Download", "Загрузка"),
    ("Installation complete", "Установка завершена"),
]


def _ru(status):
    for en, ru in _STATUS_RU:
        if status.lower().startswith(en.lower()):
            return ru + status[len(en):]
    return status


class Task:
    _ids = itertools.count(1)

    def __init__(self, title, inst=None):
        self.id = next(self._ids)
        self.title = title
        self.inst = inst
        self.status = ""
        self.progress = 0
        self.max = 0
        self._last = 0.0
        self._emit(True)

    def _emit(self, force=False, **extra):
        now = time.monotonic()
        if not force and now - self._last < 0.1:
            return
        self._last = now
        emit("task", id=self.id, title=self.title, inst=self.inst, status=self.status,
             progress=self.progress, max=self.max, **extra)

    def set_status(self, s):
        self.status = _ru(str(s))
        self._emit()

    def set_progress(self, v):
        self.progress = int(v)
        self._emit()

    def set_max(self, v):
        self.max = int(v)
        self.progress = 0
        self._emit()

    def counter(self, done, total):
        self.max = total
        self.progress = done
        self._emit(done == total)

    def callback(self):
        return {"setStatus": self.set_status, "setProgress": self.set_progress, "setMax": self.set_max}

    def finish(self, error=None, result=None):
        emit("task", id=self.id, title=self.title, inst=self.inst, status=self.status,
             progress=self.max, max=self.max, done=True, error=error, result=result)


def run_task(title, fn, inst=None):
    """Запускает fn(task) в фоне, возвращает id задачи."""
    task = Task(title, inst)

    def worker():
        try:
            res = fn(task)
            task.finish(result=res if isinstance(res, (dict, list, str, int, type(None))) else None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            task.finish(error=str(e) or e.__class__.__name__)

    threading.Thread(target=worker, daemon=True).start()
    return task.id

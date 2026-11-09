"""Общие утилиты: пути, JSON, HTTP, загрузки."""
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter

# minecraft-launcher-lib качает без таймаута — при подвисшем соединении загрузка ждала бы вечно.
# Ставим таймаут по умолчанию на все запросы: зависшая загрузка падает и перезапускается.
_orig_request = requests.Session.request


def _request_with_timeout(self, method, url, **kwargs):
    if kwargs.get("timeout") is None:
        kwargs["timeout"] = (15, 30)  # подключение, ожидание данных
    return _orig_request(self, method, url, **kwargs)


requests.Session.request = _request_with_timeout

APP_NAME = "Hvoya Launcher"
APP_VERSION = "1.2.0"
UA = f"HvoyaLauncher/{APP_VERSION}"


# ---------------------------------------------------------------- paths
def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w") as f:
            f.write("1")
        os.remove(probe)
        return True
    except OSError:
        return False


BASE = _base_dir()
DATA = os.path.join(BASE, "data")
if not _writable(DATA):  # например, лаунчер лежит в Program Files
    DATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "HvoyaLauncher")
SHARED = os.path.join(DATA, "minecraft")      # versions / libraries / assets / runtime
INSTANCES = os.path.join(DATA, "instances")   # отдельная папка на каждую сборку
CACHE = os.path.join(DATA, "cache")
for _d in (DATA, SHARED, INSTANCES, CACHE):
    os.makedirs(_d, exist_ok=True)


def resource(*parts):
    root = getattr(sys, "_MEIPASS", BASE)
    return os.path.join(root, *parts)


# ---------------------------------------------------------------- json
def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------- http
_session = None
_session_lock = threading.Lock()


def http():
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            s.headers["User-Agent"] = UA
            adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=2)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            _session = s
        return _session


def get_json(url, **kw):
    kw.setdefault("timeout", 30)
    r = http().get(url, **kw)
    r.raise_for_status()
    return r.json()


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(urls, path, sha1=None, timeout=60):
    """Скачивает файл (с повтором и проверкой sha1). urls — строка или список зеркал."""
    if isinstance(urls, str):
        urls = [urls]
    if sha1 and os.path.isfile(path) and sha1_file(path) == sha1:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    last = None
    for attempt in range(3):
        for url in urls:
            try:
                h = hashlib.sha1()
                with http().get(url, stream=True, timeout=timeout) as r:
                    r.raise_for_status()
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                            h.update(chunk)
                if sha1 and h.hexdigest() != sha1:
                    raise IOError(f"Неверная контрольная сумма: {os.path.basename(path)}")
                os.replace(tmp, path)
                return path
            except Exception as e:  # noqa: BLE001
                last = e
        time.sleep(1 + attempt)
    try:
        os.remove(tmp)
    except OSError:
        pass
    raise last


def download_many(items, progress=None, workers=8):
    """items: [(urls, path, sha1)]; progress(done, total)."""
    total = len(items)
    done = 0
    if progress:
        progress(0, total)
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(download, u, p, s) for u, p, s in items]
        for fut in as_completed(futures):
            fut.result()
            done += 1
            if progress:
                progress(done, total)


def safe_join(root, rel):
    root = os.path.abspath(root)
    p = os.path.abspath(os.path.join(root, rel))
    if p != root and not p.startswith(root + os.sep):
        raise ValueError(f"Недопустимый путь: {rel}")
    return p


def slugify(name):
    s = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:48] or "instance"


def total_ram_mb():
    try:
        import ctypes

        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMSTAT()
        st.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return int(st.ullTotalPhys // (1024 * 1024))
    except Exception:  # noqa: BLE001
        return 8192

"""Скриншоты сборки + маленький локальный http-сервер, чтобы UI грузил картинки напрямую (а не base64)."""
import os
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote

from . import instances
from .util import recycle, safe_join

EXTS = (".png", ".jpg", ".jpeg")
_TOKEN = secrets.token_urlsafe(16)
_server = {"port": None}
_lock = threading.Lock()


def _dir(inst_id):
    return os.path.join(instances.game_dir(inst_id), "screenshots")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401 — без спама в консоль
        pass

    def do_GET(self):  # noqa: N802
        parts = self.path.split("?")[0].strip("/").split("/")
        try:
            if len(parts) != 3 or parts[0] != _TOKEN:
                raise PermissionError
            if parts[1] == "__img__":  # картинки модов/паков с CDN — через Python, с зеркалами и кэшем
                path = _remote_image(parts[2])
                ok = True
            elif parts[1] == "__bg__":  # фоны оформления (looks.py)
                from .looks import BG_DIR
                from .looks import EXTS as BG_EXTS
                path = safe_join(BG_DIR, unquote(parts[2]))
                ok = path.lower().endswith(BG_EXTS)
            else:
                path = safe_join(_dir(unquote(parts[1])), unquote(parts[2]))
                ok = path.lower().endswith(EXTS)
            if not ok or not os.path.isfile(path):
                raise FileNotFoundError
            with open(path, "rb") as f:
                data = f.read()
        except PermissionError:
            self.send_error(403)
            return
        except (OSError, ValueError, KeyError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", _mime(path, data))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400" if parts[1] == "__img__" else "max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


# Хосты картинок, которые UI раньше грузил напрямую: без VPN они бывают недоступны, а WebView
# зеркал не знает. Через этот прокси картинку качает util.http() (подмена на зеркала MCIM).
_IMG_HOSTS = ("cdn.modrinth.com", "media.forgecdn.net", "edge.forgecdn.net", "mediafilez.forgecdn.net")
_img_locks = {}


def _mime(path, data):
    if data[1:4] == b"PNG":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    if data.lstrip()[:5] in (b"<?xml", b"<svg ") or path.lower().endswith(".svg"):
        return "image/svg+xml"
    return "image/jpeg"


def _remote_image(token):
    """token — base64url адреса картинки. Возвращает путь к файлу в кэше (качает при первом запросе)."""
    import base64
    import hashlib
    from urllib.parse import urlsplit

    from . import util
    url = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or u.hostname not in _IMG_HOSTS:
        raise PermissionError
    folder = os.path.join(util.CACHE, "img")
    path = os.path.join(folder, hashlib.sha1(url.encode()).hexdigest())
    if os.path.isfile(path):
        return path
    with _lock:
        lk = _img_locks.setdefault(path, threading.Lock())
    with lk:
        if not os.path.isfile(path):
            data = _fetch_image(url, u.hostname)
            if not data:
                raise FileNotFoundError
            os.makedirs(folder, exist_ok=True)
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
    return path


_img_down = {}       # хост CDN → время сбоя: следующие картинки сразу через wsrv.nl


def _fetch_image(url, host):
    """Сначала напрямую (util.http сам попробует зеркало MCIM — но MCIM отдаёт только то, что у него
    в кэше, остальное редиректит на заблокированный CDN), потом wsrv.nl — он качает картинку у себя."""
    from urllib.parse import quote

    import requests

    from . import util
    proxy = "https://wsrv.nl/?url=" + quote(url, safe="")
    direct_first = time.time() - _img_down.get(host, 0) > 600
    order = [url, proxy] if direct_first else [proxy, url]
    for src in order:
        try:
            r = util.http().get(src, timeout=(6, 20))
            if r.status_code == 200 and r.content and not r.content.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                return r.content
        except (requests.RequestException, OSError):
            pass
        if src == url:
            _img_down[host] = time.time()
    return None


def img_base():
    return _base_url() + "/__img__/"


def _base_url():
    with _lock:
        if _server["port"] is None:
            srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True, name="shots-http").start()
            _server["port"] = srv.server_address[1]
    return f"http://127.0.0.1:{_server['port']}/{_TOKEN}"


def list_shots(inst_id):
    d = _dir(inst_id)
    if not os.path.isdir(d):
        return []
    base = _base_url()
    out = []
    for n in os.listdir(d):
        p = os.path.join(d, n)
        if n.lower().endswith(EXTS) and os.path.isfile(p):
            st = os.stat(p)
            out.append({"name": n, "size": st.st_size, "time": int(st.st_mtime),
                        "url": f"{base}/{quote(inst_id)}/{quote(n)}?v={int(st.st_mtime)}"})
    out.sort(key=lambda s: -s["time"])
    return out


def delete(inst_id, names):
    for n in names:
        recycle(safe_join(_dir(inst_id), n))
    return list_shots(inst_id)


def reveal(inst_id, name):
    p = safe_join(_dir(inst_id), name)
    subprocess.Popen(["explorer", "/select,", p], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # noqa: S603,S607


def copy_to_clipboard(inst_id, name):
    """Копирование картинки средствами Windows (на случай, если буфер обмена браузера недоступен)."""
    p = safe_join(_dir(inst_id), name)
    ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
          f"$i=[System.Drawing.Image]::FromFile('{p.replace(chr(39), chr(39) * 2)}');"
          "[System.Windows.Forms.Clipboard]::SetImage($i);$i.Dispose()")
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True,  # noqa: S603,S607
                       timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("Не удалось скопировать: " + (r.stderr or "").strip()[:200])
    return True

"""Локальный прокси Yggdrasil API Ely.by для authlib-injector.

Сервер Ely.by на рваной сети отвечает не на каждый запрос: часть запросов висит 15-30 с.
Minecraft запрашивает профиль со скином один раз и до перезапуска запоминает неудачу, поэтому
скина в игре нет. Игра ходит сюда (127.0.0.1), а прокси шлёт запрос к Ely.by: если ответа нет
через пару секунд, параллельно отправляет повторный, и берёт первый успешный ответ. Удачные
ответы с профилями сохраняются на диск: если Ely.by не ответил совсем, игра получит последний
сохранённый ответ.
"""
import base64
import hashlib
import json
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from .util import CACHE, SHARED, UA, _orig_request

UPSTREAM = "https://account.ely.by/api/authlib-injector"
HEDGE_AFTER = 2.5      # с, через сколько отправить параллельный повтор
MAX_ATTEMPTS = 4
DEADLINE = 12.0        # с, authlib в игре ждёт около 15 с
TRY_TIMEOUT = (4, 8)   # подключение, ожидание данных одной попытки
CACHE_PATH = os.path.join(CACHE, "ely_profiles.json")
CACHEABLE = ("/sessionserver/session/minecraft/profile/",)
SKIP_REQ = {"host", "content-length", "connection", "accept-encoding", "keep-alive"}
SKIP_RESP = {"content-length", "content-encoding", "transfer-encoding", "connection", "keep-alive",
             "x-authlib-injector-api-location"}  # иначе authlib-injector уйдёт напрямую на Ely.by

_session = requests.Session()
_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="ely-proxy")
_lock = threading.Lock()
_cache = None
_server = None


class _Resp:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body


def _load_cache():
    global _cache
    if _cache is None:
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _cache_get(key):
    with _lock:
        item = _load_cache().get(key)
    if not item:
        return None
    return _Resp(200, {"Content-Type": item.get("type", "application/json")}, item["body"].encode("utf-8"))


def _cache_put(key, resp):
    try:
        body = resp.body.decode("utf-8")
    except UnicodeDecodeError:
        return
    with _lock:
        c = _load_cache()
        c[key] = {"body": body, "type": resp.headers.get("Content-Type", "application/json"), "t": int(time.time())}
        if len(c) > 500:  # держим только свежие
            for k in sorted(c, key=lambda k: c[k].get("t", 0))[:len(c) - 500]:
                del c[k]
        try:
            tmp = CACHE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(c, f)
            os.replace(tmp, CACHE_PATH)
        except OSError:
            pass


def _attempt(method, url, headers, body):
    r = _orig_request(_session, method, url, headers=headers, data=body, timeout=TRY_TIMEOUT,
                      allow_redirects=False)
    if r.status_code >= 500:
        raise requests.HTTPError(f"HTTP {r.status_code}")
    hdrs = {k: v for k, v in r.headers.items() if k.lower() not in SKIP_RESP}
    return _Resp(r.status_code, hdrs, r.content)


def fetch(method, path, headers=None, body=None):
    """Запрос к Ely.by с параллельными повторами. Возвращает _Resp или None."""
    url = UPSTREAM + path
    headers = dict(headers or {})
    headers.setdefault("User-Agent", UA)
    deadline = time.monotonic() + DEADLINE
    pending, attempts = set(), 0
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return None
        if attempts < MAX_ATTEMPTS:
            pending.add(_pool.submit(_attempt, method, url, headers, body))
            attempts += 1
        elif not pending:
            return None
        done, pending = wait(pending, timeout=min(HEDGE_AFTER, left) if attempts < MAX_ATTEMPTS else left,
                             return_when=FIRST_COMPLETED)
        for f in done:
            if f.exception() is None:
                return f.result()


def _is_cacheable(method, path):
    return method == "GET" and (path.split("?")[0] in ("", "/") or path.startswith(CACHEABLE))


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _handle(self):
        method = self.command
        path = self.path if self.path.startswith("/") else "/" + self.path
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in SKIP_REQ}
        cacheable = _is_cacheable(method, path)
        key = path.split("?")[0]

        resp = fetch(method, path, headers, body)
        if resp is not None and cacheable and resp.status == 200 and resp.body:
            _cache_put(key, resp)
        if resp is None and cacheable:
            resp = _cache_get(key)
        if resp is None:
            resp = _Resp(502, {"Content-Type": "application/json"},
                         b'{"error":"Unavailable","errorMessage":"Ely.by is not responding"}')
        try:
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)
        except OSError:
            pass

    do_GET = do_POST = do_PUT = do_DELETE = _handle


def url():
    """Запускает прокси (один раз за время работы лаунчера) и возвращает его адрес."""
    global _server
    with _lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            _server.daemon_threads = True
            threading.Thread(target=_server.serve_forever, name="ely-proxy", daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}"


def _texture_file(url):
    """Путь, где Minecraft ищет скачанный скин: assets/skins/xx/sha1(utf-16le(имя файла))."""
    name = os.path.splitext(url.rsplit("/", 1)[-1])[0]
    h = hashlib.sha1(name.encode("utf-16-le")).hexdigest()
    return os.path.join(SHARED, "assets", "skins", h[:2], h)


def _prefetch_textures(profile_body):
    """Скачивает скин/плащ в кэш игры: сама игра качает его один раз и при обрыве остаётся без скина."""
    try:
        prop = next(p for p in json.loads(profile_body)["properties"] if p["name"] == "textures")
        textures = json.loads(base64.b64decode(prop["value"] + "==="))["textures"]
    except (ValueError, KeyError, StopIteration, TypeError):
        return
    for tex in textures.values():
        url = tex.get("url") if isinstance(tex, dict) else None
        if not url:
            continue
        path = _texture_file(url)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            continue
        for _ in range(6):
            try:
                r = _attempt("GET", url, {"User-Agent": UA}, None)
            except Exception:  # noqa: BLE001
                continue
            if r.status == 200 and r.body[1:4] == b"PNG":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(r.body)
                os.replace(tmp, path)
            break


def prefetch_profile(uuid):
    """Заранее кладёт свой профиль в кэш прокси, а скин — в кэш игры, пока она запускается."""
    def work():
        path = f"/sessionserver/session/minecraft/profile/{uuid}?unsigned=false"
        r = fetch("GET", path)
        if r is not None and r.status == 200 and r.body:
            _cache_put(path.split("?")[0], r)
        else:
            r = _cache_get(path.split("?")[0])
        if r is not None:
            _prefetch_textures(r.body)
    threading.Thread(target=work, daemon=True).start()

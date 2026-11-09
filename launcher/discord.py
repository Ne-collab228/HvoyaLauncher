"""Discord Rich Presence: «Играет в Hvoya Launcher — <сборка>». Без библиотек — через IPC-канал Discord."""
import json
import os
import struct
import threading
import time
import uuid

from . import config

# Приложение «Hvoya Launcher» на discord.com/developers (ID публичный, секрет не нужен)
APP_ID = "1569421543329767524"
LOADER_NAMES = {"vanilla": "Vanilla", "fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge", "quilt": "Quilt"}

_cond = threading.Condition()
_playing = {}       # inst_id -> activity (последний запущенный — в конце)
_dirty = False
_thread = None


class _Pipe:
    def __init__(self, client_id):
        self.f = None
        for i in range(10):
            try:
                self.f = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)  # noqa: SIM115
                break
            except OSError:
                continue
        if not self.f:
            raise OSError("Discord не запущен")
        self.send(0, {"v": 1, "client_id": client_id})
        op, data = self.recv()
        if op != 1 or data.get("evt") != "READY":
            raise OSError(f"Discord отклонил подключение: {data.get('message') or data}")

    def send(self, op, payload):
        raw = json.dumps(payload).encode()
        self.f.write(struct.pack("<II", op, len(raw)) + raw)

    def recv(self):
        hdr = self._read(8)
        op, n = struct.unpack("<II", hdr)
        return op, json.loads(self._read(n) or b"{}")

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.f.read(n - len(buf))
            if not chunk:
                raise OSError("Канал Discord закрыт")
            buf += chunk
        return buf

    def set_activity(self, activity):
        self.send(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity},
                      "nonce": str(uuid.uuid4())})
        self.recv()

    def close(self):
        try:
            self.f.close()
        except OSError:
            pass


def _activity(inst):
    loader = inst.get("loader", "vanilla")
    state = f"Minecraft {inst.get('mc', '')}" + (f" · {LOADER_NAMES.get(loader, loader)}" if loader != "vanilla" else "")
    mp = inst.get("modpack") or {}
    act = {"details": (inst.get("name") or "Minecraft")[:120], "state": state[:120],
           "timestamps": {"start": int(time.time())},
           "assets": {"large_image": "logo", "large_text": "Hvoya Launcher"}}
    if mp.get("name") and mp["name"] != inst.get("name"):
        act["assets"]["small_text"] = f"Модпак: {mp['name']}"[:120]
    return act


def _worker():
    global _dirty
    pipe, pipe_id = None, None
    while True:
        with _cond:
            while not _dirty:
                _cond.wait(timeout=30)
                if not _dirty and pipe is None and _playing:
                    _dirty = True  # Discord мог запуститься позже игры — пробуем снова
            _dirty = False
            want = list(_playing.values())[-1] if _playing else None
        s = config.load()
        cid = (s.get("discordClientId") or "").strip() or APP_ID
        enabled = s.get("discordRpc") and cid.isdigit()
        try:
            if not enabled or want is None:
                if pipe:
                    pipe.set_activity(None)
                    pipe.close()
                    pipe = None
                continue
            if pipe is None or pipe_id != cid:
                if pipe:
                    pipe.close()
                pipe, pipe_id = _Pipe(cid), cid
            pipe.set_activity(want)
        except (OSError, ValueError, struct.error):
            if pipe:
                pipe.close()
            pipe = None


def _kick():
    global _dirty, _thread
    with _cond:
        _dirty = True
        if _thread is None:
            _thread = threading.Thread(target=_worker, daemon=True, name="discord-rpc")
            _thread.start()
        _cond.notify()


def playing(inst_id, inst):
    with _cond:
        _playing.pop(inst_id, None)
        _playing[inst_id] = _activity(inst)
    _kick()


def stopped(inst_id):
    with _cond:
        _playing.pop(inst_id, None)
    _kick()


def refresh():
    """Настройки поменялись — переотправить статус."""
    _kick()

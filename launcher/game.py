"""Установка версий/загрузчиков и запуск игры."""
import collections
import os
import shlex
import subprocess
import sys
import threading
import time

import minecraft_launcher_lib as mll
import requests
import urllib3
from minecraft_launcher_lib import command, install, mod_loader, runtime

from . import accounts, config, events, instances, storage
from .util import APP_VERSION, SHARED

# Установщики Forge/Fabric запускают java — не показываем консольные окна.
if sys.platform == "win32":
    _orig_init = subprocess.Popen.__init__

    def _no_console_init(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_console_init

_version_cache = {"t": 0, "list": []}
_running = {}          # inst_id -> Popen
_killed = set()
_logs = {}             # inst_id -> deque
_lock = threading.Lock()
LOG_LIMIT = 5000


# ---------------------------------------------------------------- versions
def mc_versions():
    if time.time() - _version_cache["t"] > 600 or not _version_cache["list"]:
        lst = mll.utils.get_version_list()
        _version_cache["list"] = [{"id": v["id"], "type": v["type"],
                                   "date": v["releaseTime"].strftime("%Y-%m-%d")} for v in lst]
        _version_cache["t"] = time.time()
    return _version_cache["list"]


def loader_versions(loader, mc):
    if loader == "vanilla":
        return []
    ml = mod_loader.get_mod_loader(loader)
    try:
        return ml.get_loader_versions(mc, False)
    except Exception:  # noqa: BLE001
        return []


def _java_for(version_id):
    try:
        info = runtime.get_version_runtime_information(version_id, SHARED)
    except Exception:  # noqa: BLE001
        info = None
    if info:
        return runtime.get_executable_path(info["name"], SHARED)
    return None


def _version_ok(vid):
    # версия, родитель, Java и индекс ассетов на месте (после очистки хранилища что-то могло пропасть)
    return storage.version_ready(vid)


def ensure_installed(inst, task, force=False):
    if not force and inst.get("installed") and _version_ok(inst.get("versionId")):
        return inst["versionId"]
    mc, loader = inst["mc"], inst["loader"]
    cb = task.callback()
    for attempt in range(6):  # уже скачанные файлы повторно не качаются — просто продолжаем
        try:
            task.set_status(f"Установка Minecraft {mc}")
            install.install_minecraft_version(mc, SHARED, callback=cb)
            if loader == "vanilla":
                vid = mc
            else:
                ml = mod_loader.get_mod_loader(loader)
                lv = inst.get("loaderVersion") or ml.get_latest_loader_version(mc)
                task.set_status(f"Установка {ml.get_name()} {lv}")
                vid = ml.install(mc, SHARED, loader_version=lv, callback=cb, java=_java_for(mc) or "java")
                inst["loaderVersion"] = lv
            break
        except (requests.RequestException, urllib3.exceptions.HTTPError, ConnectionError, TimeoutError,
                mll.exceptions.InvalidChecksum) as e:
            if attempt == 5:
                raise RuntimeError(f"Ошибка сети при загрузке файлов: {e}") from e
            task.set_status(f"Сбой сети, повтор ({attempt + 1})…")
            time.sleep(2)
    fresh = instances.get(inst["id"])
    fresh.update({"versionId": vid, "installed": True, "loaderVersion": inst.get("loaderVersion", "")})
    instances.save(fresh)
    inst.update(fresh)
    return vid


# ---------------------------------------------------------------- running
def is_running(inst_id):
    p = _running.get(inst_id)
    return p is not None and p.poll() is None


def running_ids():
    return [i for i in list(_running) if is_running(i)]


def get_log(inst_id):
    return list(_logs.get(inst_id, []))


def kill(inst_id):
    p = _running.get(inst_id)
    if p and p.poll() is None:
        _killed.add(inst_id)
        p.kill()


def _log(inst_id, line, pending):
    _logs.setdefault(inst_id, collections.deque(maxlen=LOG_LIMIT)).append(line)
    pending.append(line)


def launch(inst_id, task, on_started=None):
    if is_running(inst_id):
        raise RuntimeError("Сборка уже запущена")
    settings = config.load()
    acc = accounts.prepare_launch()
    inst = instances.get(inst_id)
    vid = ensure_installed(inst, task)

    ram = int(inst.get("ramMax") or settings["ramMax"])
    ram_min = min(int(settings.get("ramMin") or 512), ram)
    jvm = [f"-Xmx{ram}M", f"-Xms{ram_min}M", "-Dfile.encoding=UTF-8",
           "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]
    extra = (inst.get("jvmArgs") or settings.get("jvmArgs") or "").strip()
    if extra:
        jvm += shlex.split(extra, posix=False)
    if acc["type"] == "elyby":
        jvm.insert(0, f"-javaagent:{accounts.ensure_authlib(task)}=ely.by")

    width = inst.get("width") or settings.get("width")
    height = inst.get("height") or settings.get("height")
    opts = {
        "username": acc["name"], "uuid": acc["uuid"], "token": acc["token"],
        "jvmArguments": jvm, "launcherName": "HvoyaLauncher", "launcherVersion": APP_VERSION,
        "gameDirectory": instances.game_dir(inst_id),
    }
    if width and height:
        opts.update(customResolution=True, resolutionWidth=str(width), resolutionHeight=str(height))
    if inst.get("server"):
        host, _, port = inst["server"].partition(":")
        opts["server"] = host
        if port:
            opts["port"] = port
    java = (inst.get("javaPath") or settings.get("javaPath") or "").strip()
    if java:
        opts["executablePath"] = java

    cmd = command.get_minecraft_command(vid, SHARED, opts)
    if cmd[0] == "java" and not java:
        jp = _java_for(vid)
        if jp:
            cmd[0] = jp
    task.set_status("Запуск игры")

    _logs[inst_id] = collections.deque(maxlen=LOG_LIMIT)
    pending = []
    safe_cmd = " ".join("***" if c == acc["token"] and c != "0" else c for c in cmd)
    _log(inst_id, f"[Hvoya] Аккаунт: {acc['name']} ({acc['type']}), версия {vid}, RAM {ram} МБ", pending)
    _log(inst_id, f"[Hvoya] Команда: {safe_cmd}", pending)
    try:
        proc = subprocess.Popen(cmd, cwd=instances.game_dir(inst_id), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise RuntimeError(f"Java не найдена: {cmd[0]}. Укажите путь в настройках.") from e
    _running[inst_id] = proc
    started = time.time()
    events.emit("game", inst=inst_id, state="running")
    if on_started:
        on_started()

    def flusher():
        while True:
            alive = proc.poll() is None
            if pending:
                with _lock:
                    batch = pending[:]
                    del pending[:]
                events.emit("log", inst=inst_id, lines=batch)
            if not alive and not pending:
                break
            time.sleep(0.25)

    def reader():
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            with _lock:
                _log(inst_id, line, pending)
        code = proc.wait()
        elapsed = int(time.time() - started)
        try:
            i = instances.get(inst_id)
            i["playtime"] = int(i.get("playtime") or 0) + elapsed
            i["lastPlayed"] = int(time.time())
            instances.save(i)
        except Exception:  # noqa: BLE001
            pass
        with _lock:
            _log(inst_id, f"[Hvoya] Игра завершена, код {code}", pending)
        time.sleep(0.4)
        events.emit("game", inst=inst_id, state="stopped", code=code,
                    crashed=code != 0 and inst_id not in _killed)
        _killed.discard(inst_id)
        _running.pop(inst_id, None)

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=flusher, daemon=True).start()
    return {"pid": proc.pid}

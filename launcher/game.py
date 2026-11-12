"""Установка версий/загрузчиков и запуск игры."""
import collections
import os
import shlex
import subprocess
import sys
import threading
import time
import traceback

import minecraft_launcher_lib as mll
import requests
import urllib3
from minecraft_launcher_lib import command, install, mod_loader, runtime

from . import accounts, config, crash, discord, elyproxy, events, instances, playtime, skins, storage
from .util import APP_VERSION, SHARED

# Установщики Forge/Fabric запускают java — не показываем консольные окна.
if sys.platform == "win32":
    _orig_init = subprocess.Popen.__init__

    def _no_console_init(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_console_init


# mll считает версию MC из номера NeoForge как "1." + первые две цифры (21.11.48 → 1.21.11).
# С Minecraft 26.x NeoForge нумеруется "26.2.0.93" (полная версия MC + сборка) — mll давал "1.26.2".
def _neoforge_mc(v):
    if v.startswith("0.") or "+" in v:          # 0.x — древние, "+snapshot" — сборки под снапшоты
        return None
    parts = v.split("-")[0].split(".")
    if int(parts[0]) >= 26:
        return ".".join(parts[:3]).removesuffix(".0")
    return "1." + ".".join(parts[:2]).removesuffix(".0")


_NF_MIRROR = "https://bmclapi2.bangbang93.com/maven/net/neoforged/neoforge"


def _nf_key(v):
    """Порядок версий NeoForge: по числам, beta раньше релиза той же версии.
    Зеркало отдаёт maven-metadata не по порядку (26.1.2.126 после 26.3.0.101)."""
    import re
    base, _, tag = v.partition("-")
    return tuple(int(x) for x in re.findall(r"\d+", base)), tag == ""


_nf_mem = {"t": 0.0, "list": None}
_nf_lock = threading.Lock()


def _nf_fetch_one(url, parse):
    from . import util
    s = requests.Session()
    try:
        # мимо util-обёртки: та повторяет запрос до 5 раз с таймаутом 30 с — на заблокированном
        # без VPN хосте это минуты ожидания, а UI в это время пишет «не поддерживает»
        r = util._orig_request(s, "GET", url, timeout=(7, 15))
        r.raise_for_status()
        vs = parse(r)
        if not vs:
            raise ValueError("пустой список")
        return vs
    finally:
        s.close()


def _nf_versions():
    """Список версий NeoForge (старые → новые). Оригинал и зеркало BMCLAPI спрашиваются
    одновременно, берётся первый ответ; если не ответил никто — список с диска с прошлого раза."""
    import concurrent.futures as cf
    import re

    from minecraft_launcher_lib.mod_loader import _neoforge

    from . import util
    with _nf_lock:
        if _nf_mem["list"] and time.time() - _nf_mem["t"] < 600:
            return _nf_mem["list"]
        cache = os.path.join(util.CACHE, "neoforge_versions.json")
        xml = lambda r: re.findall(r"<version>([^<]+)</version>", r.text)  # noqa: E731
        sources = [
            (_neoforge._API_URL, lambda r: r.json()["versions"]),
            ("https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml", xml),
            ("https://maven.creeperhost.net/net/neoforged/neoforge/maven-metadata.xml", xml),
            (_NF_MIRROR + "/maven-metadata.xml", xml),
        ]
        vs, err = None, None
        for attempt in range(2):
            pool = cf.ThreadPoolExecutor(len(sources))
            futs = [pool.submit(_nf_fetch_one, u, p) for u, p in sources]
            try:
                for f in cf.as_completed(futs, timeout=40):
                    try:
                        vs = f.result()
                        break
                    except Exception as e:  # noqa: BLE001
                        err = e
            except cf.TimeoutError as e:
                err = e
            pool.shutdown(wait=False, cancel_futures=True)
            if vs:
                break
        if not vs:
            vs = util.read_json(cache, None)
            if not vs:
                raise err or requests.ConnectionError("NeoForge: нет связи ни с maven.neoforged.net, ни с зеркалом")
            vs = sorted(dict.fromkeys(vs), key=_nf_key)
            _nf_mem.update(t=time.time() - 540, list=vs)   # через минуту попробуем сеть снова
            return vs
        vs = sorted(dict.fromkeys(vs), key=_nf_key)
        _nf_mem.update(t=time.time(), list=vs)
        try:
            util.write_json(cache, vs)
        except Exception:  # noqa: BLE001
            pass
        return vs


def _nf_get_mc_versions(self, stable_only):
    return list(dict.fromkeys(m for m in map(_neoforge_mc, _nf_versions()) if m))


def _nf_get_loader_versions(self, minecraft_version, stable_only):
    return [v for v in reversed(_nf_versions())
            if not (stable_only and "beta" in v) and _neoforge_mc(v) == minecraft_version]


from minecraft_launcher_lib.mod_loader._neoforge import Neoforge as _Neoforge  # noqa: E402
_Neoforge.get_minecraft_versions = _nf_get_mc_versions
_Neoforge.get_loader_versions = _nf_get_loader_versions


def _prefetch_installer_libs(installer_path, minecraft_directory, callback):
    """Установщик NeoForge (java) сам качает свои библиотеки с maven.neoforged.net — без VPN
    он недоступен, а зеркал установщик не знает. Но уже лежащие на диске файлы с верным sha1
    он не качает, поэтому скачиваем всё заранее через util.download (там подмена на зеркала)."""
    import json
    import zipfile

    from . import util
    with zipfile.ZipFile(installer_path) as z:
        names = set(z.namelist())
        libs = []
        for js in ("install_profile.json", "version.json"):
            if js in names:
                libs += json.loads(z.read(js)).get("libraries", [])
        items, seen = [], set()
        for lib in libs:
            a = (lib.get("downloads") or {}).get("artifact") or {}
            path, url = a.get("path"), a.get("url")
            if not path or path in seen:
                continue
            seen.add(path)
            dest = util.safe_join(os.path.join(minecraft_directory, "libraries"), path)
            if "maven/" + path in names:          # файл вшит в установщик — он распакует сам
                continue
            if not url:
                continue
            if a.get("sha1") and os.path.isfile(dest) and util.sha1_file(dest) == a["sha1"]:
                continue
            items.append((url, dest, a.get("sha1")))
    if not items:
        return
    set_status = callback.get("setStatus", lambda s: None)
    set_status(f"Загрузка библиотек NeoForge ({len(items)})")
    set_max, set_prog = callback.get("setMax"), callback.get("setProgress")
    if set_max:
        set_max(len(items))
    import concurrent.futures as cf
    done = 0
    with cf.ThreadPoolExecutor(6) as pool:
        for f in cf.as_completed([pool.submit(_maven_fetch, u, d, s) for u, d, s in items]):
            f.result()
            done += 1
            if set_prog:
                set_prog(done)


# Где ещё лежат библиотеки из maven.neoforged.net / libraries.minecraft.net.
# CreeperHost проксирует весь maven NeoForge; Maven Central — сторонние библиотеки (asm, guava…);
# BMCLAPI — последним: файлы он отдаёт редиректом на медленный cernet.
_MAVEN_BASES = ["https://maven.creeperhost.net/", "https://repo1.maven.org/maven2/",
                "https://bmclapi2.bangbang93.com/maven/"]
_MAVEN_ORIGS = ("https://maven.neoforged.net/releases/", "https://libraries.minecraft.net/",
                "https://maven.minecraftforge.net/")
_base_fails = collections.Counter()
_base_lock = threading.Lock()


def _maven_fetch(url, dest, sha1):
    """Скачивает файл maven, перебирая оригинал и зеркала. Источник, который не ответил,
    дальше пробуется последним — чтобы не ждать таймаут на каждом из десятков файлов."""
    import hashlib

    from . import util
    rel = next((url[len(o):] for o in _MAVEN_ORIGS if url.startswith(o)), None)
    cands = [url] + ([b + rel for b in _MAVEN_BASES] if rel else [])
    last = None
    for attempt in range(3):
        with _base_lock:
            order = sorted(cands, key=lambda u: _base_fails[u.split("/")[2]])
        for u in order:
            host = u.split("/")[2]
            tmp = dest + ".part"
            s = requests.Session()
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                r = util._orig_request(s, "GET", u, stream=True, timeout=(6, 20))
                if r.status_code == 404:
                    r.close()
                    continue            # на этом зеркале файла нет — это не сбой источника
                r.raise_for_status()
                h = hashlib.sha1()
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
                        h.update(chunk)
                if sha1 and h.hexdigest() != sha1:
                    raise IOError(f"неверная контрольная сумма {os.path.basename(dest)} с {host}")
                os.replace(tmp, dest)
                with _base_lock:
                    _base_fails[host] = max(0, _base_fails[host] - 1)
                return
            except Exception as e:  # noqa: BLE001
                last = e
                with _base_lock:
                    _base_fails[host] += 1
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            finally:
                s.close()
        time.sleep(1 + attempt)
    raise requests.ConnectionError(f"Не удалось скачать {os.path.basename(dest)} ни с одного зеркала: {last}")


def _nf_install(self, minecraft_version, minecraft_directory, callback, java, loader_version):
    from minecraft_launcher_lib._helper import SUBPROCESS_STARTUP_INFO, download_file
    from minecraft_launcher_lib.vanilla_launcher import (create_empty_vanilla_launcher_profiles_file,
                                                         do_vanilla_launcher_profiles_exists)
    import tempfile
    if not do_vanilla_launcher_profiles_exists(minecraft_directory):
        create_empty_vanilla_launcher_profiles_file(minecraft_directory)
    with tempfile.TemporaryDirectory(prefix="hvoya-neoforge-") as tempdir:
        installer_path = os.path.join(tempdir, "neoforge-installer.jar")
        download_file(self.get_installer_url(minecraft_version, loader_version), installer_path)
        _prefetch_installer_libs(installer_path, minecraft_directory, callback)
        callback.get("setStatus", lambda s: None)("Running NeoForge installer")
        p = subprocess.run([java, "-jar", installer_path, "--install-client", minecraft_directory],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=tempdir,
                           startupinfo=SUBPROCESS_STARTUP_INFO)
        if p.returncode != 0:
            out = p.stdout.decode("utf-8", "replace").strip().splitlines()
            try:
                with open(os.path.join(SHARED, "neoforge-installer.log"), "w", encoding="utf-8") as f:
                    f.write("\n".join(out))
            except OSError:
                pass
            tail = "\n".join(out[-12:])
            raise RuntimeError(f"Установщик NeoForge завершился с ошибкой (код {p.returncode}):\n{tail}")


_Neoforge.install = _nf_install


# mll качает каждый файл одной попыткой. Ассеты — тысячи файлов в пуле потоков: одна сетевая
# ошибка роняет всю установку, но пул сперва дожидается остальных файлов (прогресс стоит),
# а повтор заново хеширует всё скачанное. На нестабильной сети это выглядит как зависание.
# Поэтому каждый файл mll сам повторяется несколько раз (обычные GET повторяет util.py).
_NET_ERRORS = (requests.RequestException, urllib3.exceptions.HTTPError, ConnectionError, TimeoutError,
               mll.exceptions.InvalidChecksum)
_FILE_TRIES = 10


def _patch_mll_downloads():
    import importlib
    import pkgutil

    from minecraft_launcher_lib import _helper

    orig_download = _helper.download_file

    def download_file(url, path, *args, **kwargs):
        for attempt in range(_FILE_TRIES):
            try:
                return orig_download(url, path, *args, **kwargs)
            except _NET_ERRORS:
                # недокачанный файл без sha1 mll иначе счёл бы готовым
                try:
                    os.remove(path)
                except OSError:
                    pass
                if attempt == _FILE_TRIES - 1:
                    raise
                time.sleep(min(1 + attempt, 5))

    # модули mll импортируют эти функции по имени — подменяем во всех
    names = {info.name for info in pkgutil.walk_packages(mll.__path__, mll.__name__ + ".")}
    # на случай если в собранном exe walk_packages ничего не найдёт
    names.update(mll.__name__ + "." + n for n in (
        "install", "runtime", "forge", "fabric", "quilt", "mrpack",
        "mod_loader._forge", "mod_loader._fabric", "mod_loader._neoforge", "mod_loader._quilt"))
    for n in sorted(names):
        try:
            importlib.import_module(n)
        except Exception:  # noqa: BLE001
            pass
    for name, mod in list(sys.modules.items()):
        if mod is None or not (name == mll.__name__ or name.startswith(mll.__name__ + ".")):
            continue
        if getattr(mod, "download_file", None) is orig_download:
            mod.download_file = download_file


_patch_mll_downloads()

_version_cache = {"t": 0, "list": []}
_running = {}          # inst_id -> Popen
_killed = set()
_started = {}         # inst_id -> время запуска
_sessions = {}        # inst_id -> {"last": время последнего сохранения playtime}
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
    except (requests.RequestException, urllib3.exceptions.HTTPError, OSError) as e:
        raise RuntimeError(f"Нет связи с сервером {ml.get_name()} — проверьте интернет или включите VPN") from e
    except Exception:  # noqa: BLE001
        return []


def mc_at_least(mc, ver):
    import re
    if not re.match(r"^\d+(\.\d+)*$", mc or ""):
        return True      # снапшоты — свежие
    return tuple(int(x) for x in mc.split(".")) >= ver


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
    for attempt in range(20):  # уже скачанные файлы повторно не качаются — просто продолжаем
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
            if attempt == 19:
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


def started_at(inst_id):
    return _started.get(inst_id)


def live_sessions():
    """Для живого счётчика в UI: когда время запущенных сборок сохранялось последний раз."""
    return {i: {"started": _started.get(i), "last": s["last"]} for i, s in list(_sessions.items()) if is_running(i)}


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


def launch(inst_id, task, on_started=None, join=None):
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
        # Игра ходит к Ely.by через локальный прокси с повторами и кэшем (см. elyproxy.py)
        jvm.insert(0, f"-javaagent:{accounts.ensure_authlib(task)}={elyproxy.url()}")
        elyproxy.prefetch_profile(acc["uuid"])

    width = inst.get("width") or settings.get("width")
    height = inst.get("height") or settings.get("height")
    opts = {
        "username": acc["name"], "uuid": acc["uuid"], "token": acc["token"],
        "jvmArguments": jvm, "launcherName": "HvoyaLauncher", "launcherVersion": APP_VERSION,
        "gameDirectory": instances.game_dir(inst_id),
    }
    if width and height:
        opts.update(customResolution=True, resolutionWidth=str(width), resolutionHeight=str(height))
    join = (join or "").strip()
    new_style = bool(join) and mc_at_least(inst["mc"], (1, 20))
    if join and not new_style:
        host, _, port = join.partition(":")
        opts["server"] = host
        if port:
            opts["port"] = port
    elif inst.get("server") and not join:
        host, _, port = inst["server"].partition(":")
        opts["server"] = host
        if port:
            opts["port"] = port
    java = (inst.get("javaPath") or settings.get("javaPath") or "").strip()
    if java:
        opts["executablePath"] = java

    cmd = command.get_minecraft_command(vid, SHARED, opts)
    if new_style:     # Minecraft 1.20+: быстрый вход на сервер
        cmd += ["--quickPlayMultiplayer", join]
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
        note = skins.prepare_launch(inst_id, instances.game_dir(inst_id), acc)
        if note:
            _log(inst_id, note, pending)
    except Exception as e:  # noqa: BLE001 — скин не должен мешать запуску
        _log(inst_id, f"[Hvoya] Не удалось подготовить скин: {e}", pending)
    try:
        proc = subprocess.Popen(cmd, cwd=instances.game_dir(inst_id), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise RuntimeError(f"Java не найдена: {cmd[0]}. Укажите путь в настройках.") from e
    _running[inst_id] = proc
    started = time.time()
    _started[inst_id] = started
    sess = {"last": started, "done": False}
    sess_lock = threading.Lock()
    _sessions[inst_id] = sess
    try:
        playtime.session_started(inst_id, started)
    except Exception:  # noqa: BLE001
        traceback.print_exc()

    def save_time(final=False):
        # время сохраняется раз в минуту, чтобы не потерялось при закрытии лаунчера
        with sess_lock:
            if sess["done"]:
                return
            now = time.time()
            try:
                total = playtime.add(inst_id, sess["last"], now)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                total = None
            sess["last"] = now
            sess["done"] = final
        if total is not None and not final:
            events.emit("playtime", inst=inst_id, playtime=total, last=now)

    def ticker():
        while proc.poll() is None:
            time.sleep(2)
            if time.time() - sess["last"] >= 60:
                save_time()
    events.emit("game", inst=inst_id, state="running")
    discord.playing(inst_id, inst)
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
        save_time(final=True)
        _sessions.pop(inst_id, None)
        with _lock:
            _log(inst_id, f"[Hvoya] Игра завершена, код {code}", pending)
        discord.stopped(inst_id)
        crashed = code != 0 and inst_id not in _killed
        analysis = None
        if crashed:
            time.sleep(1.0)  # краш-репорт дописывается чуть позже выхода процесса
            try:
                analysis = crash.analyze(inst_id, code)
                crash.save_last(inst_id, analysis)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        else:
            time.sleep(0.4)
        events.emit("game", inst=inst_id, state="stopped", code=code, crashed=crashed, analysis=analysis)
        _killed.discard(inst_id)
        _running.pop(inst_id, None)

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=ticker, daemon=True).start()
    threading.Thread(target=flusher, daemon=True).start()
    return {"pid": proc.pid}

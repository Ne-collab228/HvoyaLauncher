"""Обновление лаунчера через релизы GitHub.

Портативный/установленный exe в папке с правом записи: качаем новый HvoyaLauncher.exe,
текущий переименовываем в .old (запущенный exe переименовать можно), ставим новый и перезапускаемся.
Если папка без права записи (например, Program Files) — качаем установщик и запускаем его тихо.
"""
import hashlib
import os
import re
import subprocess
import sys

from .util import APP_VERSION, CACHE, get_json, http, _writable

REPO = "Ne-collab228/HvoyaLauncher"
EXE_ASSET = "HvoyaLauncher.exe"


def _ver(s):
    nums = [int(x) for x in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def frozen():
    return bool(getattr(sys, "frozen", False))


def _latest_release():
    try:
        return get_json(f"https://api.github.com/repos/{REPO}/releases/latest",
                        headers={"Accept": "application/vnd.github+json"}, timeout=15)
    except Exception:  # noqa: BLE001 — лимит API (60 запросов/час с IP): берём тег из редиректа страницы
        r = http().get(f"https://github.com/{REPO}/releases/latest", allow_redirects=False, timeout=15)
        loc = r.headers.get("Location", "")
        m = re.search(r"/releases/tag/([^/?#]+)", loc)
        if not m:
            raise RuntimeError("Не удалось проверить обновления (GitHub недоступен)")
        tag = m.group(1)
        dl = f"https://github.com/{REPO}/releases/download/{tag}/"
        ver = tag.lstrip("vV")
        return {"tag_name": tag, "html_url": f"https://github.com/{REPO}/releases/tag/{tag}", "body": "",
                "assets": [{"name": EXE_ASSET, "browser_download_url": dl + EXE_ASSET},
                           {"name": f"HvoyaLauncher-Setup-{ver}.exe",
                            "browser_download_url": dl + f"HvoyaLauncher-Setup-{ver}.exe"}]}


def check():
    rel = _latest_release()
    latest = (rel.get("tag_name") or "").lstrip("vV")
    assets = rel.get("assets") or []
    exe = next((a for a in assets if a["name"] == EXE_ASSET), None)
    setup = next((a for a in assets if a["name"].startswith("HvoyaLauncher-Setup") and a["name"].endswith(".exe")), None)
    return {
        "current": APP_VERSION, "latest": latest, "available": _ver(latest) > _ver(APP_VERSION),
        "notes": rel.get("body") or "", "url": rel.get("html_url") or f"https://github.com/{REPO}/releases",
        "canAuto": frozen() and bool(exe or setup), "_exe": exe, "_setup": setup,
    }


def public(info):
    return {k: v for k, v in info.items() if not k.startswith("_")}


def _download(asset, path, task):
    total = int(asset.get("size") or 0)
    digest = (asset.get("digest") or "")
    h = hashlib.sha256()
    tmp = path + ".part"
    done = 0
    with http().get(asset["browser_download_url"], stream=True, timeout=(15, 60)) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if total:
                    task.counter(done // 65536, max(1, total // 65536))
    if total and done != total:
        raise IOError("Файл обновления скачался не полностью")
    if digest.startswith("sha256:") and h.hexdigest() != digest.split(":", 1)[1]:
        os.remove(tmp)
        raise IOError("Контрольная сумма обновления не совпала")
    os.replace(tmp, path)


def _clean_env():
    """Новый onefile-exe не должен подхватить окружение распаковки текущего процесса."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _spawn(args, cwd):
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, cwd=cwd, env=_clean_env(), creationflags=flags, close_fds=True)


def apply(task, guard=None):
    """Скачивает и ставит обновление. Возвращает True — лаунчер должен закрыться.
    guard() вызывается после загрузки, прямо перед заменой файлов: если игра запустилась
    за время скачивания, бросает исключение и обновление откладывается."""
    if not frozen():
        raise RuntimeError("Обновление работает только в собранном exe")
    info = check()
    if not info["available"]:
        raise RuntimeError("Уже установлена последняя версия")
    exe_path = os.path.abspath(sys.executable)
    folder = os.path.dirname(exe_path)

    if info["_exe"] and _writable(folder):
        task.set_status(f"Загрузка версии {info['latest']}")
        new = exe_path + ".new"
        _download(info["_exe"], new, task)
        if guard:
            guard()
        old = exe_path + ".old"
        if os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                old = exe_path + f".old{os.getpid()}"
        os.replace(exe_path, old)
        try:
            os.replace(new, exe_path)
        except OSError:
            os.replace(old, exe_path)  # откат
            raise
        task.set_status("Перезапуск")
        _spawn([exe_path, "--after-update"], folder)
        return True

    if info["_setup"]:
        task.set_status(f"Загрузка установщика {info['latest']}")
        os.makedirs(CACHE, exist_ok=True)
        setup = os.path.join(CACHE, info["_setup"]["name"])
        _download(info["_setup"], setup, task)
        if guard:
            guard()
        task.set_status("Запуск установщика")
        _spawn([setup, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"], CACHE)
        return True
    raise RuntimeError("В релизе нет файла для обновления — скачайте вручную со страницы релиза")


def cleanup_old():
    """Удаляет HvoyaLauncher.exe.old после обновления."""
    if not frozen():
        return
    exe_path = os.path.abspath(sys.executable)
    folder = os.path.dirname(exe_path)
    base = os.path.basename(exe_path)
    for name in os.listdir(folder):
        if name.startswith(base + ".old") or name == base + ".new":
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass

"""Ярлык сборки на рабочем столе и передача запроса «запустить сборку» уже открытому лаунчеру."""
import base64
import json
import os
import re
import struct
import subprocess
import sys
import time

from . import instances
from .util import DATA, read_json, slugify, write_json

REQUEST = os.path.join(DATA, "launch_request.json")


def _ico(png):
    """ICO с одним встроенным PNG (Windows Vista+)."""
    w, h = struct.unpack(">II", png[16:24])
    return struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(png), 22) + png


def create(inst_id, png_b64=""):
    inst = instances.get(inst_id)
    os.makedirs(os.path.join(DATA, "shortcuts"), exist_ok=True)
    icon = ""
    if png_b64:
        raw = base64.b64decode(png_b64.split(",", 1)[-1])
        icon = os.path.join(DATA, "shortcuts", f"{inst_id}.ico")
        with open(icon, "wb") as f:
            f.write(_ico(raw))
    if getattr(sys, "frozen", False):
        target, args = sys.executable, f"--launch {inst_id}"
        workdir = os.path.dirname(sys.executable)
    else:
        main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        py = sys.executable.replace("python.exe", "pythonw.exe")
        target, args, workdir = py, f'"{main}" --launch {inst_id}', os.path.dirname(main)
    name = re.sub(r'[\/:*?"<>|]', "_", inst["name"]).strip() or inst_id
    ps = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$d=[Environment]::GetFolderPath('Desktop');"
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '{name.replace(chr(39), chr(39) * 2)} - Hvoya.lnk'));"
        f"$s.TargetPath='{target}';$s.Arguments='{args}';$s.WorkingDirectory='{workdir}';"
        + (f"$s.IconLocation='{icon},0';" if icon else "")
        + f"$s.Description='Запустить «{inst['name']}» в Hvoya Launcher';$s.Save();Write-Output (Join-Path $d '{name.replace(chr(39), chr(39) * 2)} - Hvoya.lnk')"
    )
    import base64 as _b64
    enc = _b64.b64encode(ps.encode("utf-16-le")).decode()    # кириллица без искажений кодировки
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "Не удалось создать ярлык").strip()[:300])
    return r.stdout.strip()


def request_launch(inst_id):
    write_json(REQUEST, {"id": inst_id, "t": time.time()})


def take_request():
    """Забирает запрос от второй копии (свежее 30 секунд) и удаляет файл."""
    if not os.path.isfile(REQUEST):
        return None
    d = read_json(REQUEST, {}) or {}
    try:
        os.remove(REQUEST)
    except OSError:
        pass
    if d.get("id") and time.time() - d.get("t", 0) < 30:
        return d["id"]
    return None

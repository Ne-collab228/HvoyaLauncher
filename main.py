"""Hvoya Launcher — лёгкий лаунчер Minecraft (офлайн / Ely.by, Modrinth / CurseForge)."""
import ctypes
import os
import socket
import sys
import time

import webview

from launcher import events, updater
from launcher.api import Api
from launcher.util import APP_NAME, DATA, resource


def _single_instance():
    """Не даём запустить вторую копию — вместо этого показываем уже открытое окно."""
    if sys.platform != "win32":
        return True
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.CreateMutexW.restype = ctypes.c_void_p
    # после обновления старая копия ещё закрывается — ждём её до 20 секунд
    tries = 80 if "--after-update" in sys.argv else 1
    for i in range(tries):
        handle = k32.CreateMutexW(None, False, "HvoyaLauncher_SingleInstance")
        if k32.GetLastError() != 183:  # не ERROR_ALREADY_EXISTS
            return True
        if i < tries - 1:
            k32.CloseHandle(ctypes.c_void_p(handle))
            time.sleep(0.25)
    hwnd = u32.FindWindowW(None, APP_NAME)
    if hwnd:
        u32.ShowWindow(hwnd, 9)  # SW_RESTORE
        u32.SetForegroundWindow(hwnd)
    return False
    return True


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    if not _single_instance():
        return
    if getattr(sys, "frozen", False):  # --windowed: логи в файл
        log = open(os.path.join(DATA, "launcher.log"), "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stderr = log
    updater.cleanup_old()
    api = Api(just_updated="--after-update" in sys.argv)
    window = webview.create_window(
        APP_NAME, resource("ui", "index.html"), js_api=api, width=1180, height=740,
        min_size=(900, 580), background_color="#16181a", text_select=False)
    api._attach(window)
    events.set_window(window)
    webview.start(debug="--debug" in sys.argv, private_mode=False, http_port=_free_port(),
                  storage_path=os.path.join(DATA, "webview"))


if __name__ == "__main__":
    main()

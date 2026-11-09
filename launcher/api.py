"""Мост JS ↔ Python (pywebview js_api)."""
import base64
import functools
import os
import subprocess
import traceback

import webview

from . import (accounts, config, content, crash, discord, events, export, game, importer, instances, shots, sources,
               storage, updater, worlds)
from .util import APP_VERSION, DATA, INSTANCES, total_ram_mb


def api(fn):
    @functools.wraps(fn)
    def wrapper(self, *args):
        try:
            return {"ok": True, "data": fn(self, *args)}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": str(e) or e.__class__.__name__,
                    "twofactor": isinstance(e, accounts.TwoFactorRequired)}
    return wrapper


def _open(path):
    os.makedirs(path, exist_ok=True)
    os.startfile(path)  # noqa: S606


class Api:
    def __init__(self, just_updated=False):
        self._window = None
        self._just_updated = just_updated

    def _attach(self, window):
        self._window = window

    # ----------------------------------------------------------- general
    @api
    def init(self):
        return {"version": APP_VERSION, "settings": config.load(), "accounts": accounts.list_accounts(),
                "instances": instances.list_all(), "running": game.running_ids(), "ram": total_ram_mb(),
                "dataDir": DATA, "justUpdated": self._just_updated, "frozen": updater.frozen()}

    @api
    def get_settings(self):
        return config.load()

    @api
    def save_settings(self, values):
        res = config.save(values)
        discord.refresh()
        return res

    @api
    def open_folder(self, what, inst_id=None, sub=""):
        if what == "launcher":
            _open(DATA)
        elif what == "instances":
            _open(INSTANCES)
        elif what == "backups":
            _open(worlds.backup_dir(inst_id))
        elif what == "instance":
            _open(os.path.join(instances.game_dir(inst_id), sub) if sub else instances.game_dir(inst_id))
        return True

    @api
    def open_url(self, url):
        if url.startswith(("https://", "http://")):
            os.startfile(url)  # noqa: S606
        return True

    @api
    def pick_java(self):
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Java (java.exe;javaw.exe)", "All files (*.*)"))
        return res[0] if res else None

    @api
    def test_java(self, path):
        out = subprocess.run([path or "java", "-version"], capture_output=True, text=True, timeout=15)
        return (out.stderr or out.stdout).strip().splitlines()[0]

    # ----------------------------------------------------------- accounts
    @api
    def accounts(self):
        return accounts.list_accounts()

    @api
    def add_offline(self, name):
        return accounts.add_offline(name)

    @api
    def add_elyby(self, login, password, totp=""):
        return accounts.add_elyby(login, password, totp)

    @api
    def remove_account(self, acc_id):
        return accounts.remove(acc_id)

    @api
    def select_account(self, acc_id):
        return accounts.select(acc_id)

    # ----------------------------------------------------------- instances
    @api
    def instances(self):
        return instances.list_all()

    @api
    def mc_versions(self):
        return game.mc_versions()

    @api
    def loader_versions(self, loader, mc):
        return game.loader_versions(loader, mc)

    @api
    def create_instance(self, data):
        inst = instances.create(data.get("name"), data["mc"], data.get("loader", "vanilla"),
                                data.get("loaderVersion", ""), data.get("group", ""), data.get("icon", "grass"))
        return inst

    @api
    def update_instance(self, inst_id, values):
        return instances.update(inst_id, values)

    @api
    def delete_instance(self, inst_id):
        if game.is_running(inst_id):
            raise RuntimeError("Сначала закройте игру")
        instances.delete(inst_id)
        return True

    @api
    def copy_instance(self, inst_id, name):
        return instances.copy(inst_id, name)

    @api
    def pick_icon(self, inst_id):
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Images (*.png;*.jpg;*.jpeg)",))
        if not res:
            return None
        import shutil
        shutil.copyfile(res[0], os.path.join(instances.inst_dir(inst_id), "icon.png"))
        return instances.update(inst_id, {"icon": "custom"})

    @api
    def reset_icon(self, inst_id, icon):
        p = os.path.join(instances.inst_dir(inst_id), "icon.png")
        if os.path.exists(p):
            os.remove(p)
        return instances.update(inst_id, {"icon": icon})

    @api
    def instance_icon(self, inst_id):
        p = os.path.join(instances.inst_dir(inst_id), "icon.png")
        if not os.path.isfile(p):
            return None
        with open(p, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()

    @api
    def launch(self, inst_id):
        inst = instances.get(inst_id)

        def started():
            mode = config.load().get("afterLaunch")
            if mode == "minimize":
                self._window.minimize()

        return events.run_task(f"Запуск «{inst['name']}»", lambda t: game.launch(inst_id, t, started), inst_id)

    @api
    def repair(self, inst_id):
        inst = instances.get(inst_id)
        return events.run_task(f"Проверка файлов «{inst['name']}»",
                               lambda t: game.ensure_installed(inst, t, force=True) and None, inst_id)

    @api
    def kill(self, inst_id):
        game.kill(inst_id)
        return True

    @api
    def get_log(self, inst_id):
        return game.get_log(inst_id)

    @api
    def running(self):
        return game.running_ids()

    # ----------------------------------------------------------- content
    @api
    def list_content(self, inst_id, kind):
        return content.list_content(inst_id, kind)

    @api
    def toggle_content(self, inst_id, kind, name, enabled):
        return content.toggle(inst_id, kind, name, enabled)

    @api
    def delete_content(self, inst_id, kind, names):
        return content.delete(inst_id, kind, names)

    @api
    def add_content_files(self, inst_id, kind):
        types = {"mods": ("Моды (*.jar)",), "resourcepacks": ("Ресурспаки (*.zip)",),
                 "shaderpacks": ("Шейдеры (*.zip)",)}[kind]
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=types)
        if not res:
            return None
        return content.add_files(inst_id, kind, list(res))

    @api
    def installed_projects(self, inst_id):
        return content.installed_projects(inst_id)

    @api
    def search(self, source, query, ptype, mc, loader, offset, sort):
        return sources.search(source, query, ptype, mc, loader, offset, sort)

    @api
    def versions(self, source, project_id, ptype, mc, loader):
        return sources.versions(source, project_id, ptype, mc, loader)

    @api
    def project(self, source, project_id):
        return sources.project(source, project_id)

    @api
    def install_content(self, source, ptype, inst_id, project_id, version_id, title):
        return events.run_task(f"Установка {title}",
                               lambda t: content.install_project(source, ptype, inst_id, project_id, version_id, t),
                               inst_id)

    @api
    def install_modpack(self, source, project_id, version_id, name):
        return events.run_task(f"Модпак «{name}»",
                               lambda t: content.install_modpack(source, project_id, version_id, name, t))

    @api
    def import_pack(self):
        res = self._window.create_file_dialog(webview.FileDialog.OPEN,
                                              file_types=("Модпаки (*.mrpack;*.zip)", "All files (*.*)"))
        if not res:
            return None
        path = res[0]
        name = os.path.splitext(os.path.basename(path))[0]
        return events.run_task(f"Импорт «{name}»", lambda t: content.install_pack_file(path, None, t))

    @api
    def check_updates(self, inst_id):
        return content.check_updates(inst_id)

    @api
    def apply_updates(self, inst_id, updates):
        return events.run_task("Обновление модов", lambda t: content.apply_updates(inst_id, updates, t), inst_id)

    # ----------------------------------------------------------- storage
    @api
    def storage_scan(self):
        return storage.scan()

    @api
    def storage_clean(self, what, arg=None):
        if game.running_ids() and what in ("unused", "runtime", "version"):
            raise RuntimeError("Закройте игру перед очисткой")
        return storage.clean(what, arg)

    # ----------------------------------------------------------- import from other launchers
    @api
    def import_scan(self):
        return importer.scan_known()

    @api
    def import_pick_folder(self):
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not res:
            return None
        return importer.detect_folder(res[0] if isinstance(res, (list, tuple)) else res)

    @api
    def import_instance(self, data):
        return events.run_task(f"Импорт «{data.get('name')}»", lambda t: importer.import_instance(data, t))

    # ----------------------------------------------------------- self-update
    @api
    def check_update(self):
        return updater.public(updater.check())

    @api
    def apply_update(self):
        if game.running_ids():
            raise RuntimeError("Закройте игру перед обновлением лаунчера")

        def work(task):
            if updater.apply(task):
                import threading
                threading.Timer(1.0, self._window.destroy).start()
            return {"restarting": True}
        return events.run_task("Обновление лаунчера", work)

    # ----------------------------------------------------------- worlds
    def _dialog_path(self, res):
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    @api
    def worlds(self, inst_id):
        return {"worlds": worlds.list_worlds(inst_id), "backups": worlds.list_backups(inst_id)}

    @api
    def world_delete(self, inst_id, folder):
        if game.is_running(inst_id):
            raise RuntimeError("Сначала закройте игру")
        return worlds.delete_world(inst_id, folder)

    @api
    def world_copy(self, inst_id, folder, target_id):
        if target_id == inst_id:
            raise ValueError("Выберите другую сборку")
        return worlds.copy_world(inst_id, folder, target_id)

    @api
    def world_backup(self, inst_id, folder=None):
        if folder:
            return events.run_task(f"Бэкап мира «{folder}»", lambda t: {"file": worlds.backup_world(inst_id, folder, t)}, inst_id)
        return events.run_task("Бэкап всех миров", lambda t: {"files": worlds.backup_all(inst_id, t)}, inst_id)

    @api
    def backup_restore(self, inst_id, name):
        return events.run_task("Восстановление мира", lambda t: {"world": worlds.restore_backup(inst_id, name, t)}, inst_id)

    @api
    def backup_delete(self, inst_id, name):
        return worlds.delete_backup(inst_id, name)

    @api
    def world_import(self, inst_id):
        path = self._dialog_path(self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Архив с миром (*.zip)", "All files (*.*)")))
        if not path:
            return None
        return events.run_task("Импорт мира", lambda t: {"world": worlds.restore_zip(inst_id, path, t)}, inst_id)

    # ----------------------------------------------------------- crash analysis
    @api
    def analyze_crash(self, inst_id):
        return crash.analyze(inst_id)

    @api
    def last_crash(self, inst_id):
        return crash.load_last(inst_id)

    @api
    def crash_report(self, inst_id, name):
        return crash.crash_report_text(inst_id, name)

    # ----------------------------------------------------------- export
    @api
    def export_entries(self, inst_id):
        return export.entries(inst_id)

    @api
    def export_instance(self, inst_id, opts):
        inst = instances.get(inst_id)
        ext = "zip" if opts.get("format") == "zip" else "mrpack"
        base = "".join(c for c in (opts.get("name") or inst["name"]) if c not in r'\/:*?"<>|').strip() or "modpack"
        ver = "".join(c for c in (opts.get("version") or "") if c not in r'\/:*?"<>|').strip()
        fname = f"{base}{('-' + ver) if ver else ''}.{ext}"
        types = ("Архив сборки (*.zip)",) if ext == "zip" else ("Модпак Modrinth (*.mrpack)",)
        dest = self._dialog_path(self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=fname,
                                                                 file_types=types))
        if not dest:
            return None
        if not dest.lower().endswith("." + ext):
            dest += "." + ext
        return events.run_task(f"Экспорт «{inst['name']}»", lambda t: export.export(inst_id, dest, opts, t))

    @api
    def reveal_file(self, path):
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])  # noqa: S603,S607
        return True

    # ----------------------------------------------------------- screenshots
    @api
    def screenshots(self, inst_id):
        return shots.list_shots(inst_id)

    @api
    def screenshots_delete(self, inst_id, names):
        return shots.delete(inst_id, names)

    @api
    def screenshot_reveal(self, inst_id, name):
        shots.reveal(inst_id, name)
        return True

    @api
    def screenshot_copy(self, inst_id, name):
        return shots.copy_to_clipboard(inst_id, name)

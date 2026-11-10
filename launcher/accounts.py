"""Аккаунты: офлайн и Ely.by (Yggdrasil + authlib-injector)."""
import hashlib
import os
import re
import threading
import time
import uuid

import requests

from .util import DATA, download, get_json, http, read_json, write_json

PATH = os.path.join(DATA, "accounts.json")
ELY_AUTH = "https://authserver.ely.by/auth"
AUTHLIB_PATH = os.path.join(DATA, "authlib-injector.jar")
_lock = threading.Lock()


class AuthError(Exception):
    pass


class TwoFactorRequired(AuthError):
    pass


def _load():
    data = read_json(PATH, None) or {}
    data.setdefault("accounts", [])
    data.setdefault("selected", None)
    if not data.get("clientToken"):
        data["clientToken"] = uuid.uuid4().hex
    return data


def _save(data):
    write_json(PATH, data)


def offline_uuid(name):
    """Тот же UUID, что выдаёт сервер в offline-mode (UUID.nameUUIDFromBytes)."""
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(h)).hex


def public(acc):
    if acc["type"] == "elyby":
        skin = f"https://skinsystem.ely.by/skins/{acc['name']}.png"
    else:
        from . import skins
        data = skins.offline_skin(acc["name"])
        skin = skins._data_url(data) if data else None  # noqa: SLF001
    return {"id": acc["id"], "type": acc["type"], "name": acc["name"], "uuid": acc["uuid"], "skin": skin}


def list_accounts():
    with _lock:
        data = _load()
        return {"selected": data["selected"], "accounts": [public(a) for a in data["accounts"]]}


def _add(acc):
    with _lock:
        data = _load()
        data["accounts"] = [a for a in data["accounts"]
                            if not (a["type"] == acc["type"] and a["uuid"] == acc["uuid"])]
        data["accounts"].append(acc)
        data["selected"] = acc["id"]
        _save(data)
    return list_accounts()


def add_offline(name):
    name = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
        raise AuthError("Ник: 3–16 символов, латиница, цифры и _")
    acc = {"id": "off-" + name.lower(), "type": "offline", "name": name, "uuid": offline_uuid(name)}
    return _add(acc)


def _ely_post(endpoint, payload):
    # Ely.by на рваной сети часто не отвечает с первого раза — повторяем с коротким таймаутом
    for attempt in range(4):
        try:
            r = http().post(f"{ELY_AUTH}/{endpoint}", json=payload, timeout=(5, 10))
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 3:
                raise AuthError("Ely.by не отвечает — проверьте интернет и попробуйте ещё раз") from None
            time.sleep(1)
    if r.status_code == 200:
        return r.json() if r.content else {}
    try:
        err = r.json()
    except ValueError:
        err = {}
    msg = err.get("errorMessage") or f"HTTP {r.status_code}"
    if "two factor" in msg.lower():
        raise TwoFactorRequired("Нужен код двухфакторной аутентификации")
    if "invalid credentials" in msg.lower():
        msg = "Неверный логин или пароль"
    raise AuthError(f"Ely.by: {msg}")


def add_elyby(login, password, totp=""):
    with _lock:
        client_token = _load()["clientToken"]
    pw = password + (":" + totp.strip() if totp and totp.strip() else "")
    res = _ely_post("authenticate", {
        "username": login.strip(), "password": pw, "clientToken": client_token, "requestUser": True,
    })
    prof = res.get("selectedProfile") or {}
    if not prof:
        raise AuthError("У аккаунта Ely.by нет игрового профиля")
    acc = {"id": "ely-" + prof["id"], "type": "elyby", "name": prof["name"], "uuid": prof["id"],
           "accessToken": res["accessToken"]}
    return _add(acc)


def remove(acc_id):
    with _lock:
        data = _load()
        acc = next((a for a in data["accounts"] if a["id"] == acc_id), None)
        data["accounts"] = [a for a in data["accounts"] if a["id"] != acc_id]
        if data["selected"] == acc_id:
            data["selected"] = data["accounts"][0]["id"] if data["accounts"] else None
        _save(data)
    if acc and acc["type"] == "elyby":
        try:
            _ely_post("invalidate", {"accessToken": acc["accessToken"], "clientToken": data["clientToken"]})
        except Exception:  # noqa: BLE001
            pass
    return list_accounts()


def select(acc_id):
    with _lock:
        data = _load()
        if any(a["id"] == acc_id for a in data["accounts"]):
            data["selected"] = acc_id
            _save(data)
    return list_accounts()


def prepare_launch():
    """Возвращает данные выбранного аккаунта для запуска (обновляя токен Ely.by)."""
    with _lock:
        data = _load()
        acc = next((a for a in data["accounts"] if a["id"] == data["selected"]), None)
        client_token = data["clientToken"]
    if acc is None:
        raise AuthError("Сначала добавьте аккаунт")
    if acc["type"] == "offline":
        return {"type": "offline", "name": acc["name"], "uuid": acc["uuid"], "token": "0"}

    try:
        _ely_post("validate", {"accessToken": acc["accessToken"]})
    except TwoFactorRequired:
        raise
    except AuthError:
        try:
            res = _ely_post("refresh", {"accessToken": acc["accessToken"], "clientToken": client_token,
                                        "requestUser": True})
        except AuthError as e:
            raise AuthError("Сессия Ely.by истекла — войдите в аккаунт заново") from e
        acc["accessToken"] = res["accessToken"]
        if res.get("selectedProfile"):
            acc["name"] = res["selectedProfile"]["name"]
        with _lock:
            d = _load()
            d["accounts"] = [acc if a["id"] == acc["id"] else a for a in d["accounts"]]
            _save(d)
    return {"type": "elyby", "name": acc["name"], "uuid": acc["uuid"], "token": acc["accessToken"]}


def ensure_authlib(task=None):
    if os.path.isfile(AUTHLIB_PATH) and os.path.getsize(AUTHLIB_PATH) > 10000:
        return AUTHLIB_PATH
    if task:
        task.set_status("Загрузка authlib-injector")
    urls = []
    try:
        meta = get_json("https://authlib-injector.yushi.moe/artifact/latest.json", timeout=15)
        urls.append(meta["download_url"])
    except Exception:  # noqa: BLE001
        pass
    try:
        rel = get_json("https://api.github.com/repos/yushijinhun/authlib-injector/releases/latest", timeout=15)
        urls += [a["browser_download_url"] for a in rel.get("assets", []) if a["name"].endswith(".jar")]
    except Exception:  # noqa: BLE001
        pass
    if not urls:
        raise AuthError("Не удалось скачать authlib-injector (нужен для Ely.by)")
    download(urls, AUTHLIB_PATH)
    return AUTHLIB_PATH

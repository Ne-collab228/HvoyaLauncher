"""Зеркала для адресов, которые без VPN бывают недоступны (Mojang, Forge/NeoForge, Fabric, Modrinth, CurseForge).

Подмена работает на уровне requests.Session.request (см. util.py), поэтому покрывает и
собственные запросы лаунчера, и minecraft-launcher-lib. Режимы (настройка `mirror`):
auto — сначала оригинал, при сбое зеркало (и несколько минут идём сразу на зеркало);
always — сначала зеркало; off — только оригинал.
Чистый модуль без импорта util (util импортирует его).
"""
import threading
import time
from urllib.parse import urlsplit

BMCL = "https://bmclapi2.bangbang93.com"
MCIM = "https://mod.mcimirror.top"
CREEPER = "https://maven.creeperhost.net"

# хост → (префикс пути, который срезаем, база зеркала)
_HOSTS = {
    "launchermeta.mojang.com": ("", BMCL),
    "piston-meta.mojang.com": ("", BMCL),
    "launcher.mojang.com": ("", BMCL),
    "piston-data.mojang.com": ("", BMCL),
    "resources.download.minecraft.net": ("", BMCL + "/assets"),
    "libraries.minecraft.net": ("", BMCL + "/maven"),
    "maven.minecraftforge.net": ("", BMCL + "/maven"),
    # BMCLAPI отдаёт библиотеки NeoForge редиректом на mirrors.cernet.edu.cn — из РФ почти не отвечает
    "maven.neoforged.net": ("/releases", CREEPER),
    "meta.fabricmc.net": ("", BMCL + "/fabric-meta"),
    "meta.quiltmc.org": ("", BMCL + "/quilt-meta"),
    "api.modrinth.com": ("", MCIM + "/modrinth"),
    "cdn.modrinth.com": ("", MCIM),
    "api.curse.tools": ("/v1/cf", MCIM + "/curseforge/v1"),
    "api.curseforge.com": ("/v1", MCIM + "/curseforge/v1"),
    "edge.forgecdn.net": ("", MCIM),
    "mediafilez.forgecdn.net": ("", MCIM),
}

DOWN_FOR = 600          # сколько секунд после сбоя оригинала сразу идём на зеркало
_down = {}
_lock = threading.Lock()


def host_of(url):
    return urlsplit(url).netloc.lower().split(":")[0]


def alternative(url):
    """Адрес на зеркале или None, если для этого адреса зеркала нет."""
    u = urlsplit(url)
    rule = _HOSTS.get(u.netloc.lower().split(":")[0])
    if not rule or u.scheme not in ("http", "https"):
        return None
    strip, base = rule
    path = u.path
    if strip:
        if not path.startswith(strip + "/"):
            return None
        path = path[len(strip):]
    return base + path + ("?" + u.query if u.query else "")


def is_down(host):
    with _lock:
        t = _down.get(host)
        return t is not None and time.time() - t < DOWN_FOR


def mark_down(host):
    with _lock:
        _down[host] = time.time()


def mark_up(host):
    with _lock:
        _down.pop(host, None)

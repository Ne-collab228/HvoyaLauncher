"""Список серверов сборки (servers.dat) и пинг по протоколу Server List Ping."""
import io
import json
import os
import re
import shutil
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

from . import instances


# ---------------------------------------------------------------- NBT без потерь (чтение/запись)
def _rd(f, tag):
    if tag == 1:
        return struct.unpack(">b", f.read(1))[0]
    if tag == 2:
        return struct.unpack(">h", f.read(2))[0]
    if tag == 3:
        return struct.unpack(">i", f.read(4))[0]
    if tag == 4:
        return struct.unpack(">q", f.read(8))[0]
    if tag == 5:
        return struct.unpack(">f", f.read(4))[0]
    if tag == 6:
        return struct.unpack(">d", f.read(8))[0]
    if tag == 7:
        return f.read(struct.unpack(">i", f.read(4))[0])
    if tag == 8:
        return f.read(struct.unpack(">H", f.read(2))[0]).decode("utf-8", "replace")
    if tag == 9:
        sub, n = struct.unpack(">bi", f.read(5))
        return (sub, [_rd(f, sub) for _ in range(max(n, 0))])
    if tag == 10:
        out = {}
        while True:
            t = f.read(1)
            if not t or t == b"\x00":
                return out
            name = f.read(struct.unpack(">H", f.read(2))[0]).decode("utf-8", "replace")
            out[name] = (t[0], _rd(f, t[0]))
    if tag == 11:
        n = struct.unpack(">i", f.read(4))[0]
        return list(struct.unpack(f">{n}i", f.read(4 * n)))
    if tag == 12:
        n = struct.unpack(">i", f.read(4))[0]
        return list(struct.unpack(f">{n}q", f.read(8 * n)))
    raise ValueError(f"NBT tag {tag}")


def _wr(tag, v):
    if tag == 1:
        return struct.pack(">b", v)
    if tag == 2:
        return struct.pack(">h", v)
    if tag == 3:
        return struct.pack(">i", v)
    if tag == 4:
        return struct.pack(">q", v)
    if tag == 5:
        return struct.pack(">f", v)
    if tag == 6:
        return struct.pack(">d", v)
    if tag == 7:
        return struct.pack(">i", len(v)) + v
    if tag == 8:
        b = v.encode("utf-8")
        return struct.pack(">H", len(b)) + b
    if tag == 9:
        sub, items = v
        return struct.pack(">bi", sub, len(items)) + b"".join(_wr(sub, x) for x in items)
    if tag == 10:
        out = b""
        for k, (t, x) in v.items():
            kb = k.encode("utf-8")
            out += bytes([t]) + struct.pack(">H", len(kb)) + kb + _wr(t, x)
        return out + b"\x00"
    if tag == 11:
        return struct.pack(">i", len(v)) + struct.pack(f">{len(v)}i", *v)
    if tag == 12:
        return struct.pack(">i", len(v)) + struct.pack(f">{len(v)}q", *v)
    raise ValueError(tag)


def _path(inst_id):
    return os.path.join(instances.game_dir(inst_id), "servers.dat")


def _load(inst_id):
    p = _path(inst_id)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "rb") as fh:
            f = io.BytesIO(fh.read())
        f.read(1)
        f.read(struct.unpack(">H", f.read(2))[0])
        root = _rd(f, 10)
        return list(root.get("servers", (9, (10, [])))[1][1])
    except Exception:  # noqa: BLE001
        return []


def _save(inst_id, items):
    p = _path(inst_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.isfile(p):
        try:
            shutil.copy2(p, p + ".bak")
        except OSError:
            pass
    root = {"servers": (9, (10, items))}
    data = b"\x0a\x00\x00" + _wr(10, root)
    tmp = p + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, p)


def _s(c, k, d=""):
    v = c.get(k)
    return v[1] if v else d


def list_servers(inst_id):
    return [{"name": _s(c, "name", "Minecraft Server"), "ip": _s(c, "ip"),
             "icon": ("data:image/png;base64," + _s(c, "icon")) if _s(c, "icon") else ""}
            for c in _load(inst_id)]


def add(inst_id, name, ip):
    ip = (ip or "").strip()
    if not ip:
        raise ValueError("Укажите адрес сервера")
    items = _load(inst_id)
    items.append({"name": (8, (name or "").strip() or ip), "ip": (8, ip)})
    _save(inst_id, items)
    return list_servers(inst_id)


def edit(inst_id, index, name, ip):
    items = _load(inst_id)
    ip = (ip or "").strip()
    if not ip:
        raise ValueError("Укажите адрес сервера")
    items[index]["name"] = (8, (name or "").strip() or ip)
    items[index]["ip"] = (8, ip)
    _save(inst_id, items)
    return list_servers(inst_id)


def remove(inst_id, index):
    items = _load(inst_id)
    del items[index]
    _save(inst_id, items)
    return list_servers(inst_id)


def move(inst_id, index, delta):
    items = _load(inst_id)
    j = index + delta
    if 0 <= j < len(items):
        items[index], items[j] = items[j], items[index]
        _save(inst_id, items)
    return list_servers(inst_id)


# ---------------------------------------------------------------- пинг
def _srv(host):
    """SRV-запись _minecraft._tcp.<host> простым DNS-запросом; None, если её нет."""
    q = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for part in ("_minecraft", "_tcp") + tuple(host.split(".")):
        q += bytes([len(part)]) + part.encode()
    q += b"\x00\x00\x21\x00\x01"
    for dns in ("77.88.8.8", "1.1.1.1", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.5)
            s.sendto(q, (dns, 53))
            d = s.recv(2048)
            s.close()
        except OSError:
            continue
        if struct.unpack(">H", d[6:8])[0] < 1:
            return None
        i = 12
        while d[i]:
            i += d[i] + 1
        i += 5
        if d[i] & 0xC0 == 0xC0:
            i += 2
        else:
            while d[i]:
                i += d[i] + 1
            i += 1
        if d[i:i + 2] != b"\x00\x21":
            return None
        i += 10
        port = struct.unpack(">H", d[i + 4:i + 6])[0]
        j, labels = i + 6, []
        while d[j]:
            if d[j] & 0xC0 == 0xC0:
                j = ((d[j] & 0x3F) << 8) | d[j + 1]
                continue
            labels.append(d[j + 1:j + 1 + d[j]].decode())
            j += d[j] + 1
        return ".".join(labels), port
    return None


def _varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _read_varint(sock):
    r = 0
    for i in range(5):
        b = sock.recv(1)
        if not b:
            raise OSError("соединение закрыто")
        r |= (b[0] & 0x7F) << (7 * i)
        if not b[0] & 0x80:
            return r
    raise OSError("bad varint")


def _recv(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            raise OSError("соединение закрыто")
        buf += c
    return buf


def _text(d):
    if isinstance(d, str):
        return d
    if isinstance(d, list):
        return "".join(_text(x) for x in d)
    if isinstance(d, dict):
        return d.get("text", "") + _text(d.get("extra", []))
    return ""


def ping(ip, timeout=4):
    host, _, port = ip.strip().partition(":")
    port = int(port) if port.isdigit() else None
    if port is None:
        srv = None
        try:
            srv = _srv(host)
        except Exception:  # noqa: BLE001
            pass
        if srv:
            host, port = srv
        port = port or 25565
    try:
        sock = socket.create_connection((host, port), timeout)
        sock.settimeout(timeout)
        hb = host.encode()
        hs = b"\x00" + _varint(765) + _varint(len(hb)) + hb + struct.pack(">H", port) + b"\x01"
        sock.sendall(_varint(len(hs)) + hs + b"\x01\x00")
        _read_varint(sock)
        _read_varint(sock)
        n = _read_varint(sock)
        info = json.loads(_recv(sock, n).decode("utf-8", "replace"))
        ms = None
        try:
            t = time.time()
            sock.sendall(b"\x09\x01" + struct.pack(">q", 1))
            _read_varint(sock)
            _recv(sock, 9)
            ms = int((time.time() - t) * 1000)
        except Exception:  # noqa: BLE001
            pass
        sock.close()
        pl = info.get("players") or {}
        motd = re.sub("§.", "", _text(info.get("description", "")))
        fav = info.get("favicon") or ""
        return {"ok": True, "online": pl.get("online", 0), "max": pl.get("max", 0),
                "version": (info.get("version") or {}).get("name", ""), "motd": motd.strip(),
                "ping": ms, "favicon": fav if fav.startswith("data:image") else ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e) or e.__class__.__name__}


def ping_all(inst_id):
    ips = [s["ip"] for s in list_servers(inst_id)]
    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(ping, ips))

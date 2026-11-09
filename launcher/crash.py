"""Разбор вылета игры: по журналу, краш-репорту и модам ищем понятную причину."""
import glob
import os
import re
import time
import zipfile

from . import instances

# Версия class-файла → нужная Java
_CLASS_JAVA = {52: 8, 53: 9, 54: 10, 55: 11, 56: 12, 57: 13, 58: 14, 59: 15, 60: 16, 61: 17, 62: 18,
               63: 19, 64: 20, 65: 21, 66: 22, 67: 23, 68: 24, 69: 25}


def _p(level, title, text, action=None, **extra):
    return {"level": level, "title": title, "text": text, "action": action, **extra}


def _read(path, limit=4_000_000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def _sources(inst_id):
    """Текст журнала текущего/последнего запуска + свежий краш-репорт + hs_err (падение самой JVM)."""
    from . import game
    gd = instances.game_dir(inst_id)
    lines = game.get_log(inst_id)
    started = game.started_at(inst_id)
    log = "\n".join(lines)
    if not lines:
        log = _read(os.path.join(gd, "logs", "latest.log"))
        try:
            started = os.path.getmtime(os.path.join(gd, "logs", "latest.log")) - 6 * 3600
        except OSError:
            started = 0
    since = (started or 0) - 5
    crash_file, crash = None, ""
    reports = sorted(glob.glob(os.path.join(gd, "crash-reports", "*.txt")), key=os.path.getmtime, reverse=True)
    if reports and os.path.getmtime(reports[0]) >= since:
        crash_file, crash = reports[0], _read(reports[0])
    hs = sorted(glob.glob(os.path.join(gd, "hs_err_pid*.log")), key=os.path.getmtime, reverse=True)
    hs_err = _read(hs[0], 200_000) if hs and os.path.getmtime(hs[0]) >= since else ""
    return log, crash, crash_file, hs_err


def _mod_loader_kind(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (OSError, zipfile.BadZipFile):
        return "broken"
    kinds = set()
    if "fabric.mod.json" in names:
        kinds.add("fabric")
    if "quilt.mod.json" in names:
        kinds.add("quilt")
    if "META-INF/mods.toml" in names:
        kinds.add("forge")
    if "META-INF/neoforge.mods.toml" in names:
        kinds.add("neoforge")
    if "mcmod.info" in names:
        kinds.add("forge")
    # универсальные jar грузятся в (Neo)Forge через сервисы ModLauncher, без mods.toml
    for n in names:
        if n.startswith("META-INF/services/"):
            if "minecraftforge" in n or "cpw.mods" in n:
                kinds.add("forge")
            if "neoforged" in n:
                kinds.add("neoforge")
    return kinds


_COMPAT = {"fabric": {"fabric"}, "quilt": {"quilt", "fabric"}, "forge": {"forge"},
           "neoforge": {"neoforge", "forge"}}
_LNAMES = {"fabric": "Fabric", "quilt": "Quilt", "forge": "Forge", "neoforge": "NeoForge"}


def _check_mods(inst):
    """Статическая проверка папки mods: битые jar и моды под другой загрузчик."""
    out = []
    folder = os.path.join(instances.game_dir(inst["id"]), "mods")
    if not os.path.isdir(folder):
        return out
    jars = [n for n in os.listdir(folder) if n.endswith(".jar")]
    loader = inst.get("loader", "vanilla")
    if loader == "vanilla" and jars:
        out.append(_p("warn", "Моды в сборке без загрузчика",
                      f"В папке mods {len(jars)} модов, но у сборки нет загрузчика (Vanilla) — они не загрузятся. "
                      "Выберите Fabric/Forge/NeoForge/Quilt на вкладке «Версия».", "version"))
        return out
    if any("connector" in n.lower() for n in jars):  # Sinytra Connector грузит Fabric-моды на (Neo)Forge
        allowed = _COMPAT.get(loader, set()) | {"fabric"}
    else:
        allowed = _COMPAT.get(loader, set())
    broken, wrong = [], []
    for n in jars:
        kinds = _mod_loader_kind(os.path.join(folder, n))
        if kinds == "broken":
            broken.append(n)
        elif kinds and not (kinds & allowed):
            wrong.append((n, "/".join(_LNAMES[k] for k in sorted(kinds))))
    if broken:
        out.append(_p("error", "Повреждённые файлы модов",
                      "Эти файлы не открываются как архив (недокачаны или битые) — удалите и скачайте заново.",
                      "mods", mods=broken))
    if wrong:
        out.append(_p("error", f"Моды для другого загрузчика (сборка на {_LNAMES.get(loader, loader)})",
                      "Эти моды сделаны под другой загрузчик и не будут работать здесь — отключите их "
                      "или поставьте версию под ваш загрузчик.",
                      "mods", mods=[f"{n} — {k}" for n, k in wrong]))
    return out


def _uniq(seq):
    seen, out = set(), []
    for s in seq:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def analyze(inst_id, code=None):
    inst = instances.get(inst_id)
    log, crash, crash_file, hs_err = _sources(inst_id)
    text = log + "\n" + crash
    probs = []

    # --- Fabric/Quilt: несовместимый набор модов
    if "Mod resolution encountered an incompatible mod set" in text or "Incompatible mods found!" in text \
            or "Unmet dependency listing" in text:
        sol = re.search(r"A potential solution has been determined(?:, this may resolve your problem)?:\s*\n((?:\s*-\s.*\n?)+)", text)
        unmet = re.search(r"(?:Unmet dependency listing|More details):\s*\n((?:\s*-\s.*\n?)+)", text)
        items = []
        if sol:
            items += [re.sub(r"^\s*-\s*", "", l) for l in sol.group(1).splitlines()]
        if unmet:
            items += [re.sub(r"^\s*-\s*", "", l) for l in unmet.group(1).splitlines()]
        items = _uniq(_translate_fabric(i) for i in items)
        probs.append(_p("error", "Не хватает модов или версии несовместимы",
                        "Загрузчик не смог собрать набор модов. Что нужно сделать:", "mods", mods=items[:20]))

    # --- Forge/NeoForge: отсутствующие зависимости
    m = re.search(r"Missing or unsupported mandatory dependencies:\s*\n((?:\s*Mod ID: .*\n?)+)", text)
    if m:
        items = []
        for l in m.group(1).splitlines():
            mm = re.search(r"Mod ID: '([^']+)', Requested by: '([^']+)', Expected range: '([^']*)', Actual version: '([^']*)'", l)
            if mm:
                dep, by, rng, act = mm.groups()
                items.append(f"{by} требует «{dep}» {rng}" + (" — не установлен" if act == "[MISSING]" else f", а стоит {act}"))
        probs.append(_p("error", "Не хватает модов-зависимостей",
                        "Установите недостающие моды (или нужные версии):", "mods", mods=_uniq(items)))
    for mm in re.finditer(r"Mod (\S+) requires (\S+) (\S+)\s*\n?\s*Currently, \S+ is not installed", text):
        probs.append(_p("error", "Не хватает мода", f"{mm.group(1)} требует {mm.group(2)} {mm.group(3)}", "mods"))

    # --- дубликаты
    dup = re.search(r"(?:Found duplicate mods?|Duplicate mods? found|DuplicateModsFoundException)[^\n]*\n?((?:.*\n){0,8})", text, re.I)
    if dup:
        files = _uniq(re.findall(r"([\w.+\-\[\] ]+\.jar)", dup.group(0)))
        probs.append(_p("error", "Один мод установлен дважды",
                        "Удалите лишние копии (обычно разные версии одного мода):", "mods", mods=files[:12]))

    # --- Java
    m = re.search(r"class file version (\d+)\.\d+\)?, this version of the Java Runtime only recognizes class file versions up to (\d+)", text)
    if m:
        need, have = _CLASS_JAVA.get(int(m.group(1)), "новее"), _CLASS_JAVA.get(int(m.group(2)), "?")
        probs.append(_p("error", f"Нужна Java {need}",
                        f"Игра или мод требует Java {need}, а запущена Java {have}. Очистите поле «Java» в настройках "
                        "сборки — лаунчер сам скачает подходящую — или укажите путь к Java " + str(need) + ".", "settings"))
    elif "UnsupportedClassVersionError" in text:
        probs.append(_p("error", "Неподходящая версия Java",
                        "Игре нужна другая версия Java. Очистите поле «Java» в настройках сборки.", "settings"))
    if re.search(r"Could not reserve enough space for .*object heap|Invalid maximum heap size|Could not create the Java Virtual Machine", text + hs_err):
        probs.append(_p("error", "Java не смогла выделить память",
                        "Уменьшите максимум памяти в настройках, проверьте аргументы JVM. На 32-битной Java больше ~1.5 ГБ не выделить.",
                        "settings"))

    # --- память
    if "java.lang.OutOfMemoryError" in text or "There is insufficient memory for the Java Runtime" in hs_err:
        ram = inst.get("ramMax") or "по умолчанию"
        probs.append(_p("error", "Не хватило памяти",
                        f"Игре не хватило выделенной памяти (сейчас: {ram} МБ). Увеличьте её в настройках сборки — "
                        "для модпаков обычно нужно 6–8 ГБ.", "ram"))

    # --- Mixin
    mixin_mods = _uniq(re.findall(r"Mixin apply(?:ing)? for mod (\S+) failed", text) +
                       re.findall(r"from mod (\S+)\] failed", text) +
                       re.findall(r"MixinApplyError.*?from mod ([\w\-]+)", text))
    if mixin_mods:
        probs.append(_p("error", "Мод несовместим с версией игры или другим модом",
                        "Сбой Mixin в модах ниже — обновите их, найдите версию под ваш Minecraft или временно отключите:",
                        "mods", mods=mixin_mods[:10]))

    # --- видеокарта / OpenGL
    if re.search(r"Pixel format not accelerated|GLFW error 65542|WGL: The driver does not appear to support OpenGL|"
                 r"Couldn't set pixel format|OpenGL 3\.2 .*not supported|No OpenGL context", text):
        probs.append(_p("error", "Проблема с драйвером видеокарты",
                        "Игра не смогла создать окно OpenGL. Обновите драйвер видеокарты с сайта NVIDIA/AMD/Intel; "
                        "на ноутбуке запускайте игру на дискретной видеокарте."))
    elif hs_err and re.search(r"atio6axx|nvoglv|ig\d+icd|amdxx|OpenGL|lwjgl", hs_err, re.I):
        probs.append(_p("error", "Сбой драйвера видеокарты",
                        "Java упала внутри графического драйвера. Обновите драйвер видеокарты; если стоят шейдеры "
                        "или Sodium/Iris — попробуйте отключить их."))
    elif hs_err:
        probs.append(_p("warn", "Аварийное завершение Java",
                        "Java завершилась с ошибкой (hs_err). Частые причины: драйвер видеокарты, разгон, "
                        "антивирус или битые файлы. Попробуйте «Проверить файлы» и обновить драйверы.", "repair"))

    # --- битые файлы игры
    if re.search(r"Could not find or load main class|ClassNotFoundException: net\.minecraft|"
                 r"java\.util\.zip\.ZipException|zip END header not found|error in opening zip file|"
                 r"Failed to download .* (?:library|asset)", text):
        zm = re.search(r"(?:ZipException|zip END header|error in opening zip).*", text)
        bad_jar = re.search(r"([\w.\-+]+\.jar)", zm.group(0)) if zm else None
        probs.append(_p("error", "Повреждены файлы игры",
                        "Часть файлов игры или библиотек повреждена" + (f" ({bad_jar.group(1)})" if bad_jar else "") +
                        ". Нажмите «Проверить файлы» — лаунчер скачает их заново.", "repair"))

    # --- статическая проверка модов (если загрузчик ничего внятного не написал)
    if not any(p["action"] == "mods" for p in probs):
        probs += _check_mods(inst)
    else:
        probs += [p for p in _check_mods(inst) if p["title"].startswith("Повреждённые")]

    # --- краш-репорт: описание и подозреваемые моды
    desc = cause = None
    suspects = []
    if crash:
        dm = re.search(r"^Description: (.+)$", crash, re.M)
        desc = dm.group(1).strip() if dm else None
        em = re.search(r"^Description: .+\n\n(.+)$", crash, re.M)
        cause = em.group(1).strip() if em else None
        sm = re.search(r"Suspected Mods?: (.+)", crash)
        if sm and "NONE" not in sm.group(1).upper():
            suspects = _uniq(sm.group(1).split(","))
            sm2 = re.findall(r"^\s+(.+?) \(([\w\-]+)\), Version: ", crash[crash.find("Suspected Mod"):], re.M)
            if sm2:
                suspects = _uniq(f"{n} ({i})" for n, i in sm2)
    if suspects and not any(p.get("mods") for p in probs if p["level"] == "error"):
        probs.append(_p("error", "Подозреваемые моды",
                        "По краш-репорту вылет связан с этими модами — обновите или отключите их:", "mods", mods=suspects[:8]))

    if not cause:
        ex = re.findall(r"^(?:Caused by: |Exception in thread \"[^\"]+\" )?((?:[a-z][\w$]*\.)+[A-Z][\w$]*(?:Exception|Error)(?:: .*)?)$",
                        text, re.M)
        cause = ex[-1].strip() if ex else None

    if not probs:
        if code in (None, 0) and not crash:
            probs.append(_p("info", "Ошибок не найдено", "В журнале нет признаков вылета."))
        else:
            probs.append(_p("warn", "Точную причину определить не удалось",
                            "Посмотрите краш-репорт и строку ошибки ниже. Попробуйте отключить недавно добавленные моды "
                            "или «Проверить файлы».", "repair"))

    if code is not None and code in (-1073740791, 3221226505) and not any("видеокарт" in p["title"] for p in probs):
        probs.append(_p("warn", f"Код выхода {code}", "Такой код часто бывает при сбое драйвера видеокарты или оверлея (Discord, MSI Afterburner, RTSS)."))

    return {"problems": probs, "description": desc, "cause": (cause or "")[:600],
            "crashReport": os.path.basename(crash_file) if crash_file else None,
            "hsErr": bool(hs_err), "time": int(time.time())}


_FABRIC_RU = [
    (r"^Install (\S+), (?:any version|version (.+))\.?$", lambda m: f"Установить {m.group(1)}" + (f" версии {m.group(2)}" if m.group(2) else "")),
    (r"^Replace mod '(.+?)' \((\S+)\) (\S+) with (?:any version|version (.+?))(?: that is compatible with:? ?(.*?))?[.:]?$",
     lambda m: f"Заменить «{m.group(1)}» {m.group(3)} на " + (f"версию, совместимую с {m.group(5)}" if m.group(5) else "совместимую версию")),
    (r"^Remove mod '(.+?)' \((\S+)\).*$", lambda m: f"Удалить мод «{m.group(1)}»"),
    (r"^Mod '(.+?)' \((\S+)\) (\S+) requires (?:any version of|version (.+?) of) (.+?), which is missing!?$",
     lambda m: f"«{m.group(1)}» требует {m.group(5)}" + (f" {m.group(4)}" if m.group(4) else "") + " — не установлен"),
    (r"^Mod '(.+?)' \((\S+)\) (\S+) requires (?:any version of|version (.+?) of) (.+?), but only the wrong version is present: (.+?)!?$",
     lambda m: f"«{m.group(1)}» требует {m.group(5)} {m.group(4) or ''}, а стоит {m.group(6)}".replace("  ", " ")),
    (r"^Mod '(.+?)' \((\S+)\) (\S+) is incompatible with (?:any version of|version (.+?) of) (.+?), but .*$",
     lambda m: f"«{m.group(1)}» несовместим с {m.group(5)}"),
]


def _translate_fabric(line):
    line = line.strip()
    for pat, fn in _FABRIC_RU:
        m = re.match(pat, line)
        if m:
            return fn(m)
    return line


def crash_report_text(inst_id, name):
    from .util import safe_join
    return _read(safe_join(os.path.join(instances.game_dir(inst_id), "crash-reports"), name), 400_000)


def save_last(inst_id, result):
    from .util import write_json
    write_json(os.path.join(instances.inst_dir(inst_id), "last_crash.json"), result)


def load_last(inst_id):
    from .util import read_json
    return read_json(os.path.join(instances.inst_dir(inst_id), "last_crash.json"))


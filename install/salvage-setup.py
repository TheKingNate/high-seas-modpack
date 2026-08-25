#!/usr/bin/env python3
"""
Salvage Setup -- installs or updates the Salvage modpack.

    python3 salvage-setup.py

Shows every step up front, explains what each one does before it
runs, and reports what happened after.
"""

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
except ImportError:
    print(
        "\nThis needs Python's tkinter, which isn't installed.\n\n"
        "  Ubuntu/Debian:  sudo apt install -y python3-tk\n"
        "  Fedora:         sudo dnf install -y python3-tkinter\n"
        "  Arch:           sudo pacman -S tk\n\n"
        "Then run this again.\n"
    )
    sys.exit(1)

REPO = "TheKingNate/high-seas-modpack"
PACK_URL = f"https://raw.githubusercontent.com/{REPO}/release/pack.toml"
OLD_URL = f"https://raw.githubusercontent.com/{REPO}/main/pack.toml"
BOOTSTRAP = ("https://github.com/packwiz/packwiz-installer-bootstrap"
             "/releases/latest/download/packwiz-installer-bootstrap.jar")

INSTANCE = "Salvage"
MC_VERSION = "1.20.1"
FABRIC = "0.19.3"

QUARANTINE = ".salvage-quarantine"

BG = "#1b1e24"
CARD = "#242832"
FG = "#eceff4"
DIM = "#8b93a1"
ACCENT = "#5aa2ff"
GOOD = "#5fd18c"
BAD = "#ff7070"

MAC = platform.system() == "Darwin"
MONO = "Menlo" if MAC else "monospace"
UI = "Helvetica Neue" if MAC else "DejaVu Sans"


class Stop(Exception):
    def __init__(self, what, todo=""):
        self.what, self.todo = what, todo
        super().__init__(what)


def prism_candidates():
    h = Path.home()
    if MAC:
        c = [h / "Library/Application Support/PrismLauncher"]
    else:
        c = [h / ".var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher",
             h / ".local/share/PrismLauncher"]
    c.append(h / "Desktop/PrismLauncher")
    return c


def prism_roots():
    """Every Prism data folder present, not just the first one found.

    The Flatpak and the distro package can both be installed, and the
    pack may live under either. Looking only at the first hit is how a
    real install gets reported as "nothing here".
    """
    return [d for d in prism_candidates() if (d / "instances").is_dir()]


def find_prism():
    roots = prism_roots()
    for d in roots:
        if pack_instances(d, OLD_URL) or pack_instances(d, PACK_URL):
            return d
    return roots[0] if roots else None


def total_ram_mb():
    try:
        if MAC:
            return int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"])) // (1024 * 1024)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 8192


def heap_mb():
    return max(4096, min(12288, total_ram_mb() // 2))


def pack_instances(data, url):
    out = []
    if not data:
        return out
    root = data / "instances"
    if not root.is_dir():
        return out
    for cfg in root.glob("*/instance.cfg"):
        try:
            if url in cfg.read_text(errors="ignore"):
                out.append(cfg)
        except Exception:
            pass
    return out


def trash_self():
    me = Path(__file__).resolve()
    try:
        if MAC:
            shutil.move(str(me), str(Path.home() / ".Trash" / me.name))
        elif shutil.which("gio"):
            subprocess.run(["gio", "trash", str(me)],
                           check=True, capture_output=True)
        else:
            t = Path.home() / ".local/share/Trash/files"
            t.mkdir(parents=True, exist_ok=True)
            shutil.move(str(me), str(t / me.name))
        return True
    except Exception:
        return False


# -- repair: reading an instance -------------------------------------

def salvage_instances():
    """Instance folders belonging to this pack, across every Prism root.

    packwiz.json is the stronger signal of the two: an instance the
    player renamed, or one still pointing at the old channel, keeps it.
    """
    out = []
    for root in prism_roots():
        try:
            entries = sorted((root / "instances").iterdir())
        except Exception:
            continue
        for inst in entries:
            if not inst.is_dir():
                continue
            if (inst / "minecraft" / "packwiz.json").is_file():
                out.append(inst)
                continue
            try:
                text = (inst / "instance.cfg").read_text(errors="ignore")
            except Exception:
                continue
            if OLD_URL in text or PACK_URL in text:
                out.append(inst)
    return out


def cfg_value(text, key):
    for line in text.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def channel_of(cfg_text):
    if OLD_URL in cfg_text:
        return "main"
    if PACK_URL in cfg_text:
        return "release"
    return "unknown"


def hash_file(path, algo):
    """Hex digest, or None if we cannot compute that algorithm.

    packwiz mixes sha512, sha1 and sha256 in one file. Anything we do
    not recognise has to read as "not checked" -- calling it corrupt
    would quarantine perfectly good jars.
    """
    try:
        h = hashlib.new(algo)
    except ValueError:
        return None
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def hash_bytes(data, algo):
    try:
        h = hashlib.new(algo)
    except ValueError:
        return None
    h.update(data)
    return h.hexdigest()


def digest_matches(path, spec):
    """True / False / None, where None means we could not check."""
    algo = (spec.get("type") or "").lower()
    want = (spec.get("value") or "").lower()
    if not algo or not want:
        return None
    got = hash_file(path, algo)
    if got is None:
        return None
    return got.lower() == want


def fetch(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def pack_meta(text):
    """name, version and the index filename out of a pack.toml."""
    meta = {"name": "", "version": "", "index": "index.toml"}
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"')
            if section == "" and k in ("name", "version"):
                meta[k] = v
            elif section == "index" and k == "file":
                meta["index"] = v
    return meta


def java_of(cfg_text):
    """(version string, major number). Major 0 means unknown."""
    ver = cfg_value(cfg_text, "JavaVersion")
    if not ver:
        exe = cfg_value(cfg_text, "JavaPath") or "java"
        try:
            r = subprocess.run([exe, "-version"], capture_output=True,
                               text=True, timeout=15)
            m = re.search(r'version "([^"]+)"', r.stderr + r.stdout)
            ver = m.group(1) if m else ""
        except Exception:
            ver = ""
    m = re.match(r"(\d+)(?:\.(\d+))?", ver or "")
    major = 0
    if m:
        major = int(m.group(1))
        if major == 1 and m.group(2):      # 1.8.0_402 style
            major = int(m.group(2))
    return ver, major


EXC_LINE = re.compile(r"^[\w.$]+(?:Exception|Error|Throwable)\b")


def last_crash(mc):
    d = mc / "crash-reports"
    if not d.is_dir():
        return None
    files = [p for p in d.iterdir() if p.is_file()]
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        lines = newest.read_text(errors="ignore").splitlines()
    except Exception:
        return None
    exc, frames = "", []
    for i, raw in enumerate(lines):
        if EXC_LINE.match(raw.strip()):
            exc = raw.strip()
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if s.startswith("at "):
                    frames.append(s)
                    if len(frames) == 3:
                        break
                elif frames:
                    break
            break
    return {
        "file": newest.name,
        "when": time.strftime("%Y-%m-%d %H:%M",
                              time.localtime(newest.stat().st_mtime)),
        "exception": exc,
        "frames": frames,
    }


def diagnose(inst, log, progress):
    """Rung 0. Reads an instance and writes nothing at all."""
    mc = inst / "minecraft"
    try:
        cfg_text = (inst / "instance.cfg").read_text(errors="ignore")
    except Exception:
        cfg_text = ""

    r = {
        "inst": inst,
        "mc": mc,
        "label": cfg_value(cfg_text, "name") or inst.name,
        "channel": channel_of(cfg_text),
        "pack": "", "version": "",
        "tracked": 0, "jars": 0,
        "orphans": [], "corrupt": [], "missing": [], "unchecked": [],
        "warnings": [],
        "tracking": "not checked",
        "crash": last_crash(mc),
    }

    ver, major = java_of(cfg_text)
    r["java"] = ver or "unknown"
    if major and major < 17:
        r["warnings"].append(
            "java %s is too old, the pack needs 17 or newer" % ver)
    elif not major:
        r["warnings"].append(
            "could not tell which java this instance will use")

    try:
        alloc = int(cfg_value(cfg_text, "MaxMemAlloc") or 0)
    except ValueError:
        alloc = 0
    r["ram_alloc"] = alloc
    r["ram_total"] = total_ram_mb()
    if alloc and alloc < 4096:
        r["warnings"].append(
            "only %d MB of memory allocated, the pack wants 4096 or more"
            % alloc)
    if alloc and alloc > r["ram_total"] - 1024:
        r["warnings"].append(
            "%d MB allocated of %d MB physical, which leaves nothing for "
            "the rest of the system" % (alloc, r["ram_total"]))

    jar = mc / "packwiz-installer-bootstrap.jar"
    if not jar.is_file():
        r["bootstrap"] = "missing"
        r["warnings"].append(
            "the updater jar is missing, so this instance cannot update")
    elif jar.stat().st_size <= 10000:
        r["bootstrap"] = "damaged, %d bytes" % jar.stat().st_size
        r["warnings"].append("the updater jar is too small to be real")
    else:
        r["bootstrap"] = "present, %d KB" % (jar.stat().st_size // 1024)

    if r["channel"] == "main":
        r["warnings"].append(
            "on the main channel, players should be on release")
    elif r["channel"] == "unknown":
        r["warnings"].append(
            "no packwiz pre-launch command, so this instance never "
            "updates itself")

    pj = mc / "packwiz.json"
    data = {}
    if not pj.is_file():
        r["warnings"].append(
            "no packwiz.json, so there is no record of what this "
            "instance should contain")
    else:
        try:
            data = json.loads(pj.read_text(errors="ignore"))
        except Exception as e:
            r["warnings"].append("packwiz.json is unreadable: %s" % e)

    entries = data.get("cachedFiles") or {}
    # onlyOtherSide entries are server-side mods the client correctly
    # never downloaded. They have no cachedLocation and are not missing.
    checkable = [(k, v) for k, v in entries.items()
                 if not v.get("onlyOtherSide") and v.get("cachedLocation")]
    checkable.sort(key=lambda kv: kv[0])
    r["tracked"] = len(checkable)
    skipped = len(entries) - len(checkable)
    if skipped:
        log("  %d server-side entries skipped, as expected" % skipped)

    known = set()
    total = len(checkable)
    for n, (_key, e) in enumerate(checkable, 1):
        loc = e["cachedLocation"]
        known.add(loc)
        progress(n, total, loc)
        p = mc / loc
        if not p.is_file():
            r["missing"].append(loc)
            continue
        # A jar entry carries linkedFileHash for the jar itself; hash
        # describes the .pw.toml, which is not on disk.
        spec = e.get("linkedFileHash") or e.get("hash") or {}
        ok = digest_matches(p, spec)
        if ok is None:
            r["unchecked"].append(loc)
        elif not ok:
            r["corrupt"].append(loc)

    mods = mc / "mods"
    if mods.is_dir():
        jars = sorted(p for p in mods.rglob("*.jar") if p.is_file())
        r["jars"] = len(jars)
        # No usable record means no way to tell a stray jar from a real
        # one, and calling all of them orphans would quarantine the whole
        # mods folder. Say so instead; option 2 is the fix for that.
        if not entries:
            r["warnings"].append(
                "cannot tell which mods belong to the pack without a "
                "readable packwiz.json, so stray files were not looked "
                "for")
        else:
            for p in jars:
                rel = p.relative_to(mc).as_posix()
                if rel not in known:
                    r["orphans"].append(rel)

    if data:
        url = OLD_URL if r["channel"] == "main" else PACK_URL
        log("  comparing the tracking file with the live pack")
        try:
            raw = fetch(url)
        except Exception as e:
            r["tracking"] = "could not check, no connection to GitHub"
            log("  %s" % e)
        else:
            meta = pack_meta(raw.decode("utf-8", "replace"))
            r["pack"], r["version"] = meta["name"], meta["version"]
            drift = []
            want = data.get("packFileHash") or {}
            got = hash_bytes(raw, (want.get("type") or "sha256").lower())
            if got and got.lower() != (want.get("value") or "").lower():
                drift.append("pack.toml")
            iurl = url.rsplit("/", 1)[0] + "/" + meta["index"]
            try:
                iraw = fetch(iurl)
            except Exception:
                iraw = None
            if iraw is not None:
                want = data.get("indexFileHash") or {}
                got = hash_bytes(iraw,
                                 (want.get("type") or "sha256").lower())
                if got and got.lower() != (want.get("value") or "").lower():
                    drift.append("index.toml")
            if drift:
                r["tracking"] = ("out of date, %s changed since this "
                                 "instance last synced" % " and ".join(drift))
                # Without this check an unsynced instance looks perfect:
                # its packwiz.json still lists everything it once had.
                r["warnings"].append(
                    "this instance has not synced with the current pack, "
                    "so its own file list is out of date")
            else:
                r["tracking"] = "up to date"

    r["problems"] = len(r["orphans"]) + len(r["corrupt"]) + len(r["missing"])
    return r


# -- repair: changing an instance ------------------------------------

def quarantine(mc, rels, stamp, log):
    """Move files into .salvage-quarantine/<stamp>/, keeping their paths.

    Nothing is ever deleted. A stale packwiz.json would otherwise make
    this eat mods the player added on purpose, with no way back.
    """
    moved = []
    for rel in rels:
        src = mc / rel
        if not src.exists():
            continue
        dest = mc / QUARANTINE / stamp / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
        except Exception as e:
            log("  could not move %s: %s" % (rel, e))
            continue
        moved.append(rel)
        log("  moved %s" % rel)
    return moved


def reset_targets(mc):
    """Everything rung 3 clears out of mods/ and config/.

    config/*.txt is left in place: those are the keybind and settings
    files mods write, and losing them is precisely the cost of the
    clean reinstall this tool exists to avoid.
    """
    rels = []
    mods = mc / "mods"
    if mods.is_dir():
        rels += [p.relative_to(mc).as_posix()
                 for p in sorted(mods.rglob("*")) if p.is_file()]
    cfg = mc / "config"
    if cfg.is_dir():
        rels += [p.relative_to(mc).as_posix()
                 for p in sorted(cfg.rglob("*"))
                 if p.is_file() and p.suffix.lower() != ".txt"]
    return rels


# -- repair: the report ----------------------------------------------

def report_dir():
    d = Path.home() / "Desktop"
    return d if d.is_dir() else Path.home()


RULE_MAJOR = "=" * 62
RULE_MINOR = "-" * 62

# Every problem class gets exactly one word, and all three installers use the
# same one. See "Fixed vocabulary" in install/REPAIR-SPEC.md - these drifted
# once already and two reports of the same fault read as two different faults.
W_ORPHAN = "orphan"
W_HASH = "failed hash"
W_MISSING = "missing"
W_UNCHECKED = "not checked"


def os_label():
    """platform.system() says "Darwin", which nobody calls it."""
    sysname = platform.system()
    return {"Darwin": "macOS", "Windows": "Windows"}.get(sysname, sysname)


def _field(label, value):
    return "  %-13s %s" % (label, value)


def _problems(r):
    """Problem lines for one instance, in report order. Vocabulary is fixed."""
    out = []
    for w in r["warnings"]:
        out.append("    %-12s %s" % ("setup", w))
    for f in r["orphans"]:
        out.append("    %-12s %s" % (W_ORPHAN, f))
    for f in r["corrupt"]:
        out.append("    %-12s %s" % (W_HASH, f))
    for f in r["missing"]:
        out.append("    %-12s %s" % (W_MISSING, f))
    for f in r["unchecked"]:
        out.append("    %-12s %s" % (W_UNCHECKED, f))
    return out


def write_report(results, changes, stamp, ran="diagnose only"):
    out = [RULE_MAJOR,
           "  SALVAGE  -  install report",
           RULE_MAJOR,
           "",
           _field("generated", time.strftime("%Y-%m-%d %H:%M:%S")),
           _field("ran", ran),
           _field("system", "%s %s, %d MB memory"
                  % (os_label(), platform.machine(), total_ram_mb())),
           _field("copies found", str(len(results))),
           ""]

    for r in results:
        probs = _problems(r)
        pack = ("%s %s" % (r["pack"], r["version"])).strip() or "unknown"
        out += [RULE_MINOR,
                "  %s  %s" % ("[ !! ]" if probs else "[ OK ]", r["label"]),
                RULE_MINOR,
                "",
                _field("path", r["inst"]),
                _field("pack", pack),
                _field("channel", r["channel"]),
                _field("java", r["java"]),
                _field("memory", "%d MB allocated of %d MB"
                       % (r["ram_alloc"], r["ram_total"])),
                _field("updater", r["bootstrap"]),
                _field("tracking", r["tracking"]),
                "",
                "  tracked %d  |  jars %d  |  orphans %d  |  %s %d  |  %s %d"
                % (r["tracked"], r["jars"], len(r["orphans"]),
                   W_HASH, len(r["corrupt"]),
                   W_MISSING, len(r["missing"])),
                "",
                "  problems"]
        out += probs or ["    none"]
        out += ["", "  last crash"]
        c = r["crash"]
        if c:
            out.append("    %s (%s)" % (c["file"], c["when"]))
            out.append("    %s" % (c["exception"] or "no exception line found"))
            out += ["      %s" % f for f in c["frames"]]
        else:
            out.append("    none recorded")
        out.append("")

    out += [RULE_MINOR, "  what this run changed", RULE_MINOR, ""]
    out += ["  %s" % c for c in changes]
    out += ["",
            "  Send this to your server operator. The installer can also put a",
            "  short version on your clipboard - use the Copy summary button.",
            ""]

    path = report_dir() / ("salvage-report-%s.txt" % stamp)
    path.write_text("\n".join(out))
    return path


SUMMARY_MAX = 1800
SUMMARY_LIST_CAP = 5


def _summary_list(word, items):
    """At most SUMMARY_LIST_CAP entries, then a count. Basenames only - a
    pasted summary must not carry the player's home directory into a chat."""
    out = []
    for f in items[:SUMMARY_LIST_CAP]:
        out.append("  %-12s %s" % (word, Path(f).name))
    if len(items) > SUMMARY_LIST_CAP:
        out.append("  %-12s ... and %d more"
                   % ("", len(items) - SUMMARY_LIST_CAP))
    return out


def summary_text(results, ran, report_name):
    """The abridged report, sized for a chat message. Same vocabulary as the
    file - this is the report shortened, never a second format."""
    out = ["Salvage check - %s" % time.strftime("%Y-%m-%d %H:%M"),
           "%s %s, %d MB" % (os_label(), platform.machine(),
                             total_ram_mb())]

    for r in results:
        probs = _problems(r)
        pack = ("%s %s" % (r["pack"], r["version"])).strip() or "unknown"
        out += ["",
                "[%s] %s - %s, pack %s"
                % ("!!" if probs else "OK", r["label"], r["channel"], pack),
                "  orphans %d | %s %d | %s %d | tracking %s"
                % (len(r["orphans"]), W_HASH, len(r["corrupt"]),
                   W_MISSING, len(r["missing"]), r["tracking"])]
        for w in r["warnings"]:
            out.append("  %-12s %s" % ("setup", w))
        out += _summary_list(W_ORPHAN, r["orphans"])
        out += _summary_list(W_HASH, r["corrupt"])
        out += _summary_list(W_MISSING, r["missing"])
        c = r["crash"]
        if c and c["exception"]:
            out.append("  crash        %s" % c["exception"])
            if c["frames"]:
                out.append("               %s" % c["frames"][0])

    out += ["", "ran: %s" % ran, "full report on my Desktop: %s" % report_name]

    text = "\n".join(out)
    if len(text) > SUMMARY_MAX:
        text = text[:SUMMARY_MAX - 20].rstrip() + "\n... (truncated)"
    return text


def copy_clipboard(widget, text):
    """Best effort. A repair that has already moved files must never fail on a
    cosmetic step, so every failure here is swallowed - the caller falls back
    to naming the report file."""
    try:
        widget.clipboard_clear()
        widget.clipboard_append(text)
        widget.update()      # without this the clipboard is empty after exit
        return True
    except Exception:
        return False


RUNGS = [
    ("Leave it alone for now",
     "Keep the report, change nothing."),
    ("1.  Targeted fix",
     "Quarantine mods that aren't part of the pack, and any file that "
     "fails its checksum. The updater re-downloads them next launch."),
    ("2.  Resync",
     "The targeted fix, plus the tracking file, so the updater "
     "re-checks every single file next launch."),
    ("3.  Full reset",
     "Quarantine all of mods/ and config/ and let the updater rebuild "
     "them. Your world, settings and keybinds stay where they are."),
]


BLURB = {
    "Get Prism Launcher":
        "Prism Launcher is the app that runs modded Minecraft.\n\n"
        "If you already have it, this does nothing. If not, it "
        "downloads and installs it for you.",
    "Create the Salvage instance":
        "Adds an entry in Prism called Salvage, set to Minecraft "
        "1.20.1 with the Fabric mod loader.\n\n"
        "It picks how much memory to give Minecraft based on how "
        "much your computer has.",
    "Set up automatic updates":
        "Adds a small file that checks the mod list every time you "
        "play.\n\nThat means you never have to reinstall or "
        "re-download anything when the pack changes.",
    "Look at your current setup":
        "Finds your existing Salvage instances and reports which "
        "update channel they're on.\n\nNothing is changed in this "
        "step.",
    "Switch to stable updates":
        "Points your copy at the stable release channel, so you only "
        "receive changes once they've been tested.\n\nOne line in "
        "your settings file changes, and a backup is saved first. "
        "Your world is untouched.",
    "Verify the updater":
        "Checks the auto-update file is present and undamaged, and "
        "re-downloads it if needed.",
}


class Repair(tk.Toplevel):
    """Rung 0, then the 1-2-3 ladder. Separate window, own worker."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Salvage -- check for problems")
        self.configure(bg=BG)
        self.geometry("700x720")
        self.minsize(660, 620)

        self.results = []
        self.stamp = time.strftime("%Y%m%d-%H%M%S")
        self.report = None
        self.done = False
        self.pick_inst = tk.IntVar(value=0)
        self.pick_rung = tk.IntVar(value=0)

        self._build()
        self.transient(master)
        self.lift()
        self.after(200, lambda: threading.Thread(
            target=self._work_diagnose, daemon=True).start())

    def _build(self):
        tk.Label(self, text="Check for problems", bg=BG, fg=FG,
                 font=(UI, 24, "bold")).pack(pady=(20, 0))
        tk.Label(self,
                 text="Nothing is ever deleted. Anything this moves goes "
                      "into .salvage-quarantine inside the instance, and "
                      "your world and settings are never touched.",
                 bg=BG, fg=DIM, font=(UI, 10), wraplength=560,
                 justify="center").pack(pady=(4, 14))

        card = tk.Frame(self, bg=CARD)
        card.pack(fill="x", padx=36)
        self.head = tk.Label(card, text="Looking at your install", bg=CARD,
                             fg=FG, font=(UI, 15, "bold"), anchor="w",
                             wraplength=560, justify="left")
        self.head.pack(fill="x", padx=18, pady=(14, 6))
        self.body = tk.Label(card,
                             text="This step only reads. It changes "
                                  "nothing until you pick an option.",
                             bg=CARD, fg=DIM, font=(UI, 11), anchor="w",
                             wraplength=560, justify="left")
        self.body.pack(fill="x", padx=18, pady=(0, 14))

        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100,
                                   style="Bar.Horizontal.TProgressbar")
        self.bar.pack(fill="x", padx=36, pady=(12, 0))

        self.status = tk.Label(self, text="starting", bg=BG, fg=DIM,
                               font=(UI, 10))
        self.status.pack(pady=(4, 0))

        self.choice = tk.Frame(self, bg=BG)

        self.details = tk.Label(self, text="Details", bg=BG, fg=DIM,
                                font=(UI, 9, "bold"), anchor="w")
        self.details.pack(fill="x", padx=36, pady=(14, 4))
        self.out = scrolledtext.ScrolledText(
            self, height=10, bg="#14161b", fg=DIM, relief="flat",
            font=(MONO, 9), wrap="word", padx=12, pady=8, borderwidth=0,
            highlightthickness=0)
        self.out.pack(fill="both", expand=True, padx=36, pady=(0, 12))
        self.out.configure(state="disabled")

        row = tk.Frame(self, bg=BG)
        row.pack(pady=(0, 20))
        self.btn = ttk.Button(row, text="Working...", style="Go.TButton",
                              command=self._go)
        self.btn.pack(side="left")
        self.btn.state(["disabled"])
        # Hidden until a run has produced a summary. Copying is never automatic:
        # replacing whatever the player had on their clipboard with no warning is
        # the kind of thing that makes a tool feel untrustworthy, and a silent
        # clipboard write is indistinguishable from nothing having happened.
        self.copy_btn = ttk.Button(row, text="Copy summary",
                                   style="Quiet.TButton", command=self._copy)
        ttk.Button(row, text="Close", style="Quiet.TButton",
                   command=self.destroy).pack(side="left", padx=(10, 0))

    def _copy(self):
        if not getattr(self, "summary", None):
            return
        if copy_clipboard(self, self.summary):
            self.copy_btn.config(text="Copied")
            self.after(2500, lambda: self.copy_btn.config(text="Copy summary"))
        else:
            self.copy_btn.config(text="Clipboard unavailable")

    def _offer_copy(self, text):
        """Stash the summary and reveal the button. Called on the UI thread."""
        self.summary = text
        self.copy_btn.pack(side="left", padx=(10, 0))

    # -- called from the worker thread -------------------------------
    def post(self, fn, *args):
        """Hand work back to the UI thread, quietly if the window is gone.

        The worker outlives a close, and hashing 160 jars is long enough
        for someone to shut the window halfway through.
        """
        try:
            if self.winfo_exists():
                self.after(0, fn, *args)
        except tk.TclError:
            pass

    def log(self, msg=""):
        self.post(self._log, msg)

    def _log(self, msg):
        self.out.configure(state="normal")
        self.out.insert("end", msg + "\n")
        self.out.see("end")
        self.out.configure(state="disabled")

    def progress(self, n, total, label):
        self.post(self._progress, n, total, label)

    def _progress(self, n, total, label):
        self.bar.configure(maximum=max(total, 1), value=n)
        self.status.config(text="checking %d of %d -- %s"
                                % (n, total, Path(label).name))

    def _card(self, head, body, colour=FG):
        self.head.config(text=head, fg=colour)
        self.body.config(text=body)

    # -- rung 0 ------------------------------------------------------
    def _work_diagnose(self):
        try:
            self._diagnose()
        except Exception as e:
            self.log("")
            self.log("Stopped: %s" % e)
            self.post(self._card, "Couldn't finish the check",
                      str(e) + "\n\nClose this and try again.", BAD)
            self.post(self._offer_close)

    def _diagnose(self):
        found = salvage_instances()
        if not found:
            self.log("No Salvage install found on this computer.")
            for d in prism_candidates():
                self.log("  looked in %s" % (d / "instances"))
            self.post(self._card, "Nothing to check",
                      "No Salvage instance was found, so there is "
                      "nothing to report on. If Prism is installed "
                      "somewhere unusual, say so and it can be added.",
                      BAD)
            self.post(self._offer_close)
            return

        self.log("Found %d instance(s)." % len(found))
        for inst in found:
            self.log("")
            self.log("%s" % inst.name)
            r = diagnose(inst, self.log, self.progress)
            self.results.append(r)
            self.log("  %d tracked, %d jars on disk"
                     % (r["tracked"], r["jars"]))
            self.log("  %d orphan, %d corrupt, %d missing"
                     % (len(r["orphans"]), len(r["corrupt"]),
                        len(r["missing"])))
            self.log("  tracking: %s" % r["tracking"])
            for w in r["warnings"]:
                self.log("  note: %s" % w)

        self.report = write_report(self.results,
                                   ["nothing (diagnose only)"], self.stamp,
                                   "diagnose only")
        text = summary_text(self.results, "diagnose only", self.report.name)
        self.log("")
        self.log("Report written to %s" % self.report)
        self.post(self._offer_copy, text)
        self.post(self._diagnosed)

    def _diagnosed(self):
        self.bar.configure(value=self.bar["maximum"])
        worst = max(self.results, key=lambda r: r["problems"])
        self.pick_inst.set(self.results.index(worst))
        total = sum(r["problems"] for r in self.results)

        if total:
            self._card(
                "Found %d thing(s) worth fixing" % total,
                "The report below lists them all. Pick the smallest "
                "option first -- each one does more than the last, and "
                "each is reversible.")
            self.pick_rung.set(1)
        else:
            # "problems" counts files only. Every warning - stale tracking, java
            # below 17, a missing updater jar, the wrong channel - contributed
            # nothing here, so an instance that genuinely had not synced was told
            # "No damaged or stray files" and preselected the do-nothing option.
            # That defeats the check the spec calls load-bearing: it runs, then its
            # result is discarded at the one point where it would change what the
            # player does.
            warned = [w for r in self.results for w in r["warnings"]]
            if warned:
                self._card(
                    "No damaged or stray files, but %d thing(s) need "
                    "attention" % len(warned),
                    "\n".join("- " + w for w in warned[:6]) +
                    "\n\nThe report below has the detail.")
                # Stale tracking is exactly what option 2 fixes: it drops the
                # record so the updater re-checks every file next launch.
                if any(r.get("tracking", "").startswith("out of date")
                       for r in self.results):
                    self.pick_rung.set(2)
            else:
                self._card(
                    "No damaged or stray files",
                    "Every tracked file matches its checksum. If the game "
                    "still misbehaves, send the report on: the answer may "
                    "be in the crash or the settings rather than the mods.")
        self.status.config(text=str(self.report))
        self._build_choice()
        self.btn.config(text="Do the selected thing")
        self.btn.state(["!disabled"])

    def _build_choice(self):
        # before= matters: pack() appends, and the log and buttons are
        # already in the order, so without it the options land underneath
        # them at the bottom of the window.
        self.choice.pack(fill="x", padx=36, pady=(14, 0),
                         before=self.details)

        if len(self.results) > 1:
            # Room for one row per instance, so the buttons stay visible.
            self.geometry("700x%d" % (720 + 26 * len(self.results)))
            tk.Label(self.choice, text="Which instance", bg=BG, fg=DIM,
                     font=(UI, 9, "bold"), anchor="w").pack(fill="x")
            for i, r in enumerate(self.results):
                tk.Radiobutton(
                    self.choice,
                    text="%s  --  %d problem(s)" % (r["label"],
                                                    r["problems"]),
                    variable=self.pick_inst, value=i, bg=BG, fg=FG,
                    selectcolor=CARD, activebackground=BG,
                    activeforeground=FG, highlightthickness=0, bd=0,
                    font=(UI, 11), anchor="w").pack(fill="x")
            tk.Label(self.choice, text="", bg=BG).pack()

        tk.Label(self.choice, text="What to do", bg=BG, fg=DIM,
                 font=(UI, 9, "bold"), anchor="w").pack(fill="x")
        for i, (name, note) in enumerate(RUNGS):
            tk.Radiobutton(
                self.choice, text=name, variable=self.pick_rung, value=i,
                bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                activeforeground=FG, highlightthickness=0, bd=0,
                font=(UI, 11), anchor="w").pack(fill="x")
            tk.Label(self.choice, text=note, bg=BG, fg=DIM,
                     font=(UI, 9), anchor="w", justify="left",
                     wraplength=560).pack(fill="x", padx=(26, 0),
                                          pady=(0, 4))

    # -- rungs 1-3 ---------------------------------------------------
    def _go(self):
        if self.done:
            return self.destroy()
        rung = self.pick_rung.get()
        if rung == 0:
            self._card("Report saved",
                       "Nothing was changed. Send the report on:\n\n%s"
                       % self.report, GOOD)
            self.log("")
            self.log("Nothing changed.")
            return self._offer_close()

        r = self.results[self.pick_inst.get()]
        self.choice.pack_forget()
        self.btn.state(["disabled"])
        self.btn.config(text="Working...")
        self.bar.configure(mode="indeterminate")
        self.bar.start(12)
        self._card("Repairing %s" % r["label"],
                   "Moving files into the quarantine folder. Leave this "
                   "open until it finishes.")
        threading.Thread(target=self._work_repair, args=(r, rung),
                         daemon=True).start()

    def _work_repair(self, r, rung):
        try:
            self._repair(r, rung)
        except Exception as e:
            self.log("")
            self.log("Stopped: %s" % e)
            self.post(self._card, "Couldn't finish the repair",
                      "%s\n\nNothing was deleted. Anything already "
                      "moved is in %s inside the instance."
                      % (e, QUARANTINE), BAD)
            self.post(self._offer_close)

    def _repair(self, r, rung):
        mc = r["mc"]
        self.log("")
        self.log("Repairing %s at rung %d" % (r["label"], rung))

        if rung == 3:
            targets = reset_targets(mc)
            self.log("  clearing mods/ and config/ (%d files)"
                     % len(targets))
        else:
            # Only mods/ and config/ are in scope. The pack also tracks
            # resourcepacks/*.zip and shaderpacks/*.zip, and both are on the
            # never-touch list - the closing copy promises the player their shaders
            # and keybinds were left exactly as they were.
            scoped, skipped = [], []
            for t in r["orphans"] + r["corrupt"]:
                (scoped if t.split("/")[0] in ("mods", "config") else skipped).append(t)
            for t in skipped:
                self.log("failed its check but left in place, outside mods "
                         "and config: %s" % t)
            targets = scoped

        moved = quarantine(mc, targets, self.stamp, self.log)
        if rung >= 2:
            # The updater trusts packwiz.json. Removing it is what
            # forces a full re-check of every file on the next launch.
            moved += quarantine(mc, ["packwiz.json"], self.stamp, self.log)

        changes = []
        if moved:
            changes.append("%s: moved %d file(s) to %s/%s/"
                           % (r["label"], len(moved), QUARANTINE,
                              self.stamp))
            # Option 3 moves a few hundred files. The quarantine folder
            # is the real record; the report only needs to be readable.
            changes += ["  " + f for f in moved[:40]]
            if len(moved) > 40:
                changes.append("  ... and %d more, all listed in that "
                               "folder" % (len(moved) - 40))
        else:
            changes.append("%s: nothing needed moving" % r["label"])
        changes.append("repair option %d was used" % rung)

        ran = "%s, %d file(s) quarantined" % (RUNGS[rung][0].strip(), len(moved))
        self.report = write_report(self.results, changes, self.stamp, ran)
        text = summary_text(self.results, ran, self.report.name)
        self.log("")
        self.log("Moved %d file(s)." % len(moved))
        self.log("Report updated: %s" % self.report)
        self.post(self._offer_copy, text)
        self.post(self._repaired, len(moved))

    def _repaired(self, count):
        self.bar.stop()
        self.bar.configure(mode="determinate", value=100, maximum=100)
        self._card(
            "Done -- %d file(s) quarantined" % count,
            "Launch the game now. If it still crashes, run this again "
            "and pick the next option.\n\nThe first launch after a "
            "repair re-downloads what was moved, so give it a few "
            "minutes.\n\n%s" % self._handoff(), GOOD)
        self.status.config(text=str(self.report))
        self._offer_close()

    def _handoff(self):
        """What to tell the player to send, and how to get it there."""
        return ("Send this to your server operator:\n%s\n\n"
                "Copy summary puts a short version on your clipboard "
                "instead, which is easier to paste into a chat."
                % self.report.name)

    def _offer_close(self):
        self.done = True
        self.bar.stop()
        self.btn.config(text="Close")
        self.btn.state(["!disabled"])


class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Salvage Setup")
        self.configure(bg=BG)
        self.geometry("660x700")
        self.minsize(660, 700)

        self.prism = None
        self.mode = None
        self.steps = []
        self.rows = []
        self.idx = 0
        self.busy = False
        self.halted = False
        self.starting = True
        self.found = []

        self._style()
        self._build()

        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.after(250, self._detect)

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Go.TButton", font=(UI, 14, "bold"), padding=(30, 12),
                    background=ACCENT, foreground="#ffffff", borderwidth=0)
        s.map("Go.TButton",
              background=[("active", "#4a8ce0"), ("disabled", "#3a4050")],
              foreground=[("disabled", "#7a818f")])
        s.configure("Quiet.TButton", font=(UI, 11), padding=(14, 7),
                    background=CARD, foreground=DIM, borderwidth=0)
        s.map("Quiet.TButton",
              background=[("active", "#2d323e")],
              foreground=[("active", FG), ("disabled", "#4d535f")])
        s.configure("Bar.Horizontal.TProgressbar", troughcolor=CARD,
                    background=ACCENT, borderwidth=0, thickness=4)

    def _build(self):
        tk.Label(self, text="Salvage", bg=BG, fg=FG,
                 font=(UI, 28, "bold")).pack(pady=(22, 0))
        tk.Label(self, text="Minecraft modpack setup", bg=BG, fg=DIM,
                 font=(UI, 11)).pack(pady=(2, 16))

        self.list_frame = tk.Frame(self, bg=BG)
        self.list_frame.pack(fill="x", padx=40)

        card = tk.Frame(self, bg=CARD)
        card.pack(fill="x", padx=40, pady=(18, 0))

        self.head = tk.Label(card, text="Starting up", bg=CARD, fg=FG,
                             font=(UI, 15, "bold"), anchor="w",
                             wraplength=520, justify="left")
        self.head.pack(fill="x", padx=20, pady=(16, 6))

        self.body = tk.Label(card, text="Give it a second.", bg=CARD,
                             fg=DIM, font=(UI, 11), anchor="w",
                             justify="left", wraplength=520)
        self.body.pack(fill="x", padx=20, pady=(0, 16))

        self.bar = ttk.Progressbar(self, mode="indeterminate",
                                   style="Bar.Horizontal.TProgressbar")

        self.btn = ttk.Button(self, text="Please wait...",
                              style="Go.TButton", command=self._go)
        self.btn.pack(pady=(18, 4))
        self.btn.state(["disabled"])

        # Reachable at any point, so a player can be asked to "run it
        # and send the report" without going through the setup steps.
        self.fix = ttk.Button(self, text="Check this install for problems",
                              style="Quiet.TButton", command=self.open_fix)
        self.fix.pack(pady=(4, 2))

        self.status = tk.Label(self, text="", bg=BG, fg=DIM, font=(UI, 10))
        self.status.pack()

        tk.Label(self, text="Details", bg=BG, fg=DIM, font=(UI, 9, "bold"),
                 anchor="w").pack(fill="x", padx=40, pady=(14, 4))

        self.log = scrolledtext.ScrolledText(
            self, height=8, bg="#14161b", fg=DIM, relief="flat",
            font=(MONO, 9), wrap="word", padx=12, pady=8, borderwidth=0,
            highlightthickness=0)
        self.log.pack(fill="both", expand=True, padx=40, pady=(0, 24))
        self.log.configure(state="disabled")

    # -- checklist ---------------------------------------------------
    def render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.rows = []
        for name, _ in self.steps:
            row = tk.Frame(self.list_frame, bg=BG)
            row.pack(fill="x", pady=2)
            mark = tk.Label(row, text="\u25cb", bg=BG, fg=DIM,
                            font=(UI, 13), width=2)
            mark.pack(side="left")
            txt = tk.Label(row, text=name, bg=BG, fg=DIM, font=(UI, 12),
                           anchor="w")
            txt.pack(side="left")
            self.rows.append((mark, txt))

    def mark(self, i, state):
        if i >= len(self.rows):
            return
        mark, txt = self.rows[i]
        if state == "now":
            mark.config(text="\u25b8", fg=ACCENT)
            txt.config(fg=FG, font=(UI, 12, "bold"))
        elif state == "done":
            mark.config(text="\u2713", fg=GOOD)
            txt.config(fg=GOOD, font=(UI, 12))
        elif state == "fail":
            mark.config(text="\u2715", fg=BAD)
            txt.config(fg=BAD, font=(UI, 12, "bold"))
        self.update_idletasks()

    # -- output ------------------------------------------------------
    def say(self, msg=""):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def set_status(self, text):
        self.status.config(text=text)
        self.update_idletasks()

    def card(self, head, body):
        self.head.config(text=head, fg=FG)
        self.body.config(text=body)
        self.update_idletasks()

    # -- detection ---------------------------------------------------
    def _detect(self):
        self.card("Checking your computer",
                  "Working out what you already have installed.")
        self.set_status("looking around...")

        ram = total_ram_mb()
        self.say(f"System: {platform.system()} {platform.machine()}")
        self.say(f"Memory: {ram} MB")

        self.prism = find_prism()
        if self.prism:
            self.say(f"Prism Launcher: found at {self.prism}")
        else:
            self.say("Prism Launcher: not installed")
            for c in prism_candidates():
                self.say(f"  looked in {c}")

        existing = (pack_instances(self.prism, OLD_URL)
                    + pack_instances(self.prism, PACK_URL))

        if existing:
            self.mode = "update"
            self.say(f"Existing Salvage instances: {len(existing)}")
            for c in existing:
                self.say(f"  {c.parent.name}")
            self.steps = [
                ("Look at your current setup", self._s_check),
                ("Switch to stable updates", self._s_switch),
                ("Verify the updater", self._s_boot_all),
            ]
            head = "You already have Salvage"
            body = ("Two things this can do.\n\n"
                    "Start points your copy at the stable release "
                    "channel, so you only get changes once they've been "
                    "tested.\n\n"
                    "The button below it looks for damaged, missing or "
                    "stray mod files and writes a report you can send "
                    "on.\n\n"
                    "Either way your world, settings, keybinds, shaders "
                    "and video options are left alone.")
        else:
            self.mode = "install"
            self.say("No existing Salvage instance -- fresh install")
            self.steps = [
                ("Get Prism Launcher", self._s_prism),
                ("Create the Salvage instance", self._s_instance),
                ("Set up automatic updates", self._s_boot),
            ]
            head = "Ready to install"
            body = (f"Three steps. Each one explains itself before it runs, "
                    f"and nothing happens until you click.\n\n"
                    f"Your computer has {ram} MB of memory, so Minecraft "
                    f"will get {heap_mb()} MB.")

        self.say()
        self.render_list()
        self.card(head, body)
        self.set_status("")
        self.btn.config(text="Start")
        self.btn.state(["!disabled"])

    def open_fix(self):
        if getattr(self, "_fixwin", None) and self._fixwin.winfo_exists():
            self._fixwin.lift()
            return
        self._fixwin = Repair(self)

    # -- flow --------------------------------------------------------
    def present(self):
        if self.idx >= len(self.steps):
            return self.finish()
        name, _ = self.steps[self.idx]
        self.mark(self.idx, "now")
        self.card(name, BLURB.get(name, ""))
        self.btn.config(text="Do this step")
        self.btn.state(["!disabled"])
        self.set_status(f"step {self.idx + 1} of {len(self.steps)}")

    def _go(self):
        if self.halted:
            return self.destroy()
        if self.busy:
            return
        if self.starting:
            self.starting = False
            return self.present()

        self.busy = True
        self.btn.state(["disabled"])
        self.fix.state(["disabled"])
        self.btn.config(text="Working...")
        self.bar.pack(fill="x", padx=40, pady=(8, 0), before=self.status)
        self.bar.start(12)
        self.update_idletasks()

        fn = self.steps[self.idx][1]
        threading.Thread(target=self._run, args=(fn,), daemon=True).start()

    def _run(self, fn):
        try:
            fn()
            self.after(0, self._ok)
        except Stop as e:
            what, todo = e.what, e.todo
            self.after(0, lambda: self._fail(what, todo))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self._fail(
                "Unexpected problem: " + msg,
                "Send a screenshot of this window to your server "
                "operator."))

    def _ok(self):
        self.bar.stop()
        self.bar.pack_forget()
        self.mark(self.idx, "done")
        self.fix.state(["!disabled"])
        self.busy = False
        self.idx += 1
        self.say()
        self.present()

    def _fail(self, what, todo):
        self.bar.stop()
        self.bar.pack_forget()
        self.mark(self.idx, "fail")
        self.fix.state(["!disabled"])
        self.busy = False
        self.halted = True
        self.head.config(text="Couldn't finish that step", fg=BAD)
        self.body.config(text=what + (("\n\n" + todo) if todo else ""))
        self.say()
        self.say("STOPPED: " + what)
        if todo:
            self.say(todo)
        self.say("Nothing was broken. Close this and try again.")
        self.set_status("")
        self.btn.config(text="Close")
        self.btn.state(["!disabled"])

    # -- steps -------------------------------------------------------
    def _s_prism(self):
        if self.prism:
            self.set_status("already installed")
            self.say(f"Prism already at {self.prism} -- nothing to do")
            time.sleep(0.4)
            return

        if MAC:
            if not shutil.which("brew"):
                raise Stop(
                    "Prism Launcher isn't installed, and this can't install "
                    "it for you on this Mac.",
                    "Download it from prismlauncher.org/download, open it "
                    "once so it creates its folders, then run this again.")
            self.set_status("installing via Homebrew, takes a minute...")
            self.say("Running: brew install --cask prismlauncher")
            r = subprocess.run(["brew", "install", "--cask", "prismlauncher"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.say(r.stderr.strip()[:500])
                raise Stop("Homebrew couldn't install Prism Launcher.",
                           "Install it yourself from prismlauncher.org, "
                           "then run this again.")
            self.prism = (Path.home()
                          / "Library/Application Support/PrismLauncher")
        else:
            if not shutil.which("flatpak"):
                raise Stop(
                    "Prism Launcher isn't installed, and flatpak isn't "
                    "either, so this can't install it for you.",
                    "Install Prism from prismlauncher.org/download, open it "
                    "once, then run this again.")
            self.set_status("installing via flatpak, takes a few minutes...")
            self.say("Running: flatpak install flathub "
                     "org.prismlauncher.PrismLauncher")
            r = subprocess.run(
                ["flatpak", "install", "-y", "--user", "flathub",
                 "org.prismlauncher.PrismLauncher"],
                capture_output=True, text=True)
            if r.returncode != 0:
                self.say(r.stderr.strip()[:500])
                raise Stop("The flatpak install failed.",
                           "Run this in a terminal to see why:\n"
                           "  flatpak install flathub "
                           "org.prismlauncher.PrismLauncher")
            self.prism = (Path.home()
                          / ".var/app/org.prismlauncher.PrismLauncher"
                            "/data/PrismLauncher")

        self.prism.mkdir(parents=True, exist_ok=True)
        self.say(f"Installed. Data folder: {self.prism}")
        self.set_status("installed")

    def _s_instance(self):
        inst = self.prism / "instances" / INSTANCE
        mc = inst / "minecraft"
        self.set_status("creating folders...")
        self.say(f"Instance folder: {inst}")

        try:
            mc.mkdir(parents=True, exist_ok=True)
        except Exception:
            raise Stop(f"Couldn't create a folder at {mc}",
                       "Check you have permission to write there, and that "
                       "your disk isn't full.")

        self.say(f"Minecraft {MC_VERSION} with Fabric {FABRIC}")
        (inst / "mmc-pack.json").write_text(json.dumps({
            "components": [
                {"important": True, "uid": "net.minecraft",
                 "version": MC_VERSION},
                {"uid": "net.fabricmc.fabric-loader", "version": FABRIC},
            ],
            "formatVersion": 1,
        }, indent=4))

        h = heap_mb()
        self.set_status(f"allocating {h} MB of memory")
        self.say(f"Memory: {h} MB (half of your {total_ram_mb()} MB)")

        cfg = inst / "instance.cfg"
        ours = ("InstanceType", "name", "OverrideCommands",
                "PreLaunchCommand", "OverrideMemory", "MinMemAlloc",
                "MaxMemAlloc")
        keep = []
        if cfg.exists():
            self.say("Existing settings found -- keeping anything not ours")
            keep = [l for l in cfg.read_text(errors="ignore").splitlines()
                    if l.split("=")[0] not in ours]

        keep += [
            "InstanceType=OneSix",
            f"name={INSTANCE}",
            "OverrideCommands=true",
            'PreLaunchCommand="$INST_JAVA" -jar '
            '"$INST_MC_DIR/packwiz-installer-bootstrap.jar" '
            f'-g -s client {PACK_URL}',
            "OverrideMemory=true",
            "MinMemAlloc=4096",
            f"MaxMemAlloc={h}",
        ]
        cfg.write_text("\n".join(keep) + "\n")
        self.say("Instance created.")
        self.set_status("done")

    def _s_boot(self):
        self._bootstrap(self.prism / "instances" / INSTANCE / "minecraft")

    def _s_check(self):
        self.set_status("scanning your instances...")
        self.found = (pack_instances(self.prism, OLD_URL)
                      + pack_instances(self.prism, PACK_URL))
        for c in self.found:
            src = "old" if OLD_URL in c.read_text(errors="ignore") \
                else "stable"
            self.say(f"{c.parent.name}: currently on the {src} channel")
        self.say(f"{len(self.found)} instance(s) to look at.")
        self.say("Your worlds and settings will not be modified.")
        self.set_status(f"{len(self.found)} found")
        time.sleep(0.4)

    def _s_switch(self):
        changed = 0
        for cfg in self.found:
            text = cfg.read_text(errors="ignore")
            if OLD_URL not in text:
                self.say(f"{cfg.parent.name}: already on stable, skipping")
                continue
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = cfg.parent / f"instance.cfg.backup-{stamp}"
            shutil.copy2(cfg, backup)
            self.say(f"{cfg.parent.name}: settings backed up to "
                     f"{backup.name}")
            cfg.write_text(text.replace(OLD_URL, PACK_URL))
            self.say(f"{cfg.parent.name}: now on the stable channel")
            changed += 1
        self.say(f"Changed {changed} instance(s).")
        self.set_status(f"{changed} switched")

    def _s_boot_all(self):
        for cfg in self.found:
            self._bootstrap(cfg.parent / "minecraft")

    def _bootstrap(self, mc):
        jar = mc / "packwiz-installer-bootstrap.jar"
        if jar.exists() and jar.stat().st_size > 10000:
            self.say(f"{mc.parent.name}: updater already there "
                     f"({jar.stat().st_size // 1024} KB)")
            self.set_status("already present")
            time.sleep(0.3)
            return

        mc.mkdir(parents=True, exist_ok=True)
        self.set_status("downloading the updater from GitHub...")
        self.say("Downloading packwiz-installer-bootstrap.jar")
        try:
            urllib.request.urlretrieve(BOOTSTRAP, jar)
        except Exception as e:
            self.say(f"  {e}")
            raise Stop("Couldn't download the updater from GitHub.",
                       "Check your internet connection and try again. If "
                       "GitHub is blocked on your network, that's the cause.")
        size = jar.stat().st_size
        if size < 10000:
            raise Stop(f"The updater downloaded but looks damaged "
                       f"(only {size} bytes).",
                       "Your network may be interfering with downloads. "
                       "Try a different connection.")
        self.say(f"  done, {size // 1024} KB")
        self.set_status("updater ready")

    def finish(self):
        self.head.config(text="All done", fg=GOOD)
        if self.mode == "install":
            self.body.config(text=(
                "1.  Open Prism Launcher\n"
                "2.  Sign in with your Microsoft account, top right\n"
                "3.  Click Salvage, press Launch\n\n"
                "The first launch downloads about 150 mods, so give it "
                "several minutes. After that it updates itself."))
            self.say("Next: open Prism, sign in, launch Salvage.")
            self.say()
            self.say("Then try joining the server once. It will say you "
                     "aren't whitelisted -- that's expected, and it's how "
                     "you get added. Just say you tried.")
        else:
            self.body.config(text=(
                "Nothing else to do. Just launch as normal.\n\n"
                "Your world, settings, keybinds and shaders were left "
                "exactly as they were. A backup of each settings file is "
                "saved next to the original."))
            self.say("Nothing else to do -- launch as normal.")

        self.set_status("")
        if trash_self():
            self.say()
            self.say("(this setup file has been moved to the trash)")
        self.halted = True
        self.btn.config(text="Close")
        self.btn.state(["!disabled"])


if __name__ == "__main__":
    App().mainloop()

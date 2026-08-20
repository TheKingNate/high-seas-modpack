#!/usr/bin/env python3
"""
Salvage Setup -- a small window that walks you through installing
or updating the Salvage modpack.

macOS / Linux:

    python3 salvage-setup.py

It works out whether you need a fresh install or just an update,
tells you what each step will do before it does it, and waits for
you to click.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
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
        "Then run this again. (On macOS it should already be there --\n"
        "if not, install Python from python.org.)\n"
    )
    sys.exit(1)


REPO = "TheKingNate/high-seas-modpack"
BRANCH = "release"
PACK_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/pack.toml"
OLD_URL = f"https://raw.githubusercontent.com/{REPO}/main/pack.toml"
BOOTSTRAP = ("https://github.com/packwiz/packwiz-installer-bootstrap"
             "/releases/latest/download/packwiz-installer-bootstrap.jar")

INSTANCE = "Salvage"
MC_VERSION = "1.20.1"
FABRIC = "0.19.3"

BG = "#1e2128"
FG = "#e6e6e6"
DIM = "#9aa0a8"
ACCENT = "#4a9eff"
GOOD = "#5fd18c"
BAD = "#ff6b6b"


# ---------------------------------------------------------------- util

def is_mac():
    return platform.system() == "Darwin"


def prism_dirs():
    home = Path.home()
    if is_mac():
        c = [home / "Library/Application Support/PrismLauncher"]
    else:
        c = [
            home / ".var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher",
            home / ".local/share/PrismLauncher",
        ]
    c.append(home / "Desktop/PrismLauncher")
    return c


def find_prism():
    for d in prism_dirs():
        if (d / "instances").is_dir():
            return d
    return None


def total_ram_mb():
    try:
        if is_mac():
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"])
            return int(out) // (1024 * 1024)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 8192


def heap_mb():
    h = total_ram_mb() // 2
    return max(4096, min(12288, h))


def find_pack_instances(data_dir, url):
    hits = []
    inst_root = data_dir / "instances"
    if not inst_root.is_dir():
        return hits
    for cfg in inst_root.glob("*/instance.cfg"):
        try:
            if url in cfg.read_text(errors="ignore"):
                hits.append(cfg)
        except Exception:
            pass
    return hits


def trash_self():
    me = Path(__file__).resolve()
    try:
        if is_mac():
            shutil.move(str(me), str(Path.home() / ".Trash" / me.name))
        elif shutil.which("gio"):
            subprocess.run(["gio", "trash", str(me)], check=True,
                           capture_output=True)
        else:
            t = Path.home() / ".local/share/Trash/files"
            t.mkdir(parents=True, exist_ok=True)
            shutil.move(str(me), str(t / me.name))
        return True
    except Exception:
        return False


# ----------------------------------------------------------------- app

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Salvage Setup")
        self.configure(bg=BG)
        self.geometry("620x520")
        self.resizable(False, False)

        self.prism = None
        self.mode = None          # "install" or "update"
        self.step = 0
        self.steps = []
        self.busy = False

        self._build()
        self._detect()

    # -- layout -----------------------------------------------------
    def _build(self):
        tk.Label(self, text="Salvage", bg=BG, fg=FG,
                 font=("Helvetica", 26, "bold")).pack(pady=(24, 0))
        tk.Label(self, text="Minecraft modpack setup", bg=BG, fg=DIM,
                 font=("Helvetica", 11)).pack(pady=(0, 18))

        self.step_lbl = tk.Label(self, text="", bg=BG, fg=ACCENT,
                                 font=("Helvetica", 10, "bold"))
        self.step_lbl.pack()

        self.title_lbl = tk.Label(self, text="", bg=BG, fg=FG,
                                  font=("Helvetica", 15, "bold"),
                                  wraplength=540)
        self.title_lbl.pack(pady=(6, 4))

        self.desc_lbl = tk.Label(self, text="", bg=BG, fg=DIM,
                                 font=("Helvetica", 11), wraplength=540,
                                 justify="center")
        self.desc_lbl.pack(pady=(0, 16))

        self.btn = tk.Button(self, text="", command=self._go,
                             font=("Helvetica", 13, "bold"),
                             bg=ACCENT, fg="#ffffff",
                             activebackground="#3d86db",
                             relief="flat", padx=28, pady=10,
                             highlightthickness=0, bd=0)
        self.btn.pack()

        self.log = scrolledtext.ScrolledText(
            self, height=9, bg="#15171c", fg=DIM, relief="flat",
            font=("Menlo" if is_mac() else "monospace", 9),
            wrap="word", padx=10, pady=8, borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=24, pady=(20, 24))
        self.log.configure(state="disabled")

    def say(self, msg, colour=None):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def show(self, step_text, title, desc, button):
        self.step_lbl.config(text=step_text)
        self.title_lbl.config(text=title)
        self.desc_lbl.config(text=desc)
        self.btn.config(text=button, state="normal")

    def working(self, text="Working..."):
        self.btn.config(text=text, state="disabled")
        self.update_idletasks()

    def stop(self, what, todo):
        self.step_lbl.config(text="")
        self.title_lbl.config(text="Something went wrong", fg=BAD)
        self.desc_lbl.config(text=what)
        self.say("")
        self.say("STOPPED: " + what)
        if todo:
            self.say(todo)
        self.say("Nothing was broken. You can close this and try again.")
        self.btn.config(text="Close", state="normal",
                        command=self.destroy, bg="#555a63")

    # -- detection --------------------------------------------------
    def _detect(self):
        self.say("Checking your computer...")
        self.say(f"  system: {platform.system()} {platform.machine()}")
        self.say(f"  memory: {total_ram_mb()} MB")

        self.prism = find_prism()
        if self.prism:
            self.say(f"  Prism Launcher: {self.prism}")
        else:
            self.say("  Prism Launcher: not installed")

        existing = []
        if self.prism:
            existing = (find_pack_instances(self.prism, OLD_URL)
                        + find_pack_instances(self.prism, PACK_URL))

        if existing:
            self.mode = "update"
            self.say(f"  found {len(existing)} existing Salvage instance(s)")
            self.steps = [
                ("Check what you have", self._s_check_update),
                ("Point it at the right updates", self._s_switch),
                ("Make sure the updater is there", self._s_bootstrap_all),
            ]
        else:
            self.mode = "install"
            self.steps = [
                ("Get Prism Launcher", self._s_prism),
                ("Create the Salvage instance", self._s_instance),
                ("Set up automatic updates", self._s_bootstrap),
            ]

        self.say("")
        self._present()

    # -- step machinery ---------------------------------------------
    def _present(self):
        if self.step >= len(self.steps):
            return self._finish()

        n = self.step + 1
        total = len(self.steps)
        name, _ = self.steps[self.step]

        blurbs = {
            "Get Prism Launcher":
                ("Prism Launcher is the program that runs modded "
                 "Minecraft. If you already have it, this does nothing. "
                 "If not, it downloads it for you."),
            "Create the Salvage instance":
                ("This makes a new entry in Prism called Salvage, set to "
                 "Minecraft 1.20.1 with Fabric, and picks a sensible "
                 "amount of memory based on your computer."),
            "Set up automatic updates":
                ("This adds a small file that fetches the mod list every "
                 "time you play, so you never have to reinstall anything "
                 "when the pack changes."),
            "Check what you have":
                ("Looks at your existing Salvage setup. Your world, "
                 "settings and keybinds will not be touched -- only "
                 "where updates come from."),
            "Point it at the right updates":
                ("Switches your copy to the stable release channel, so "
                 "you only get changes once they've been tested. A "
                 "backup of your settings file is kept."),
            "Make sure the updater is there":
                ("Checks the auto-update file exists and isn't damaged, "
                 "and re-downloads it if needed."),
        }

        self.show(f"Step {n} of {total}", name,
                  blurbs.get(name, ""), "Do this step")
        self.btn.config(command=self._go, bg=ACCENT)

    def _go(self):
        if self.busy:
            return
        self.busy = True
        self.working()
        fn = self.steps[self.step][1]
        threading.Thread(target=self._run, args=(fn,), daemon=True).start()

    def _run(self, fn):
        try:
            fn()
            self.step += 1
            self.busy = False
            self.after(0, self._present)
        except Stop as e:
            self.busy = False
            self.after(0, lambda: self.stop(e.what, e.todo))
        except Exception as e:
            self.busy = False
            self.after(0, lambda: self.stop(
                f"Unexpected problem: {e}",
                "Send this whole window to Josh."))

    # -- steps: install ---------------------------------------------
    def _s_prism(self):
        if self.prism:
            self.say(f"Prism already installed at {self.prism}")
            return

        self.say("Installing Prism Launcher...")
        if is_mac():
            if not shutil.which("brew"):
                raise Stop(
                    "Prism Launcher isn't installed, and this script "
                    "can't install it for you on this Mac.",
                    "Download it from https://prismlauncher.org/download, "
                    "open it once, then run this again.")
            self.say("  using Homebrew (this takes a minute)")
            r = subprocess.run(["brew", "install", "--cask", "prismlauncher"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise Stop("Homebrew couldn't install Prism Launcher.",
                           "Download it from https://prismlauncher.org/"
                           "download, then run this again.")
            self.prism = Path.home() / "Library/Application Support/PrismLauncher"
        else:
            if not shutil.which("flatpak"):
                raise Stop(
                    "Prism Launcher isn't installed, and flatpak isn't "
                    "either, so this can't install it for you.",
                    "Install Prism from https://prismlauncher.org/download, "
                    "open it once, then run this again.")
            self.say("  using flatpak (this takes a few minutes)")
            r = subprocess.run(
                ["flatpak", "install", "-y", "--user", "flathub",
                 "org.prismlauncher.PrismLauncher"],
                capture_output=True, text=True)
            if r.returncode != 0:
                raise Stop("The flatpak install failed.",
                           "Try running this in a terminal to see why:\n"
                           "  flatpak install flathub "
                           "org.prismlauncher.PrismLauncher")
            self.prism = (Path.home() /
                          ".var/app/org.prismlauncher.PrismLauncher"
                          "/data/PrismLauncher")

        self.prism.mkdir(parents=True, exist_ok=True)
        self.say(f"  done: {self.prism}")

    def _s_instance(self):
        inst = self.prism / "instances" / INSTANCE
        mc = inst / "minecraft"
        self.say(f"Creating instance at {inst}")

        try:
            mc.mkdir(parents=True, exist_ok=True)
        except Exception:
            raise Stop(f"Couldn't create a folder at {mc}",
                       "Check you have permission to write there and "
                       "that your disk isn't full.")

        (inst / "mmc-pack.json").write_text(json.dumps({
            "components": [
                {"important": True, "uid": "net.minecraft",
                 "version": MC_VERSION},
                {"uid": "net.fabricmc.fabric-loader", "version": FABRIC},
            ],
            "formatVersion": 1,
        }, indent=4))

        h = heap_mb()
        self.say(f"  allocating {h} MB of memory")

        cfg = inst / "instance.cfg"
        ours = ("InstanceType", "name", "OverrideCommands",
                "PreLaunchCommand", "OverrideMemory", "MinMemAlloc",
                "MaxMemAlloc")
        keep = []
        if cfg.exists():
            keep = [l for l in cfg.read_text(errors="ignore").splitlines()
                    if not l.split("=")[0] in ours]

        keep += [
            "InstanceType=OneSix",
            f"name={INSTANCE}",
            "OverrideCommands=true",
            f'PreLaunchCommand="$INST_JAVA" -jar '
            f'"$INST_MC_DIR/packwiz-installer-bootstrap.jar" '
            f'-g -s client {PACK_URL}',
            "OverrideMemory=true",
            "MinMemAlloc=4096",
            f"MaxMemAlloc={h}",
        ]
        cfg.write_text("\n".join(keep) + "\n")
        self.say("  instance ready")

    def _s_bootstrap(self):
        mc = self.prism / "instances" / INSTANCE / "minecraft"
        self._fetch_bootstrap(mc)

    # -- steps: update ----------------------------------------------
    def _s_check_update(self):
        self.found = (find_pack_instances(self.prism, OLD_URL)
                      + find_pack_instances(self.prism, PACK_URL))
        for c in self.found:
            self.say(f"  {c.parent.name}")
        self.say(f"Found {len(self.found)} instance(s). Your worlds and "
                 f"settings stay exactly as they are.")

    def _s_switch(self):
        import time
        changed = 0
        for cfg in self.found:
            text = cfg.read_text(errors="ignore")
            if OLD_URL not in text:
                self.say(f"  {cfg.parent.name}: already correct")
                continue
            backup = cfg.with_suffix(
                f".cfg.backup-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(cfg, backup)
            cfg.write_text(text.replace(OLD_URL, PACK_URL))
            self.say(f"  {cfg.parent.name}: switched (backup saved)")
            changed += 1
        self.say(f"Changed {changed} instance(s).")

    def _s_bootstrap_all(self):
        for cfg in self.found:
            self._fetch_bootstrap(cfg.parent / "minecraft")

    # -- shared ------------------------------------------------------
    def _fetch_bootstrap(self, mc):
        jar = mc / "packwiz-installer-bootstrap.jar"
        if jar.exists() and jar.stat().st_size > 10000:
            self.say(f"  updater already present in {mc.parent.name}")
            return
        mc.mkdir(parents=True, exist_ok=True)
        self.say("  downloading the updater...")
        try:
            urllib.request.urlretrieve(BOOTSTRAP, jar)
        except Exception:
            raise Stop("Couldn't download the updater from GitHub.",
                       "Check your internet connection and try again. "
                       "If GitHub is blocked on your network, that's why.")
        if jar.stat().st_size < 10000:
            raise Stop("The updater downloaded but looks damaged.",
                       "Your network may be interfering with downloads. "
                       "Try a different connection.")
        self.say("  updater ready")

    # -- finish ------------------------------------------------------
    def _finish(self):
        self.step_lbl.config(text="")
        self.title_lbl.config(text="All done", fg=GOOD)

        if self.mode == "install":
            msg = ("Open Prism Launcher, sign in with your Microsoft "
                   "account, then click Salvage and press Launch.\n\n"
                   "The first launch downloads about 150 mods, so give "
                   "it several minutes.")
        else:
            msg = ("Nothing else to do. Just launch as normal.\n\n"
                   "Your world, settings, keybinds and shaders were not "
                   "touched.")

        self.desc_lbl.config(text=msg)
        self.say("")
        self.say("Finished.")

        if self.mode == "install":
            self.say("")
            self.say("Then try joining the server once. It will say you "
                     "aren't whitelisted -- that's expected, and it's how "
                     "you get added. Just tell Josh you tried.")

        if trash_self():
            self.say("(this setup file has been moved to the trash)")

        self.btn.config(text="Close", command=self.destroy, bg=GOOD)


class Stop(Exception):
    def __init__(self, what, todo=""):
        self.what = what
        self.todo = todo
        super().__init__(what)


if __name__ == "__main__":
    App().mainloop()

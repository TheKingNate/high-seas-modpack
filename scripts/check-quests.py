#!/usr/bin/env python3
"""
Validates every id in the generated questline against the mods actually in the pack.

    cd ~/mc/high-seas && python3 scripts/check-quests.py

Why this exists: FTB Quests does not error on an unresolvable id. An item task
pointing at a mod that isn't installed renders a "Missing Item" placeholder in a
quest the player can never complete, silently, forever. A lang key is not proof
either - Bountiful ships `bounties_done` lang keys but registers no stat at all.

So this checks the *registered* thing, not the name:
    item / block  -> assets/<ns>/models/item/<path>.json or blockstates/<path>.json
    entity        -> entity.<ns>.<path> in the lang file
    structure     -> data/<ns>/worldgen/structure/<path>.json  (or tags/ for #tags)
    biome         -> data/<ns>/worldgen/biome/ or tags/worldgen/biome/
    advancement   -> data/<ns>/advancements/<path>.json
    dimension     -> data/<ns>/dimension/<path>.json

Exit status is 1 if anything is unresolvable, so it can gate a release.
"""

import glob
import json
import os
import re
import sys
import zipfile
from collections import defaultdict

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTS = os.path.join(PACK, "config", "ftbquests", "quests", "chapters")

INSTANCES = [
    os.path.expanduser("~/Library/Application Support/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
    os.path.expanduser("~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
    os.path.expanduser("~/.local/share/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
]

VANILLA = "minecraft"


def find_mods_dir():
    for d in INSTANCES:
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.jar")):
            return d
    return None


# Deliberately OUTSIDE the pack directory. A cache inside it gets swept into
# index.toml by `packwiz refresh` - .packwizignore is an extension blocklist, so
# any new top-level folder ships to clients. That happened: 63 cached jars were
# indexed, and because they are gitignored every client hit a 404 at pre-launch.
CACHE = os.path.join(os.path.expanduser("~/.cache/salvage"), "questcache")


def pack_jars():
    """Every jar the pack declares: filename -> download url (None if CF-metadata)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(PACK, "mods", "*.pw.toml"))):
        t = open(f).read()
        fn = re.search(r'^filename = "(.*)"', t, re.M)
        url = re.search(r'^url = "(.*)"', t, re.M)
        if fn:
            out[fn.group(1)] = url.group(1) if url else None
    return out


def fill_cache(mods_dir):
    """Fetch any pack jar the instance lacks, so validation follows the PACK.

    An instance drifts behind the pack constantly (it only syncs when the game
    launches). Validating against a stale instance produces false failures for
    mods that are perfectly fine - which is exactly what happened the first time
    this ran. The pack's mods/*.pw.toml is the source of truth, not any instance.
    """
    import urllib.request
    have = {os.path.basename(j) for j in glob.glob(os.path.join(mods_dir, "*.jar"))}
    have |= {os.path.basename(j) for j in glob.glob(os.path.join(CACHE, "*.jar"))}
    missing = {fn: u for fn, u in pack_jars().items() if fn not in have}
    fetchable = {fn: u for fn, u in missing.items() if u}
    if missing:
        print(f"  instance is {len(missing)} jar(s) behind the pack")
    if fetchable:
        os.makedirs(CACHE, exist_ok=True)
        print(f"  fetching {len(fetchable)} into .questcache/ ...")
        for fn, u in sorted(fetchable.items()):
            try:
                urllib.request.urlretrieve(u, os.path.join(CACHE, fn))
            except Exception as e:
                print(f"    ! {fn}: {e}")
    unfetchable = sorted(set(missing) - set(fetchable))
    if unfetchable:
        print(f"  {len(unfetchable)} have no direct url (CurseForge metadata); "
              f"ids from these cannot be checked:")
        for fn in unfetchable[:6]:
            print(f"    - {fn}")
    return unfetchable


def index_jars(mods_dir):
    """Build namespace -> set of asset/data paths, once, for every installed jar."""
    idx = defaultdict(set)
    lang = defaultdict(dict)
    jars = sorted(glob.glob(os.path.join(mods_dir, "*.jar"))) + \
           sorted(glob.glob(os.path.join(CACHE, "*.jar")))
    for jar in jars:
        try:
            z = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            print(f"  ! unreadable jar: {os.path.basename(jar)}")
            continue
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) > 2 and parts[0] in ("assets", "data"):
                idx[parts[1]].add(name)
        for name in z.namelist():
            if re.fullmatch(r"assets/[^/]+/lang/en_us\.json", name):
                try:
                    lang[name.split("/")[1]].update(json.loads(z.read(name)))
                except Exception:
                    pass
    return idx, lang


def parse_tasks():
    """Yield (chapter, quest, type, id, count) for every task in the questline."""
    for f in sorted(glob.glob(os.path.join(QUESTS, "*.snbt"))):
        ch = os.path.basename(f)[:-5]
        text = open(f).read()
        for block in re.split(r"\n\t\t\{\n", text)[1:]:
            qt = re.search(r'\t\t\ttitle: "([^"]+)"', block)
            quest = qt.group(1) if qt else "?"
            body = block.split("rewards: [")[0]
            for tb in re.split(r"\n\t\t\t\t\{\n", body)[1:]:
                ty = re.search(r'type: "([a-z]+)"', tb)
                if not ty:
                    continue
                ty = ty.group(1)
                key = {"item": "item", "kill": "entity", "structure": "structure",
                       "biome": "biome", "advancement": "advancement",
                       "dimension": "dimension"}.get(ty)
                if not key:
                    continue          # checkmark, stat, etc.
                val = re.search(r'%s: "([^"]+)"' % key, tb)
                if val:
                    yield ch, quest, ty, val.group(1)


def resolves(kind, ident, idx, lang):
    ident = ident.strip()
    tag = ident.startswith("#")
    if tag:
        ident = ident[1:]
    ns, _, path = ident.partition(":")
    if not path:
        ns, path = VANILLA, ident

    if ns == VANILLA:
        return True, "vanilla"                       # trust vanilla ids
    if ns not in idx:
        return False, f"namespace '{ns}' not present in any installed jar"

    files = idx[ns]
    if kind == "item":
        ok = (f"assets/{ns}/models/item/{path}.json" in files
              or f"assets/{ns}/blockstates/{path}.json" in files)
        if not ok:
            named = any(k.endswith(f".{ns}.{path}") for k in lang.get(ns, {}))
            return False, ("lang key exists but no model/blockstate - not registered"
                           if named else "no model, blockstate or lang key")
        return True, ""
    if kind == "kill":
        ok = any(k == f"entity.{ns}.{path}" for k in lang.get(ns, {}))
        return (ok, "" if ok else "no entity.<ns>.<path> lang key")
    if kind == "structure":
        sub = "tags/worldgen/structure" if tag else "worldgen/structure"
        ok = f"data/{ns}/{sub}/{path}.json" in files
        return (ok, "" if ok else f"no data/{ns}/{sub}/{path}.json")
    if kind == "biome":
        sub = "tags/worldgen/biome" if tag else "worldgen/biome"
        ok = f"data/{ns}/{sub}/{path}.json" in files
        return (ok, "" if ok else f"no data/{ns}/{sub}/{path}.json")
    if kind == "advancement":
        ok = f"data/{ns}/advancements/{path}.json" in files
        return (ok, "" if ok else f"no data/{ns}/advancements/{path}.json")
    if kind == "dimension":
        ok = f"data/{ns}/dimension/{path}.json" in files
        return (ok, "" if ok else f"no data/{ns}/dimension/{path}.json")
    return True, ""


def main():
    mods_dir = find_mods_dir()
    if not mods_dir:
        print("No Salvage-dev instance found; cannot validate. Checked:")
        for d in INSTANCES:
            print("   ", d)
        return 2
    print(f"validating against {mods_dir}")

    fill_cache(mods_dir)
    idx, lang = index_jars(mods_dir)
    print(f"  {len(idx)} namespaces across the installed jars\n")

    bad, total = [], 0
    for ch, quest, ty, ident in parse_tasks():
        total += 1
        ok, why = resolves(ty, ident, idx, lang)
        if not ok:
            bad.append((ch, quest, ty, ident, why))

    for ch, quest, ty, ident, why in bad:
        print(f"  UNRESOLVED  {ch}/{quest}")
        print(f"              {ty}: {ident}   <- {why}")

    print(f"\n{total - len(bad)}/{total} task ids resolve.")
    if bad:
        print(f"{len(bad)} would render as a Missing Item in an uncompletable quest.")
        return 1
    print("No uncompletable quests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

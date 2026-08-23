#!/usr/bin/env python3
"""
Finds mods that call classes which no longer exist in the version of their
dependency that the pack actually ships.

    cd ~/mc/high-seas && python3 scripts/check-classes.py

Why this exists: check-deps.py validates declared version RANGES, and that is not
enough. Spellblades declares `azurelib >=1.0.29`, the pack shipped AzureLib 3.1.12,
the range was satisfied - and the game still died at startup:

    NoClassDefFoundError: mod/azure/azurelib/animatable/GeoEntity

AzureLib 3.1.0 deleted the whole `animatable` package. A version-range check cannot
see that; only the bytecode can. Druids was broken the same way and would have
crashed immediately after Spellblades was fixed.

The signal is precise because of one rule: a missing class is only reported when the
mod that OWNS its package is present in the pack. Mods routinely reference classes
from absent optional integrations (JEI, Hex Casting, ComputerCraft ...) behind
guards - the log is full of harmless "Error loading class:" lines for exactly that.
Those are skipped. A package whose owner IS installed but whose class is gone is a
real, hard break.

Exit status is 1 if anything is unresolvable, so it can gate a release.
"""

import glob
import io
import json
import os
import re
import struct
import sys
import zipfile
from collections import defaultdict

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.expanduser("~/.cache/salvage"), "questcache")
INSTANCES = [
    os.path.expanduser("~/Library/Application Support/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
    os.path.expanduser("~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
    os.path.expanduser("~/.local/share/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
]

# Runtime, loader and library packages. Vanilla is excluded because references to
# it are intermediary-remapped at load time and cannot be resolved from the jar.
SKIP_PREFIXES = (
    "java/", "javax/", "jdk/", "sun/", "net/minecraft/", "com/mojang/",
    "net/fabricmc/", "org/spongepowered/", "org/objectweb/", "org/ow2/",
    "com/llamalad7/", "org/apache/", "org/slf4j/", "com/google/", "io/netty/",
    "it/unimi/", "org/joml/", "org/lwjgl/", "kotlin/", "kotlinx/",
    "org/jetbrains/", "org/intellij/", "com/electronwill/", "org/json/",
    "org/lwjglx/", "oshi/", "com/ibm/", "org/checkerframework/",
    # Forge classes referenced by cross-platform mods and guarded by a runtime
    # platform check. Present in almost every multiloader jar; never a real break.
    "net/minecraftforge/", "cpw/mods/", "dev/architectury/platform/forge/",
)

# Package depths tried when attributing a class to the mod that owns it.
# Deepest first: 'net/blay09/mods' is a VENDOR root shared by balm, waystones and
# craftingtweaks, so a depth-3 match there means nothing. 'mod/azure/azurelib' is
# owned by exactly one mod, so a depth-3 match there is meaningful.
OWNER_DEPTHS = (4, 3)


def parse_class_refs(data):
    """Pull every CONSTANT_Class name out of a .class constant pool.

    Reading the pool properly rather than regexing the bytes: a regex over raw
    bytecode picks up string literals and fragments and produces noise, and this
    check is only useful if a hit is trustworthy.
    """
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        return set()
    count = struct.unpack(">H", data[8:10])[0]
    pos = 10
    utf8, classes = {}, []
    i = 1
    while i < count:
        tag = data[pos]
        pos += 1
        if tag == 1:                                  # Utf8
            n = struct.unpack(">H", data[pos:pos + 2])[0]
            utf8[i] = data[pos + 2:pos + 2 + n].decode("utf-8", "replace")
            pos += 2 + n
        elif tag == 7:                                # Class
            classes.append(struct.unpack(">H", data[pos:pos + 2])[0])
            pos += 2
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag in (5, 6):                           # Long/Double eat two slots
            pos += 8
            i += 1
        elif tag == 15:
            pos += 3
        elif tag in (8, 16, 19, 20):
            pos += 2
        else:
            return set()                              # unknown tag: bail, stay quiet
        i += 1
    out = set()
    for idx in classes:
        n = utf8.get(idx)
        if not n:
            continue
        n = n.lstrip("[")                             # array descriptors
        if n.startswith("L") and n.endswith(";"):
            n = n[1:-1]
        if n and not n.startswith("("):
            out.add(n)
    return out


def walk_jar(path):
    """(classes provided, classes referenced), following jar-in-jar."""
    provided, referenced = set(), {}

    def walk(z):
        for n in z.namelist():
            if n.endswith(".class"):
                provided.add(n[:-6])
                try:
                    for ref in parse_class_refs(z.read(n)):
                        referenced.setdefault(ref, n[:-6])
                except Exception:
                    pass
            elif n.startswith("META-INF/jars/") and n.endswith(".jar"):
                try:
                    walk(zipfile.ZipFile(io.BytesIO(z.read(n))))
                except Exception:
                    pass

    try:
        walk(zipfile.ZipFile(path))
    except Exception:
        pass
    return provided, referenced


def mixin_classes(path):
    """Fully-qualified names of a mod's mixin classes.

    A mixin whose TARGET is missing is only a warning - Fabric logs
    "@Mixin target ... was not found" and skips it, so the game still starts but
    that piece of the mod silently does nothing. A missing class referenced from
    ordinary code is a hard NoClassDefFoundError. Reporting both as "broken"
    would make this tool cry wolf, so they are separated.
    """
    out = set()
    try:
        z = zipfile.ZipFile(path)
        meta = json.loads(z.read("fabric.mod.json"))
    except Exception:
        return out
    cfgs = [c if isinstance(c, str) else c.get("config")
            for c in (meta.get("mixins") or [])]
    for cfg in filter(None, cfgs):
        try:
            d = json.loads(z.read(cfg))
        except Exception:
            continue
        pkg = d.get("package", "").replace(".", "/")
        for key in ("mixins", "client", "server"):
            for m in d.get(key) or []:
                out.add(f"{pkg}/{m}".replace(".", "/"))
    return out


def pack_filenames():
    out = {}
    for f in sorted(glob.glob(os.path.join(PACK, "mods", "*.pw.toml"))):
        t = open(f).read()
        m = re.search(r'^filename = "(.*)"', t, re.M)
        if m:
            out[m.group(1)] = os.path.basename(f)
    return out


def locate(filenames):
    found = {}
    for d in INSTANCES + [CACHE]:
        for j in glob.glob(os.path.join(d, "*.jar")):
            b = os.path.basename(j)
            if b in filenames and b not in found:
                found[b] = j
    return found


def prefixes(cls):
    parts = cls.split("/")
    return {d: "/".join(parts[:d]) for d in OWNER_DEPTHS if len(parts) > d}


def main():
    want = pack_filenames()
    have = locate(want)
    missing_jars = sorted(set(want) - set(have))

    print(f"{len(want)} mods in the pack, {len(have)} jars readable")
    if missing_jars:
        print(f"  {len(missing_jars)} not available locally, skipped: "
              f"{', '.join(missing_jars[:4])}")

    provided, refs, per_jar = set(), {}, {}
    mod_id_of, declared_deps, mixins = {}, {}, {}
    for name, path in sorted(have.items()):
        p, r = walk_jar(path)
        per_jar[name] = (p, r)
        mixins[name] = mixin_classes(path)
        provided |= p
        refs[name] = r
        try:
            m = json.loads(zipfile.ZipFile(path).read("fabric.mod.json"))
            mod_id_of[name] = m.get("id")
            declared_deps[name] = set(m.get("depends") or {}) | set(m.get("recommends") or {})
        except Exception:
            mod_id_of[name] = None
            declared_deps[name] = set()
    print(f"  {len(provided)} classes provided across the pack\n")

    # prefix -> the set of mods providing classes under it, so a prefix owned by
    # several mods can be recognised as a shared vendor root rather than an owner.
    owners = defaultdict(set)
    for name, path in sorted(have.items()):
        for c in per_jar[name][0]:
            for pre in prefixes(c).values():
                owners[pre].add(name)

    bad = defaultdict(list)
    for name, rs in refs.items():
        deps = declared_deps.get(name, set())
        for r in sorted(rs):
            from_class = rs[r]
            if r in provided or r.startswith(SKIP_PREFIXES):
                continue
            if r.split("$")[0] in provided:
                continue
            # Attribute the reference to a single owning mod, deepest prefix first.
            src = None
            for d in OWNER_DEPTHS:
                pre = prefixes(r).get(d)
                if not pre or pre not in owners:
                    continue
                who = owners[pre]
                if len(who) == 1:            # ambiguous vendor root -> not an owner
                    src = next(iter(who))
                break
            if not src or src == name:       # unattributable, or the mod's own class
                continue
            # Only a real break if this mod DECLARES a dependency on that mod.
            if mod_id_of.get(src) not in deps:
                continue
            bad[name].append((r, src, from_class in mixins.get(name, ())))

    hard = total = 0
    for name in sorted(bad):
        misses = sorted(set(bad[name]))
        for is_mixin in (False, True):
            sel = [(r, src) for r, src, mx in misses if mx is is_mixin]
            if not sel:
                continue
            total += len(sel)
            if not is_mixin:
                hard += len(sel)
            by_owner = defaultdict(list)
            for r, src in sel:
                by_owner[src].append(r)
            tag = "MIXIN " if is_mixin else "BROKEN"
            print(f"  {tag}  {name}  ({want.get(name, '?')})")
            for src, ms in sorted(by_owner.items()):
                print(f"          {'mixin target' if is_mixin else 'calls'} "
                      f"{len(ms)} class(es) absent from {src}:")
                for m in ms[:4]:
                    print(f"            {m}")
                if len(ms) > 4:
                    print(f"            ... and {len(ms) - 4} more")
            print("          -> logged and skipped at load; that part of the mod "
                  "silently does nothing." if is_mixin
                  else "          -> NoClassDefFoundError at load.")
            print()

    if not total:
        print("Every cross-mod class reference resolves.")
        return 0
    print(f"{total} unresolvable reference(s) across {len(bad)} mod(s): "
          f"{hard} hard, {total - hard} mixin-only.")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())

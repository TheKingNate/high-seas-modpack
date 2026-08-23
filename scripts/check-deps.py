#!/usr/bin/env python3
"""
Validates the whole pack's mod dependency graph, including VERSION RANGES.

    cd ~/mc/high-seas && python3 scripts/check-deps.py

Checking that a dependency is merely *present* is not enough. `rpgsp` pins
`rpgmana` to exactly `=1.0.8.2`; the pack shipped 1.0.8.4 and Fabric refused to
launch with "requires version 1.0.8.2 ... but only the wrong version is present".
Presence-only checking cannot catch that, so this compares versions too.

It also re-checks the client/server split: a mod that ships to clients must not
depend on one flagged `side = "server"`, because packwiz-installer runs `-s client`
and silently skips those - the client then dies on a missing dependency.

Exit status is 1 if anything is unsatisfiable.
"""

import glob
import json
import os
import re
import sys
import zipfile

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.expanduser("~/.cache/salvage"), "questcache")
INSTANCES = [
    os.path.expanduser("~/Library/Application Support/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
    os.path.expanduser("~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances/Salvage-dev/minecraft/mods"),
]

# Dependencies Fabric Loader itself provides, or that are bundled everywhere.
PROVIDED = {"fabric", "fabricloader", "minecraft", "java", "fabric-api",
            "fabricloader-fabric", "mixinextras"}


def norm(v):
    """Version string -> comparable tuple of ints, ignoring build metadata."""
    v = re.split(r"[+\-]", str(v))[0]
    parts = []
    for p in v.split("."):
        m = re.match(r"\d+", p)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts)


def cmp_ok(have, op, want):
    a, b = norm(have), norm(want)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return {"=": a == b, "==": a == b, ">=": a >= b, "<=": a <= b,
            ">": a > b, "<": a < b}.get(op, True)


def satisfies(have, spec):
    """True/False, or None when the range syntax is beyond this checker."""
    if have is None:
        return False
    specs = spec if isinstance(spec, list) else [spec]
    for s in specs:                      # a list of ranges means OR
        if _one(have, str(s)) in (True, None):
            return _one(have, str(s))
    return False


def _one(have, s):
    s = s.strip()
    if s in ("*", ""):
        return True
    if "x" in s.lower() or "X" in s:            # 1.0.x style wildcard
        pre = re.split(r"[xX]", s, maxsplit=1)[0].rstrip(".")
        return norm(have)[:len(norm(pre))] == norm(pre)
    ok = True
    for clause in s.split():             # space-separated clauses are AND
        m = re.match(r"^(>=|<=|==|=|>|<|\^|~)?\s*(.+)$", clause)
        if not m:
            return None
        op, want = m.group(1) or "=", m.group(2)
        if op in ("^", "~"):             # caret/tilde: same major (and minor for ~)
            a, b = norm(have), norm(want)
            if a < b:
                ok = False
            elif op == "^" and a[:1] != b[:1]:
                ok = False
            elif op == "~" and a[:2] != b[:2]:
                ok = False
        else:
            ok = ok and cmp_ok(have, op, want)
        if not ok:
            return False
    return ok


def load_pack():
    """jar filename -> (side, pw.toml name)"""
    out = {}
    for f in sorted(glob.glob(os.path.join(PACK, "mods", "*.pw.toml"))):
        t = open(f).read()
        fn = re.search(r'^filename = "(.*)"', t, re.M)
        sd = re.search(r'^side = "(\w+)"', t, re.M)
        if fn:
            out[fn.group(1)] = (sd.group(1) if sd else "both", os.path.basename(f))
    return out


def nested(z, acc):
    """Collect mod ids from META-INF/jars - Fabric API alone bundles ~40 of them.

    Without this the checker reports scores of false failures: xaerolib, kelvin,
    vtil, porting_lib_*, team_reborn_energy and every fabric-*-v1 submodule all
    ship nested inside a parent jar rather than as pack entries.
    """
    import io
    for n in z.namelist():
        if not (n.startswith("META-INF/jars/") and n.endswith(".jar")):
            continue
        try:
            inner = zipfile.ZipFile(io.BytesIO(z.read(n)))
            if "fabric.mod.json" not in inner.namelist():
                continue
            m = json.loads(inner.read("fabric.mod.json"))

            def keep(mid, ver):
                # highest wins here too: Create bundles flywheel 1.0.5-264 while
                # Ponder (nested inside Create) bundles 1.0.0. First-seen reported
                # a phantom "create requires flywheel >=1.0.5-264, pack has 1.0.0".
                if mid not in acc or norm(ver) > norm(acc[mid]):
                    acc[mid] = ver

            keep(m["id"], m.get("version"))
            for p in m.get("provides", []) or []:
                keep(p, m.get("version"))
            nested(inner, acc)                      # bundles can nest further
        except Exception:
            pass


def load_jars():
    """jar filename -> (fabric.mod.json, {bundled mod id: version})"""
    out = {}
    for d in INSTANCES + [CACHE]:
        for j in glob.glob(os.path.join(d, "*.jar")):
            b = os.path.basename(j)
            if b in out:
                continue
            try:
                z = zipfile.ZipFile(j)
                if "fabric.mod.json" not in z.namelist():
                    continue
                acc = {}
                nested(z, acc)
                out[b] = (json.loads(z.read("fabric.mod.json")), acc)
            except Exception:
                pass
    return out


def load_overrides():
    """config/fabric_loader_dependencies.json - the loader applies these before
    resolving, so a checker that ignores them reports conflicts that cannot occur."""
    f = os.path.join(PACK, "config", "fabric_loader_dependencies.json")
    if not os.path.exists(f):
        return {}
    try:
        return (json.load(open(f)) or {}).get("overrides", {}) or {}
    except Exception as e:
        print(f"  ! {os.path.basename(f)} is unreadable: {e}")
        return {}


def apply_overrides(mid, depends, ov):
    o = ov.get(mid)
    if not o:
        return depends
    d = dict(depends)
    if "depends" in o:
        d = dict(o["depends"])
    for k in o.get("-depends", {}) or {}:
        d.pop(k, None)
    d.update(o.get("+depends", {}) or {})
    return d


def main():
    pack = load_pack()
    ov = load_overrides()
    jars = load_jars()
    missing_jars = [f for f in pack if f not in jars]

    # mod id -> (version, jar). Includes ids a mod declares it "provides".
    have = {}
    for jar, (m, bundled) in jars.items():
        if jar not in pack:
            continue
        def offer(mid, ver, src):
            """Several jars can bundle the same lib at different versions;
            Fabric resolves to the HIGHEST, so record that, not the first seen."""
            cur = have.get(mid)
            if cur is None or norm(ver) > norm(cur[0]):
                have[mid] = (ver, src)

        offer(m["id"], m.get("version"), jar)
        for p in m.get("provides", []) or []:
            offer(p, m.get("version"), jar)
        for bid, bver in bundled.items():        # jar-in-jar counts as present
            offer(bid, bver, jar)

    print(f"{len(pack)} mods in the pack, {len(pack) - len(missing_jars)} jars readable")
    if ov:
        print(f"  {len(ov)} loader dependency override(s) applied: {', '.join(sorted(ov))}")
    if missing_jars:
        print(f"  {len(missing_jars)} jar(s) not available locally - run check-quests.py "
              f"first to populate the cache, or those go unchecked:")
        for f in missing_jars[:8]:
            print(f"    - {f}")

    hard, softside, unknown = [], [], []
    for jar, (m, _b) in jars.items():
        if jar not in pack:
            continue
        mside = pack[jar][0]
        deps = apply_overrides(m["id"], m.get("depends") or {}, ov)
        for dep, spec in deps.items():
            if dep in PROVIDED:
                continue
            if dep not in have:
                hard.append((m["id"], jar, dep, spec, "not in the pack at all"))
                continue
            hv, hjar = have[dep]
            res = satisfies(hv, spec)
            if res is False:
                hard.append((m["id"], jar, dep, spec, f"pack has {hv}"))
            elif res is None:
                unknown.append((m["id"], dep, spec))
            if mside != "server" and pack.get(hjar, ("both",))[0] == "server":
                softside.append((m["id"], mside, dep, pack[hjar][1]))

    print()
    for mid, jar, dep, spec, why in hard:
        print(f"  UNSATISFIED  {mid} requires {dep} {spec}  <- {why}")
    for mid, ms, dep, depfile in softside:
        print(f"  SIDE SPLIT   {mid} (side={ms}) requires {dep}, which is side=server in {depfile}")
    for mid, dep, spec in unknown:
        print(f"  UNCHECKED    {mid} requires {dep} '{spec}' - range syntax not understood")

    if not hard and not softside:
        print("Dependency graph is satisfiable.")
        if unknown:
            print(f"({len(unknown)} range(s) not machine-checked - listed above.)")
        return 0
    print(f"\n{len(hard)} unsatisfied, {len(softside)} side-split. The game will refuse to launch.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

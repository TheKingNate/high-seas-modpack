#!/usr/bin/env python3
"""
Validates config/fabric_loader_dependencies.json using Fabric Loader's OWN parser.

    cd ~/mc/high-seas && python3 scripts/check-loader-overrides.py

Hand-checking this file is not good enough. It is parsed by the loader before any
mod loads, and a rejected key is a hard launch abort with no fallback - a `_comment`
key (valid JSON, and the obvious place to explain the file) took the whole pack down:

    ParseMetadataException: Unsupported root key: _comment

Only `version` and `overrides` are accepted at the root. Rather than encode that
rule here and let it drift from the loader, this instantiates the real
DependencyOverrides class against the real config dir. If the loader would reject
the file at launch, this rejects it now.

Exit status is 1 if the file would fail to parse, so it can gate a push.
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(PACK, "config")
TARGET = os.path.join(CFG, "fabric_loader_dependencies.json")

LOADER_GLOBS = [
    os.path.expanduser("~/Library/Application Support/PrismLauncher/libraries/**/fabric-loader-*.jar"),
    os.path.expanduser("~/Library/Application Support/PrismLauncher/**/fabric-loader-*.jar"),
    os.path.expanduser("~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/**/fabric-loader-*.jar"),
    os.path.expanduser("~/.local/share/PrismLauncher/**/fabric-loader-*.jar"),
]
JAVA_HOMES = [
    os.path.expanduser("~/Library/Application Support/PrismLauncher/java/java-runtime-gamma/jre.bundle/Contents/Home"),
    os.path.expanduser("~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/java/java-runtime-gamma"),
]

PROBE = r"""
import java.nio.file.*;
import java.lang.reflect.*;

public class Probe {
    public static void main(String[] a) throws Exception {
        Class<?> c = Class.forName("net.fabricmc.loader.impl.metadata.DependencyOverrides");
        Constructor<?> ctor = c.getConstructor(Path.class);
        try {
            Object o = ctor.newInstance(Paths.get(a[0]));
            Method m = c.getMethod("getAffectedModIds");
            System.out.println("OK " + m.invoke(o));
        } catch (InvocationTargetException e) {
            Throwable t = e.getCause();
            while (t.getCause() != null) t = t.getCause();
            System.out.println("FAIL " + t.getMessage());
            System.exit(3);
        }
    }
}
"""


def newest(patterns):
    hits = []
    for p in patterns:
        hits += glob.glob(p, recursive=True)
    return sorted(hits)[-1] if hits else None


def main():
    if not os.path.exists(TARGET):
        print("no config/fabric_loader_dependencies.json - nothing to validate")
        return 0

    try:
        doc = json.load(open(TARGET))
    except Exception as e:
        print(f"FAIL  not valid JSON at all: {e}")
        return 1

    # Cheap check first, so this still says something useful with no JDK around.
    stray = [k for k in doc if k not in ("version", "overrides")]
    if stray:
        print(f"FAIL  unsupported root key(s): {', '.join(stray)}")
        print("      the loader accepts only 'version' and 'overrides'; anything")
        print("      else aborts launch before any mod loads.")
        return 1

    loader = newest(LOADER_GLOBS)
    jh = next((j for j in JAVA_HOMES if os.path.isfile(os.path.join(j, "bin", "java"))), None)
    if not loader or not jh:
        print("root keys OK, but could not find a fabric-loader jar + JDK to run the")
        print("real parser against. Structural check only:")
        print(f"  overrides for: {', '.join(sorted(doc.get('overrides', {})))}")
        return 0

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "Probe.java")
        open(src, "w").write(PROBE)
        r = subprocess.run([os.path.join(jh, "bin", "java"), "-cp", loader, src, CFG],
                           capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(f"parser: {os.path.basename(loader)}")
    if r.returncode == 0 and out.startswith("OK"):
        print(f"Accepted by the loader. Overrides apply to: {out[3:]}")
        return 0
    print(f"REJECTED by the loader - this would abort launch:\n  {out}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

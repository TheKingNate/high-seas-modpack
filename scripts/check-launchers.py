#!/usr/bin/env python3
"""
Validates the three installers against each other and against REPAIR-SPEC.md.

    cd ~/mc/high-seas && python3 scripts/check-launchers.py

Why this exists. Three implementations of one behaviour, in three languages, none
of which can be run on the machine the other two are edited from. They have
drifted before - one release had macOS reporting `failed hash` where Windows and
Python reported `corrupt`, three different report titles, and three spellings of
the tracking label, so two reports of the same fault read as two different faults.

Three checks, each guarding a failure that is silent at runtime:

  1. The Windows batch stub. `Salvage-Setup-Windows.bat` is a batch header
     followed by a PowerShell script, and the header extracts the rest with
     `more +N "%~f0"`. N must equal the number of stub lines. Edit the stub -
     even to add a comment - and N is wrong, `more` hands PowerShell either a
     truncated script or a few lines of batch, and the installer dies before its
     window opens. cmd reports nothing. This is the one that bit during the
     clipboard change.

  2. Brace and paren balance of that PowerShell, tokenised properly: block
     comments, here-strings, single vs double quotes, backtick escapes, and
     $( ) subexpressions nested inside double-quoted strings. A regex gets all
     of those wrong. This is not a parser - it will not catch every syntax
     error - but an unbalanced brace is the failure a bulk edit actually causes.

  3. Fixed vocabulary. Every word in the REPAIR-SPEC.md vocabulary table has to
     appear in all three, and the words they replaced must appear in none.

Exit status is 1 if anything fails, so it can gate a release.
"""

import re
import sys

MAC = "launchers/Salvage-Setup-Mac.command"
WIN = "launchers/Salvage-Setup-Windows.bat"
PY = "install/salvage-setup.py"
ALL_THREE = [MAC, WIN, PY]

# From the vocabulary table in install/REPAIR-SPEC.md. Left: what all three must
# emit. Right: spellings a previous version used, which must not come back.
REQUIRED = [
    "SALVAGE  -  install report",
    "failed hash",
    "what this run changed",
    "[ OK ]",
    "[ !! ]",
]
FORBIDDEN = [
    "Salvage repair report",
    "Salvage install report",
    "changed by this run",
]

PS_STARTS = "Add-Type -AssemblyName System.Windows.Forms"

problems = []


def check_stub():
    lines = open(WIN).read().split("\n")
    m = re.search(r"more \+(\d+)", "\n".join(lines[:10]))
    if not m:
        problems.append(f"{WIN}: no 'more +N' line in the stub")
        return None
    n = int(m.group(1))
    try:
        actual = next(i for i, l in enumerate(lines) if l.startswith(PS_STARTS))
    except StopIteration:
        problems.append(f"{WIN}: cannot find where the PowerShell starts")
        return None
    if n != actual:
        problems.append(
            f"{WIN}: stub says 'more +{n}' but the PowerShell starts at line "
            f"{actual}. The extracted script would be wrong and the installer "
            f"would die silently. Set it to 'more +{actual}'.")
    else:
        print(f"  ok    {WIN}: more +{n} matches the PowerShell start")
    return "\n".join(lines[actual:])


def balance(src):
    """Residual depth, unclosed openers, mismatched closers."""
    i, n = 0, len(src)
    pairs = {"}": "{", ")": "(", "]": "["}
    depth = {"{": 0, "(": 0, "[": 0}
    stack, bad, line = [], [], 1
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1; i += 1; continue
        if src.startswith("<#", i):
            j = src.find("#>", i + 2); i = n if j < 0 else j + 2; continue
        if ch == "#" and (i == 0 or src[i - 1] in " \t\n;{()"):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith('@"', i):
            j = src.find('\n"@', i + 2); i = n if j < 0 else j + 3; continue
        if src.startswith("@'", i):
            j = src.find("\n'@", i + 2); i = n if j < 0 else j + 3; continue
        if ch == "'":
            i += 1
            while i < n:
                if src[i] == "'":
                    if i + 1 < n and src[i + 1] == "'":
                        i += 2; continue
                    i += 1; break
                if src[i] == "\n":
                    line += 1
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n:
                c = src[i]
                if c == "`":
                    i += 2; continue
                if c == '"':
                    i += 1; break
                if c == "\n":
                    line += 1
                if src.startswith("$(", i):
                    d = 0; i += 1
                    while i < n:
                        if src[i] == "(":
                            d += 1
                        elif src[i] == ")":
                            d -= 1
                            if d == 0:
                                i += 1; break
                        elif src[i] == "\n":
                            line += 1
                        i += 1
                    continue
                i += 1
            continue
        if ch == "`":
            i += 2; continue
        if ch in "{([":
            depth[ch] += 1; stack.append((ch, line)); i += 1; continue
        if ch in ")}]":
            want = pairs[ch]
            if not stack or stack[-1][0] != want:
                bad.append((line, ch))
            else:
                stack.pop(); depth[want] -= 1
            i += 1; continue
        i += 1
    return depth, stack, bad


def check_balance(ps):
    if ps is None:
        return
    depth, stack, bad = balance(ps)
    if any(v for v in depth.values()) or stack or bad:
        problems.append(
            f"{WIN}: PowerShell is unbalanced - residual {depth}, "
            f"unclosed {[(c, l) for c, l in stack][:4]}, mismatched {bad[:4]}")
    else:
        print(f"  ok    {WIN}: PowerShell braces and parens balance")


def check_vocabulary():
    texts = {f: open(f).read() for f in ALL_THREE}
    for word in REQUIRED:
        missing = [f for f, t in texts.items() if word not in t]
        if missing:
            problems.append(
                f"vocabulary: {word!r} is required by REPAIR-SPEC.md but "
                f"missing from {', '.join(missing)}")
    for word in FORBIDDEN:
        present = [f for f, t in texts.items() if word in t]
        if present:
            problems.append(
                f"vocabulary: {word!r} was replaced and must not come back - "
                f"still in {', '.join(present)}")
    if not problems:
        print(f"  ok    all three agree on {len(REQUIRED)} required "
              f"and {len(FORBIDDEN)} retired terms")


print("checking the installers")
ps = check_stub()
check_balance(ps)
check_vocabulary()

if problems:
    print("\nproblems:")
    for p in problems:
        print(f"  FAIL  {p}")
    sys.exit(1)
print("\nall good")

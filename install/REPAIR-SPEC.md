# Salvage installer repair system — implementation spec

One behaviour, three implementations. This file is the authority; if an installer
disagrees with this document, the installer is wrong.

Implementations:

| platform | file | language |
|---|---|---|
| macOS   | `launchers/Salvage-Setup-Mac.command` | bash + osascript dialogs |
| Windows | `launchers/Salvage-Setup-Windows.bat` | PowerShell-in-batch |
| Linux   | `install/salvage-setup.py`            | Python + tkinter |

`launchers/Salvage-Setup-Linux.sh` is only a bootstrap: it checks for python3 and
tkinter, then downloads `install/salvage-setup.py` from the `release` branch and runs
it. It needs no repair logic of its own.

---

## Non-negotiable safety rules

**Nothing is ever deleted.** Every repair action MOVES files to
`<instance>/minecraft/.salvage-quarantine/<YYYYMMDD-HHMMSS>/`, preserving the relative
path. A stale `packwiz.json` would otherwise make the tool eat good files, and a player
who loses a mod they added on purpose has no way back.

**These are never touched by any rung:**

    saves/            options.txt       servers.dat
    screenshots/      shaderpacks/      resourcepacks/
    config/*.txt keybind files          any file the player created
    .salvage-quarantine/                logs/  crash-reports/

That restraint is the entire reason to run this instead of reinstalling.

**No personal names in user-facing text.** The report is addressed to "your server
operator". These installers are meant to stand alone as a public project.

---

## Reading the instance

Prism instance roots:

| platform | path |
|---|---|
| macOS   | `~/Library/Application Support/PrismLauncher/instances` |
| Windows | `%APPDATA%\PrismLauncher\instances` |
| Linux   | `~/.local/share/PrismLauncher/instances`, and the Flatpak path `~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances` |

An instance belongs to this pack if `<instance>/minecraft/packwiz.json` exists, or if
`instance.cfg` contains our pack URL. Check every instance; players commonly have both a
stable and a dev copy.

## `packwiz.json` schema — verified against a live instance

    {
      "packFileHash":  { "type": "sha256", "value": "..." },   // of pack.toml
      "indexFileHash": { "type": "sha256", "value": "..." },   // of index.toml
      "cachedSide":    "client",
      "cachedFiles": { "<metafile path>": <entry>, ... }
    }

Entries come in **three shapes** and must be handled differently. Getting this wrong is
how a repair tool invents problems:

**1. A mod jar** — has `linkedFileHash`.

    "mods/towns-and-towers.pw.toml": {
      "hash":           { "type": "sha256", "value": "..." },   // the .pw.toml itself
      "linkedFileHash": { "type": "sha512", "value": "..." },   // the JAR
      "cachedLocation": "mods/Towns-and-Towers-1.12-Fabric+Forge.jar",
      "optionValue": true
    }

Verify the file at `cachedLocation` against **`linkedFileHash`**, using the algorithm in
its `type` field. Both sha512 and sha1 occur (104 and 55 respectively in a current
instance — the sha1 ones are the CurseForge-metadata mods). **Honour the declared type.**
Assuming sha512 for everything produces 55 false corruption reports.

**2. A direct file** — has `hash` and `cachedLocation`, no `linkedFileHash`.

    "config/ftbquests/quests/chapters/the_deep.snbt": {
      "hash": { "type": "sha256", "value": "..." },
      "cachedLocation": "config/ftbquests/quests/chapters/the_deep.snbt",
      "optionValue": true
    }

Verify against **`hash`**.

**3. A skipped side** — `onlyOtherSide: true`, no hash and no `cachedLocation`.

    "mods/spark.pw.toml": { "optionValue": true, "onlyOtherSide": true }

This is a `side = "server"` mod that the client correctly did not download. **Never
report these as missing.** Skip them entirely.

---

## Rung 0 — Diagnose (read-only, always offered first)

Writes a report, changes nothing. Every later rung runs this first and shows the result
before asking to proceed.

| check | method |
|---|---|
| **Orphans** | jars in `mods/` whose path is not any entry's `cachedLocation`. These entered by another route and packwiz-installer can never remove them — it only removes what it recorded. This is the real mechanism behind "a clean reinstall fixed it". |
| **Corruption** | for each entry with a `cachedLocation` that exists, hash it per shape 1/2 above and compare. |
| **Missing** | entries with a `cachedLocation` that does not exist on disk. Excludes `onlyOtherSide` entries. |
| **Stale tracking** | recompute sha256 of the live `pack.toml` / `index.toml` and compare to `packFileHash` / `indexFileHash`. **Load-bearing:** without it an unsynced instance reports zero problems, because its `packwiz.json` still lists everything it once had. |
| **Channel** | does the pre-launch command point at `main` or `release`? Players should be on `release`. |
| **Bootstrap** | `packwiz-installer-bootstrap.jar` present and larger than 10 KB. |
| **Java** | version the instance will actually use. The pack needs 17+ on the client. |
| **RAM** | allocated heap vs physical memory. |
| **Last crash** | the exception line and the top three stack frames from the newest file in `crash-reports/`. |

### Report

Written to the Desktop as `salvage-report-<YYYYMMDD-HHMMSS>.txt`, plain text.

**ASCII only.** No box-drawing characters, no bullets, no arrows. This file is opened in
Notepad and TextEdit and pasted into chat, and each of those mangles a different subset of
UTF-8. A rule is `=` or `-`; a separator inside a line is `|`.

**Fixed vocabulary.** All three implementations emit these exact words. They have drifted
before - macOS said `failed hash` where Windows and Python said `corrupt`, and the three
titles, tracking labels and section headings all differed - which made two reports of the
same problem look like two different problems.

| thing | the word |
|---|---|
| a jar in `mods/` that the pack does not track | `orphan` |
| a tracked file whose hash does not match | `failed hash` |
| a tracked file that is not on disk | `missing` |
| a tracked file whose hash algorithm we do not know | `not checked` |
| the pre-launch command points at `main` | `channel` |
| `packwiz.json` absent or behind the published pack | `tracking` |
| `packwiz-installer-bootstrap.jar` absent or too small | `updater` |
| the instance will run on Java below 17 | `java` |

**Layout.** Header block, then one block per instance, then what changed. Each instance
block opens with a status marker so the operator can see at a glance which copy is the
problem:

    ==============================================================
      SALVAGE  -  install report
    ==============================================================

      generated     2026-08-24 12:41:07
      ran           diagnose only
      system        macOS 15.6 arm64, 32768 MB memory
      copies found  1

    --------------------------------------------------------------
      [ OK ]  Salvage
    --------------------------------------------------------------

      path          /Users/nate/.../instances/Salvage
      pack          Salvage 1.4.0
      channel       release
      java          17.0.15 (Microsoft)
      memory        12288 MB allocated of 32768 MB
      updater       present
      tracking      up to date

      tracked 168  |  jars 168  |  orphans 0  |  failed hash 0  |  missing 0

      problems
        none

      last crash
        none recorded

    --------------------------------------------------------------
      what this run changed
    --------------------------------------------------------------

      nothing (diagnose only)

The marker is `[ OK ]` when the instance has no problems and `[ !! ]` when it has any.
Field labels are left-aligned in a 14-character column. Problem lines are indented four
spaces and prefixed with the vocabulary word padded to 12 characters, then the filename.

Ends with the two lines that tell the player what to do with it - see **Clipboard summary**.

### Clipboard summary

The report file is the wrong unit for the handoff. A player has to notice a `.txt` on their
Desktop, work out where to put it, and attach it; in practice that is where the loop dies.

So every run **also builds a short summary** and offers it behind a **Copy summary** button.

**The copy is never automatic.** Silently replacing whatever the player had on their clipboard
is the kind of thing that makes a tool feel untrustworthy - they may have been mid-copy of
something else, and nothing on screen said it happened. A silent clipboard write is also
indistinguishable from nothing having happened, so the one case it is meant to help - the
player who does not know what to do next - is the case it helps least. The button says what
it will do, and confirms when it has done it.

Rules:

- **Under 1800 characters.** It has to survive being pasted into a chat message intact. Cap
  each problem list at five entries and append `... and N more` when it is longer.
- **Same vocabulary as the report.** It is the report, abridged - never a second format.
- **No absolute paths.** The full file has them; a pasted summary should not carry the
  player's home directory into a group chat.
- **Never fatal.** If the clipboard is unavailable - no `pbcopy`, a headless session, a
  locked clipboard - the button reports that and the report file remains the handoff. A
  repair that has already moved files must never fail on a cosmetic step.
- **Always reachable.** The button appears as soon as a run has produced a summary, and stays
  available until the window closes. The player may want it after reading the report, not
  before.

Shape:

    Salvage check - 2026-08-24 12:41
    macOS 15.6 arm64, 32768 MB

    [!!] Salvage - release, pack 1.4.0
      orphans 2 | failed hash 1 | missing 0 | tracking stale
      orphan       veinmining-fabric-1.5.0+1.20.1.jar
      failed hash  create-fabric-6.0.8.1.jar
      crash  java.lang.NullPointerException
             at com.example.Foo.bar(Foo.java:42)

    ran: targeted repair, 3 file(s) quarantined
    full report on my Desktop: salvage-report-20260824-124107.txt

The closing dialog then reads:

> Send this to your server operator: salvage-report-20260824-124107.txt
> Or use Copy summary for a short version to paste into a chat.

---

## Rungs 1–3 — Repair, escalating

Offered as an escalating ladder. After each, the player is told:

> Launch the game now. If it still crashes, run this again and pick the next option.

**Rung 1 — Targeted.** Quarantine orphans and any file failing its hash. packwiz-installer
re-fetches the hash failures on next launch. Fixes manual drops, leftovers from removed
mods, and truncated downloads.

**Rung 2 — Resync.** Rung 1, then also quarantine `packwiz.json` itself, forcing a full
re-validation of every file on next launch. Fixes corrupt tracking state.

**Rung 3 — Full reset.** Quarantine all of `mods/` and `config/`, then let the installer
re-download. This is the scripted equivalent of the "clean reinstall" advice, except the
world and settings survive.

---

## Entry point

The existing "found an existing install" branch currently only backs up `instance.cfg`,
switches `main` → `release`, and re-checks the bootstrap jar. It never touches `mods/`.

That branch gains a choice:

    1. Switch to stable updates   (what it does today)
    2. Check this install for problems   (rung 0, then offer 1 → 2 → 3)

Rung 0 must also be reachable without an existing-install prompt, so a player can be
asked to "run it and send the report" at any time.

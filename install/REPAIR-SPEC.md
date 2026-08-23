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

Written to the Desktop as `salvage-report-<YYYYMMDD-HHMMSS>.txt`, plain text, and the
path is shown to the player so they can send it on. Contents, in order:

1. Pack name and version, instance path, channel (`main` / `release`)
2. OS, Java version, RAM allocated and physical
3. Counts: tracked files, jars on disk, orphans, corrupt, missing
4. Each problem found, one per line, with the filename
5. What the run changed — or `nothing (diagnose only)`
6. The newest crash exception, if any

Ends with: *"Send this file to your server operator."*

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

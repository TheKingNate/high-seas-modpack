# Salvage Launcher — spec

This file is the authority for the launcher shell. If an implementation disagrees with this
document, the implementation is wrong. [REPAIR-SPEC.md](REPAIR-SPEC.md) remains the authority
for everything the repair ladder does; nothing here changes any of it.

One implementation for macOS and Windows — a Tauri desktop app at `app/`, built from this
document. Linux stays on `install/salvage-setup.py`, which is not a third copy of this logic
but the one installer of the three that is already a readable program.

Until that app ships, the three existing installers remain the implementation and remain
governed by this file and by REPAIR-SPEC.md. See [BUILD-PLAN.md](BUILD-PLAN.md) for the
sequence.

---

## Why this replaces the wizard

The current shell is a three-step wizard: get Prism, create the instance, set up updates. It
assumes the reason someone opened it is *"I am installing Salvage for the first time"*.

That is true exactly once per player. Every subsequent run is because something is wrong, or
because they want to play — and a linear flow is in the way of both. Worse, the wizard has no
answer at all for the most common state, which is **everything is fine**.

So the shell becomes a **launcher**: one home screen that reports the state of the install,
with actions off it. Install stops being a mode the player is trapped in and becomes one
action among several, which runs and returns home.

It does not replace Prism. Players keep Prism and can keep launching from it. This is the
thing that knows about *Salvage* specifically — the right instance, the right server, whether
the copy is healthy, and how to fix it when it is not.

---

## Home

The only screen that opens on start. Everything else is reached from it and returns to it.

    Salvage                                        v1.4.0 · release
    ──────────────────────────────────────────────────────────────
      Prism Launcher      installed
      Salvage instance    ready · 168 files · up to date
      Java                17.0.15
    ──────────────────────────────────────────────────────────────
      [ Play ]
      Check for problems
      Repair…
      Advanced ▾

**Status rows.** Three, always in this order, always present. Each is one of `ok`, `attention`
or `missing`, encoded in form as well as words so state reads at a glance.

| row | ok | attention | missing |
|---|---|---|---|
| Prism Launcher | `installed` | — | `not installed` |
| Salvage instance | `ready · N files · up to date` | `ready · N files · N problems` | `not installed` |
| Java | the version | `17 or newer needed, found N` | `not found` |

The instance row is the diagnosis from rung 0, run read-only on start. It must not block the
window appearing: the row reads `checking…` until it resolves.

**The primary action changes with state**, and only one is ever primary:

| state | primary |
|---|---|
| instance ready | **Play** |
| instance missing | **Install Salvage** |
| Prism missing | **Install Salvage** (installs Prism first, as today) |
| instance has problems | **Play** — still. A broken install is not a reason to hide the button; the problems row says so, and Repair is one click away. |

---

## Play

    prismlauncher --launch Salvage --server <address>

Verified present in Prism 11.0.3: `--launch` takes an instance ID, and `--server` joins on
launch and is only valid alongside it. So one command puts a player in the world, and **nobody
ever types the server address**.

This is why it beats the two alternatives considered:

- Writing `minecraft/servers.dat` would put the server in the multiplayer list, but means
  hand-writing gzipped NBT in three languages, and risks clobbering a player's own entries.
- Setting `JoinServerOnLaunchAddress` in `instance.cfg` works, but is a persistent setting
  that then fights the player if they ever want to join something else.

`--server` is a per-launch argument. It carries no state and breaks nothing.

The address lives in one place with the rest of the constants, next to `PACK_URL`. Launch is
fire-and-forget: the launcher starts Prism and stops caring. It does not wait, watch, or wrap.

---

## Advanced

Where the debug surface goes, and the reason the log stops being glued to the bottom of every
screen. Not a log tail — a set of things an operator actually asks someone to do:

- **Copy summary** — the clipboard handoff, per REPAIR-SPEC.md. Never automatic.
- **Open the report** — the newest `salvage-report-*.txt`.
- **Open the instance folder** — Finder / Explorer / xdg-open.
- **Update channel** — which of `release` / `main` this copy points at, and a switch.
- **Re-download the updater** — the existing bootstrap-jar check.
- **Log** — the run log, collapsed by default.

---

## Self-update

The launcher updates itself. A fix currently reaches nobody unless every player re-downloads
by hand, which means in practice they are all running whatever they first installed.

**Tauri's updater plugin does this**, and its contract is not negotiable, so the mechanism is
its mechanism rather than one of our choosing:

- It requires a **manifest** — a small JSON document giving a semver `version`, per-platform
  download URLs, and a **minisign signature** of each artifact.
- It verifies that signature against a public key compiled into the app. An update that was
  not signed with our private key is refused. This is a stronger guarantee than the sha256
  comparison an earlier draft of this file specified, and it is why the manifest is worth it.
- On Windows the NSIS installer **force-exits the running app** to install. That cannot be
  made silent, so the behaviour has to be honest about it on both platforms rather than
  differing between them.

**The objection the earlier draft was protecting against still stands, and is answered.** The
worry was a second file that has to agree with the first — the same drift that put three
installers out of step with one document. The answer is that **CI generates the manifest from
the build outputs**, in the same job that produced them. It cannot disagree with the artifact
because it is derived from it. A hand-written manifest would reintroduce exactly the failure.

**What the player sees.** One quiet row on Home:

    Update available - v1.4.1              [ Update and restart ]

Nothing happens until they press it. No prompt on launch, no modal, no silent restart. Same on
both platforms.

**Never blocking.** Offline, a 404, a signature mismatch, a slow network: all mean carry on.
The update check runs after the window is up and must never delay Play. Someone with no
internet must still be able to launch the game.

**The private key is the single point of failure.** If it is lost, every installed copy becomes
permanently un-updatable and the only repair is a manual reinstall by every player — precisely
the situation this feature exists to prevent. It is backed up outside the CI secret store on
the day it is generated.

**Where updates come from.** GitHub Releases, not the portal. Routing fixes through a
self-hosted box means a tunnel outage is an outage of the ability to fix the app. The portal
controls *configuration*; GitHub carries *bytes*. If a bad version needs stopping, the config
endpoint's `minAppVersion` is the kill switch, and it fails safe.

## What does not change

- The whole repair ladder — rungs 0 to 3, the quarantine rule, every check.
- The report format and the fixed vocabulary in REPAIR-SPEC.md.
- Nothing is ever deleted.
- Play never depends on the portal. Configuration is cached; a failed fetch is a warning row,
  never a block. Today three installers work with no server dependency at all, and the moment
  the app requires a handshake to launch the game, a class of "I can't play" exists that never
  existed before.

## What does change

The old model — *one file per platform, downloaded once, double-clicked, no install step and
no new dependency* — does not survive, and pretending otherwise would leave this document
disagreeing with the thing it specifies:

- It is an installed application, not a script. macOS gets a signed and notarized `.app`;
  Windows gets an NSIS installer.
- It installs, so it can be uninstalled, and it appears in Add/Remove Programs.
- Linux is not included. `install/salvage-setup.py` remains the Linux installer.

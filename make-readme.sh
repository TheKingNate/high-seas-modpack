#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(grep '^version' pack.toml | sed 's/.*"\(.*\)".*/\1/')
MCV=$(grep '^minecraft' pack.toml | sed 's/.*"\(.*\)".*/\1/')
COUNT=$(ls -1 mods/*.pw.toml 2>/dev/null | wc -l | tr -d ' ')

{
cat <<HEAD
# Salvage

Minecraft $MCV Fabric modpack. v$VERSION, $COUNT mods.

Buildable, flyable ships from Valkyrien Skies and Clockwork,
plus Applied Energistics, Create, magic, and sixteen structure
mods.

## Install

Grab the file for your OS from
[Releases](../../releases/latest) and run it.

- **Windows** — \`Salvage-Setup-Windows.bat\`, double-click
- **macOS** — \`Salvage-Setup-Mac.command\`, right-click → Open the
  first time
- **Linux** — \`Salvage-Setup-Linux.sh\`

Installs Prism Launcher if needed, builds the instance, sets memory,
and turns on auto-updates. If you already have it installed, it
converts your setup instead and leaves your world and settings
alone.

## Server

\`setup-server.sh\` on the same release page installs a dedicated
server on Linux — Fabric, server-side mods, and start/update/backup
scripts.

## Mods

HEAD

for f in mods/*.pw.toml; do
    n=$(grep -m1 '^name' "$f" 2>/dev/null | sed 's/name = "\(.*\)"/\1/')
    [ -n "$n" ] && echo "- $n" || echo "- $(basename "$f" .pw.toml)"
done | sort -f
} > README.md

echo "wrote README.md ($COUNT mods)"

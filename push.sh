#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
packwiz refresh
packwiz modrinth export
packwiz curseforge export
git add -A
git commit -m "${1:-pack update}"
git push
echo "pushed - run ./update.sh on UbuntuCraft"

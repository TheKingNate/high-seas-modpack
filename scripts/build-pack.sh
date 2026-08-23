#!/usr/bin/env bash
# Builds the High Seas pack with packwiz, targeting CurseForge.
# Re-runnable: tops up an existing pack instead of re-initialising.

set -uo pipefail

PACK_NAME="High Seas"
MC_VERSION="1.20.1"

if ! command -v packwiz >/dev/null 2>&1; then
    cat >&2 <<'EOF'
packwiz not found in PATH:

    export PATH="$PATH:$HOME/go/bin"

Add that line to ~/.zshrc to make it stick.
EOF
    exit 1
fi

if [ -f pack.toml ]; then
    echo "Existing pack found -- topping up."
else
    if ! packwiz init \
        --name "$PACK_NAME" \
        --mc-version "$MC_VERSION" \
        --modloader fabric; then
        echo "packwiz init failed -- stopping." >&2
        exit 1
    fi
fi

mods=(
    fabric-api
    fabric-language-kotlin
    architectury-api
    balm
    selene
    yungs-api-fabric

    valkyrien-skies
    eureka-ships
    valkyrien-pirates
    supplementaries
    "Valkyrien Sails"
    "Valkyrien Relogs"
    "Valkyrien Skies 2 + Supplementaries Cannon Fix"

    lithostitched
    tectonic
    terralith
    structory
    yungs-better-ocean-monuments-fabric
    yungs-better-dungeons-fabric
    yungs-better-desert-temples-fabric
    explorers-compass
    waystones
    chunky-pregenerator

    naturalist
    bosses-of-mass-destruction
    sound-physics-remastered
    ambientsounds

    jade
    roughly-enough-items
    appleskin
    xaeros-minimap
    xaeros-world-map
    mouse-tweaks

    sodium
    indium
    irisshaders
    lithium
    modernfix
    krypton
    "Entity Culling"
    ImmediatelyFast
    "Enhanced Block Entities"
    noisium
    scalablelux

    "Immersive Storms"
    "Entity Model Features"
    "Entity Texture Features"
    "Particle Rain"
    polytone
    "Inventory Particles"
    "Shoulder Surfing Reloaded"
    "Better Advancements"
    "Mod Menu"
    "Distant Horizons"
)

: > missing.txt

for mod in "${mods[@]}"; do
    echo "==> $mod"
    if ! packwiz curseforge add "$mod"; then
        echo "$mod" >> missing.txt
    fi
done

packwiz refresh
packwiz curseforge export

echo
echo "Done. Unresolved:"
cat missing.txt

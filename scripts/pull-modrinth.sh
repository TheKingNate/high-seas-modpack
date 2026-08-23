#!/usr/bin/env bash
# Pulls Modrinth-only content into a CurseForge instance folder.
# Resolves the correct 1.20.1 / Fabric build via the Modrinth API.
#
#   brew install jq
#   ./pull-modrinth.sh                      # auto-detect instance
#   ./pull-modrinth.sh "/path/to/instance"  # or pass it explicitly
#
# Re-runnable: skips anything already present.

set -uo pipefail

MC="1.20.1"
LOADER="fabric"
API="https://api.modrinth.com/v2"

# Modrinth slugs. Add more here as you find them.
MODS=(
    vs-safe-and-sound
    vs-ship-in-a-bottle
    jade-vs
    ferrite-core
    euphoria-patches
    noisium
    scalablelux
    immersive-storms
    modmenu
    distanthorizons
)

SHADERS=(
    complementary-reimagined
)

RESOURCEPACKS=(
    fresh-animations
)

# --- locate the instance -------------------------------------------

find_instance() {
    local base
    for base in "$HOME/curseforge/minecraft/Instances" \
                "$HOME/Documents/curseforge/minecraft/Instances"; do
        [ -d "$base" ] || continue
        find "$base" -maxdepth 1 -mindepth 1 -type d
    done
}

INSTANCE="${1:-}"

if [ -z "$INSTANCE" ]; then
    mapfile -t found < <(find_instance) 2>/dev/null || {
        # bash 3.2 on macOS has no mapfile
        found=()
        while IFS= read -r line; do found+=("$line"); done \
            < <(find_instance)
    }
    if [ "${#found[@]}" -eq 1 ]; then
        INSTANCE="${found[0]}"
    elif [ "${#found[@]}" -gt 1 ]; then
        echo "Multiple instances found. Pass one explicitly:" >&2
        printf '  %s\n' "${found[@]}" >&2
        exit 1
    else
        echo "No CurseForge instance found." >&2
        echo "In the app: profile -> Open Folder, then pass that" >&2
        echo "path as the first argument." >&2
        exit 1
    fi
fi

if [ ! -d "$INSTANCE" ]; then
    echo "Not a directory: $INSTANCE" >&2
    exit 1
fi

command -v jq >/dev/null 2>&1 || {
    echo "jq not found. brew install jq" >&2
    exit 1
}

echo "Instance: $INSTANCE"
echo

# --- fetch helpers -------------------------------------------------

# resolve_slug <name> -- fall back to search when the slug 404s
resolve_slug() {
    local slug="$1"
    if curl -sf -o /dev/null "$API/project/$slug"; then
        echo "$slug"
        return 0
    fi
    curl -sf --get "$API/search" \
        --data-urlencode "query=${slug//-/ }" \
        --data-urlencode 'limit=1' \
        | jq -r '.hits[0].slug // empty'
}

# versions <slug> <filter_loader:yes|no>
versions() {
    local slug="$1" use_loader="$2"
    if [ "$use_loader" = yes ]; then
        curl -sf --get "$API/project/$slug/version" \
            --data-urlencode "loaders=[\"$LOADER\"]" \
            --data-urlencode "game_versions=[\"$MC\"]"
    else
        curl -sf --get "$API/project/$slug/version" \
            --data-urlencode "game_versions=[\"$MC\"]"
    fi
}

# grab <slug> <dest_dir> <filter_loader>
grab() {
    local slug="$1" dest="$2" use_loader="$3"
    local real json url fname

    real="$(resolve_slug "$slug")"
    if [ -z "$real" ]; then
        echo "  NOT FOUND: $slug"
        return 1
    fi

    json="$(versions "$real" "$use_loader")"
    url="$(echo "$json" \
        | jq -r '[.[]|select(.files|length>0)][0].files
                 | map(select(.primary))[0].url // empty')"
    fname="$(echo "$json" \
        | jq -r '[.[]|select(.files|length>0)][0].files
                 | map(select(.primary))[0].filename // empty')"

    if [ -z "$url" ]; then
        echo "  NO $MC/$LOADER BUILD: $real"
        return 1
    fi

    mkdir -p "$dest"
    if [ -f "$dest/$fname" ]; then
        echo "  have: $fname"
        return 0
    fi

    echo "  get:  $fname"
    curl -sfL -o "$dest/$fname" "$url" || {
        echo "  DOWNLOAD FAILED: $fname"
        rm -f "$dest/$fname"
        return 1
    }
}

# --- run -----------------------------------------------------------

echo "mods:"
for s in "${MODS[@]}"; do grab "$s" "$INSTANCE/mods" yes; done

echo
echo "shaderpacks:"
for s in "${SHADERS[@]}"; do grab "$s" "$INSTANCE/shaderpacks" no; done

echo
echo "resourcepacks:"
for s in "${RESOURCEPACKS[@]}"; do
    grab "$s" "$INSTANCE/resourcepacks" no
done

echo
echo "Done."

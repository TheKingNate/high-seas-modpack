#!/usr/bin/env bash
#
# Restore a world or a single player from the snapshots backup.sh takes.
#
#   ./rollback.sh list [player]
#   ./rollback.sh find <player>
#   ./rollback.sh peek <player> <stamp>
#   ./rollback.sh player <player> <stamp>
#   ./rollback.sh world <stamp>
#   ./rollback.sh undo
#
# Why this exists. On 2026-08-25 a player lost his inventory and the only tooling
# was tar and guesswork: extract a candidate backup, parse the NBT by hand, decide
# whether it was the right one, repeat. By the time the right snapshot was found the
# obvious move looked like rolling back the whole world -- five hours for four people
# to recover one person's items.
#
# So the two things this does that plain tar does not:
#
#   find   asks every snapshot "did this player have items here?" and prints the
#          answer, so you restore from the NEWEST snapshot that helps rather than
#          the oldest one you are sure about.
#   player restores one player and touches nothing else. Nobody else loses a minute.
#
# Every destructive action copies what it is about to overwrite into pre-rollback/
# first, so `undo` always exists.

set -uo pipefail
cd "$(dirname "$0")"

SRV="$HOME/Desktop/salvage/server"
DEST="$HOME/Desktop/salvage/backups"
SAFE="$DEST/pre-rollback"
PEEK="$(dirname "$0")/peek-player.py"

mkdir -p "$SAFE"

die()  { printf '\n  %s\n\n' "$*" >&2; exit 1; }
say()  { printf '  %s\n' "$*"; }
have_server() { systemctl list-unit-files 2>/dev/null | grep -q '^salvage.service'; }

# --- resolving a player name to the uuid the files are named after ------------

resolve_uuid() {   # resolve_uuid <name-or-uuid>  -> uuid on stdout
    local q="$1"
    case "$q" in
        ????????-????-????-????-????????????) printf '%s' "$q"; return 0 ;;
    esac
    local u
    u=$(python3 - "$SRV/usernamecache.json" "$q" <<'PY'
import json, sys
try: cache = json.load(open(sys.argv[1]))
except Exception: sys.exit(1)
want = sys.argv[2].lower()
for uuid, name in cache.items():
    if name.lower() == want:
        print(uuid); break
PY
)
    [ -n "$u" ] || die "No player called '$q' in usernamecache.json. Try the UUID."
    printf '%s' "$u"
}

name_of() {   # name_of <uuid>
    python3 - "$SRV/usernamecache.json" "$1" <<'PY'
import json, sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2], "?"))
except Exception: print("?")
PY
}

# --- snapshot lookup ---------------------------------------------------------

# Player snapshots are stamped to the second, world snapshots to the minute. Both
# are matched by prefix so a partial stamp is enough to name one.
player_archive() { ls -1 "$DEST/player/playerdata-$1"*.tar.gz 2>/dev/null | head -1; }
world_archive()  { ls -1 "$DEST/world-$1"*.tar.gz 2>/dev/null | head -1; }

stop_server() {
    have_server || return 0
    systemctl is-active --quiet salvage || return 0
    say "stopping the server..."
    sudo systemctl stop salvage || die "Could not stop the server. Run this with sudo available."
    say "stopped"
}

start_server() {
    have_server || return 0
    say "starting the server..."
    sudo systemctl start salvage && say "started" || say "WARNING: server did not start - check 'journalctl -u salvage'"
}

case "${1:-}" in

# ---------------------------------------------------------------- list --------
list)
    if [ "${2:-}" = player ]; then
        say "player snapshots, newest first:"
        ls -1t "$DEST/player"/playerdata-*.tar.gz 2>/dev/null | head -40 | while read -r f; do
            b=$(basename "$f"); s=${b#playerdata-}; s=${s%.tar.gz}
            printf '    %s   %s\n' "$s" "$(date -d "${s:0:8} ${s:9:2}:${s:11:2}:${s:13:2}" '+%a %H:%M:%S' 2>/dev/null)"
        done
        echo; say "$(ls -1 "$DEST/player"/playerdata-*.tar.gz 2>/dev/null | wc -l) total"
    else
        say "world snapshots, newest first:"
        ls -1t "$DEST"/world-*.tar.gz 2>/dev/null | head -40 | while read -r f; do
            b=$(basename "$f"); s=${b#world-}; s=${s%.tar.gz}
            printf '    %s   %-18s %s\n' "$s" \
                "$(date -d "${s:0:8} ${s:9:2}:${s:11:2}" '+%a %H:%M' 2>/dev/null)" \
                "$(du -h "$f" | cut -f1)"
        done
        echo; say "$(ls -1 "$DEST"/world-*.tar.gz 2>/dev/null | wc -l) total"
    fi
    ;;

# ---------------------------------------------------------------- find --------
# The command tonight needed. Walks snapshots newest-first and reports what the
# player was carrying in each, so you can see exactly where their stuff appears.
find)
    [ -n "${2:-}" ] || die "usage: ./rollback.sh find <player>"
    uuid=$(resolve_uuid "$2") || exit 1
    say "scanning player snapshots for $(name_of "$uuid") ($uuid), newest first"
    say "looking for the newest snapshot where they still had their items"
    echo
    n=0
    for f in $(ls -1t "$DEST/player"/playerdata-*.tar.gz 2>/dev/null); do
        n=$((n + 1)); [ "$n" -gt 60 ] && { say "... stopping at 60 snapshots"; break; }
        b=$(basename "$f"); s=${b#playerdata-}; s=${s%.tar.gz}
        tmp=$(mktemp -d)
        if tar -C "$tmp" -xzf "$f" "playerdata/$uuid.dat" 2>/dev/null; then
            printf '    %s  %s\n' "$s" "$(python3 "$PEEK" "$tmp/playerdata/$uuid.dat" --summary 2>/dev/null)"
        fi
        rm -rf "$tmp"
    done
    echo
    say "then: ./rollback.sh peek $2 <stamp>     to see the full inventory"
    say "      ./rollback.sh player $2 <stamp>   to restore it"
    ;;

# ---------------------------------------------------------------- peek --------
peek)
    [ -n "${3:-}" ] || die "usage: ./rollback.sh peek <player> <stamp>"
    uuid=$(resolve_uuid "$2") || exit 1
    f=$(player_archive "$3"); [ -n "$f" ] || die "No player snapshot matching '$3'. Try: ./rollback.sh list player"
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    tar -C "$tmp" -xzf "$f" "playerdata/$uuid.dat" 2>/dev/null \
        || die "$(name_of "$uuid") is not in $(basename "$f")"
    say "$(name_of "$uuid") in $(basename "$f"):"
    echo
    python3 "$PEEK" "$tmp/playerdata/$uuid.dat"
    ;;

# -------------------------------------------------------------- player --------
player)
    [ -n "${3:-}" ] || die "usage: ./rollback.sh player <player> <stamp>"
    uuid=$(resolve_uuid "$2") || exit 1
    f=$(player_archive "$3"); [ -n "$f" ] || die "No player snapshot matching '$3'. Try: ./rollback.sh list player"
    nm=$(name_of "$uuid")

    say "about to restore $nm from $(basename "$f")"
    echo
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    tar -C "$tmp" -xzf "$f" "playerdata/$uuid.dat" 2>/dev/null || die "$nm is not in that snapshot"
    say "the snapshot contains:"
    python3 "$PEEK" "$tmp/playerdata/$uuid.dat" | sed 's/^/  /'
    echo
    say "their CURRENT state:"
    python3 "$PEEK" "$SRV/world/playerdata/$uuid.dat" 2>/dev/null | sed 's/^/  /' || say "  (no current file)"
    echo
    printf '  This replaces %s'"'"'s inventory, position, XP and health. Nobody else is affected.\n' "$nm"
    read -r -p "  Type the player's name to confirm: " ok
    [ "$ok" = "$nm" ] || die "Not confirmed. Nothing changed."

    stop_server
    stamp=$(date +%Y%m%d-%H%M%S)
    mkdir -p "$SAFE/$stamp"
    cp -p "$SRV/world/playerdata/$uuid.dat" "$SAFE/$stamp/$uuid.dat" 2>/dev/null \
        && say "current state saved to pre-rollback/$stamp/"
    cp -p "$tmp/playerdata/$uuid.dat" "$SRV/world/playerdata/$uuid.dat" || die "Copy failed. Server is still stopped."
    rm -f "$SRV/world/playerdata/$uuid.dat_old"
    say "restored $nm"
    start_server
    echo
    say "undo with: ./rollback.sh undo"
    ;;

# --------------------------------------------------------------- world --------
world)
    [ -n "${2:-}" ] || die "usage: ./rollback.sh world <stamp>"
    f=$(world_archive "$2"); [ -n "$f" ] || die "No world snapshot matching '$2'. Try: ./rollback.sh list"

    echo
    say "FULL WORLD ROLLBACK from $(basename "$f")"
    say "Everything every player has done since then is lost - builds, inventories, villagers."
    say "If one player lost items, './rollback.sh player' costs nobody else anything."
    echo
    read -r -p "  Type ROLLBACK to confirm: " ok
    [ "$ok" = "ROLLBACK" ] || die "Not confirmed. Nothing changed."

    stop_server
    stamp=$(date +%Y%m%d-%H%M%S)
    say "moving the current world aside to pre-rollback/$stamp/world ..."
    mkdir -p "$SAFE/$stamp"
    mv "$SRV/world" "$SAFE/$stamp/world" || die "Could not move the current world. Server is stopped."
    say "extracting $(basename "$f") ..."
    if tar -C "$SRV" -xzf "$f"; then
        # The snapshots deliberately exclude the Distant Horizons LOD cache, so carry
        # the live one across rather than making every client re-scan the terrain.
        for p in data/DistantHorizons.sqlite DIM-1/data/DistantHorizons.sqlite DIM1/data/DistantHorizons.sqlite; do
            [ -f "$SAFE/$stamp/world/$p" ] && cp -p "$SAFE/$stamp/world/$p" "$SRV/world/$p" 2>/dev/null
        done
        say "restored, LOD cache carried over"
    else
        say "EXTRACT FAILED - putting the original world back"
        rm -rf "$SRV/world"; mv "$SAFE/$stamp/world" "$SRV/world"
        die "Rolled back the rollback. Nothing lost."
    fi
    start_server
    echo
    say "the previous world is at $SAFE/$stamp/world if you need anything out of it"
    ;;

# ---------------------------------------------------------------- undo --------
undo)
    last=$(ls -1t "$SAFE" 2>/dev/null | head -1)
    [ -n "$last" ] || die "Nothing to undo."
    say "most recent pre-rollback snapshot: $last"
    ls -la "$SAFE/$last" | sed 's/^/    /'
    echo
    if [ -d "$SAFE/$last/world" ]; then
        say "That is a FULL WORLD snapshot. Restore it with:"
        say "  ./rollback.sh stop && mv $SRV/world /tmp/ && mv $SAFE/$last/world $SRV/world"
        exit 0
    fi
    read -r -p "  Restore these player files? [y/N] " ok
    [ "$ok" = y ] || die "Nothing changed."
    stop_server
    for f in "$SAFE/$last"/*.dat; do
        [ -f "$f" ] || continue
        cp -p "$f" "$SRV/world/playerdata/" && say "restored $(basename "$f")"
    done
    start_server
    ;;

*)
    cat <<'USAGE'

  Salvage rollback

    ./rollback.sh list [player]        what snapshots exist
    ./rollback.sh find <player>        which snapshots still have their items
    ./rollback.sh peek <player> <stamp>   full inventory in one snapshot
    ./rollback.sh player <player> <stamp> restore one player, affects nobody else
    ./rollback.sh world <stamp>        restore the whole world
    ./rollback.sh undo                 put back whatever the last restore replaced

  A stamp is a prefix of a snapshot name, so 20260825-2309 is enough.

  Start with `find` - it tells you the newest snapshot that still has what they
  lost, so you roll back minutes instead of hours.

USAGE
    ;;
esac

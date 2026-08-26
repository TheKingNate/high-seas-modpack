#!/usr/bin/env bash
#
# Salvage server backups, two tiers.
#
#   world   -- everything the server owns, minus the Distant Horizons LOD cache
#   player  -- world/playerdata only, cheap enough to run every few minutes
#
# Why two tiers. On 2026-08-25 a player lost his inventory at about 22:30 and the
# newest backup was 18:00 -- five hours, because backups ran 6-hourly. The thing
# that was actually lost was 188 KB of playerdata. Snapshotting that alone costs
# nothing, so it runs often; the full world runs often enough to matter but not so
# often that it churns the disk.
#
# Why Distant Horizons is excluded. The two DistantHorizons.sqlite files are 3.3 GB
# and 1.4 GB, they are rewritten in full every hour, and together they were 94% of
# every backup taken. They are a level-of-detail render cache for distant terrain:
# regenerable, cosmetic, and worthless in a restore. Excluding them takes a snapshot
# from 5.4 GB to 349 MB, which is the entire reason this can now run every 20 minutes.
#
#   usage: backup.sh world|player
#
set -uo pipefail

SRV="$HOME/Desktop/salvage/server"
DEST="$HOME/Desktop/salvage/backups"
LOG="$DEST/backup.log"

KEEP_WORLD=144     # every 20 min -> 48 hours of history
KEEP_PLAYER=288     # every 5 min  -> 24 hours of history

mkdir -p "$DEST/player"

log() { printf '%s: %s\n' "$(date)" "$*" >> "$LOG"; }

# save-off is the dangerous state: if this script dies between save-off and save-on,
# the server stops persisting anything and nobody finds out until the next crash.
# The trap makes save-on unconditional.
saves_off=0
restore_saves() {
    if [ "$saves_off" = 1 ] && systemctl is-active --quiet salvage; then
        screen -S salvage -X stuff "save-on$(printf '\r')"
    fi
}
trap restore_saves EXIT

quiesce() {
    systemctl is-active --quiet salvage || return 0
    screen -S salvage -X stuff "save-off$(printf '\r')"
    saves_off=1
    screen -S salvage -X stuff "save-all flush$(printf '\r')"
    sleep 10
}

case "${1:-world}" in

  player)
    # No quiesce. playerdata is written on logout and on autosave; a torn read here
    # costs one snapshot out of 288, and holding saves off every 5 minutes would be
    # a far worse trade.
    STAMP=$(date +%Y%m%d-%H%M%S)
    tar -C "$SRV/world" -czf "$DEST/player/playerdata-$STAMP.tar.gz" playerdata 2>/dev/null \
        && log "player $(du -h "$DEST/player/playerdata-$STAMP.tar.gz" | cut -f1)" \
        || log "player FAILED"
    ls -1t "$DEST/player"/playerdata-*.tar.gz 2>/dev/null | tail -n +$((KEEP_PLAYER + 1)) | xargs -r rm -f
    ;;

  world)
    quiesce
    STAMP=$(date +%Y%m%d-%H%M)
    if tar -C "$SRV" \
           --exclude='world/data/DistantHorizons.sqlite*' \
           --exclude='world/*/data/DistantHorizons.sqlite*' \
           --exclude='world/**/DistantHorizons.sqlite*' \
           -czf "$DEST/world-$STAMP.tar.gz" world 2>/dev/null
    then
        log "world  $(du -h "$DEST/world-$STAMP.tar.gz" | cut -f1)"
    else
        log "world  FAILED"
        rm -f "$DEST/world-$STAMP.tar.gz"
    fi
    restore_saves; saves_off=0
    ls -1t "$DEST"/world-*.tar.gz 2>/dev/null | tail -n +$((KEEP_WORLD + 1)) | xargs -r rm -f
    ;;

  *)
    echo "usage: $0 world|player" >&2; exit 2 ;;
esac

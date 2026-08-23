#!/usr/bin/env bash
# Salvage dedicated server installer. Linux.
#
#   ./setup-server.sh [install-dir]     default: ~/salvage
set -uo pipefail

DIR="${1:-$HOME/salvage}"
MC="1.20.1"
PACK="https://raw.githubusercontent.com/TheKingNate/high-seas-modpack/release/pack.toml"
BOOT="https://github.com/packwiz/packwiz-installer-bootstrap/releases/latest/download/packwiz-installer-bootstrap.jar"
RAM="10G"

B=$'\033[1m'; R=$'\033[31m'; N=$'\033[0m'
say() { printf '\n%s== %s%s\n' "$B" "$1" "$N"; }
die() { printf '\n%s== Stopped%s\n\n%s\n\n' "$R" "$N" "$1" >&2; exit 1; }

say "checking java"
JV=$(java -version 2>&1 | head -1 | sed -E 's/.*version "([0-9]+).*/\1/')
case "$JV" in ''|*[!0-9]*) JV=0 ;; esac
[ "$JV" -ge 21 ] || die \
"Need Java 21 or newer (found ${JV:-none}).

  Ubuntu/Debian:  sudo apt install -y openjdk-21-jre-headless
  Fedora:         sudo dnf install -y java-21-openjdk-headless

Java 17 is not enough for this pack. The Footprint mod declares
mixin compatibilityLevel JAVA_21, so the server aborts during
mixin init on anything older."
java -version 2>&1 | head -1

say "installing to $DIR"
mkdir -p "$DIR" || die "Can't create $DIR"
cd "$DIR"

say "fabric server"
if [ ! -f fabric-server-launch.jar ]; then
    L=$(curl -sf "https://meta.fabricmc.net/v2/versions/loader/$MC" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['loader']['version'])") \
        || die "Couldn't reach the Fabric API. Check your connection."
    I=$(curl -sf "https://meta.fabricmc.net/v2/versions/installer" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['version'])")
    echo "  loader $L / installer $I"
    curl -sfL -o fabric-server-launch.jar \
        "https://meta.fabricmc.net/v2/versions/loader/$MC/$L/$I/server/jar" \
        || die "Fabric server download failed."
fi
ls -lh fabric-server-launch.jar

say "mods"
[ -f packwiz-installer-bootstrap.jar ] || curl -sfL -O "$BOOT" \
    || die "Couldn't download the updater from GitHub."
java -jar packwiz-installer-bootstrap.jar -g -s server "$PACK" \
    || die "Mod install failed. Re-run to retry."
echo "  $(ls mods/*.jar 2>/dev/null | wc -l) mods installed"

say "config"
echo "eula=true" > eula.txt
if [ ! -f server.properties ]; then
cat > server.properties <<'PROPS'
motd=Salvage
server-port=25565
online-mode=true
white-list=true
max-players=8
difficulty=normal
allow-flight=true
view-distance=8
simulation-distance=6
max-tick-time=-1
spawn-protection=0
sync-chunk-writes=false
PROPS
echo "  wrote server.properties (whitelist ON)"
fi

cat > start.sh <<START
#!/usr/bin/env bash
cd "\$(dirname "\$0")"
exec java -Xms$RAM -Xmx$RAM -XX:+UseG1GC -XX:+ParallelRefProcEnabled \\
  -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions \\
  -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 \\
  -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M \\
  -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 \\
  -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 \\
  -XX:G1MixedGCLiveThresholdPercent=90 \\
  -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 \\
  -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 \\
  -jar fabric-server-launch.jar nogui
START

cat > update.sh <<'UPD'
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
B=$(md5sum mods/*.jar 2>/dev/null | md5sum)
RUN=0; systemctl is-active --quiet salvage && RUN=1
java -jar packwiz-installer-bootstrap.jar -g -s server \
  https://raw.githubusercontent.com/TheKingNate/high-seas-modpack/release/pack.toml || exit 1
[ "$B" = "$(md5sum mods/*.jar 2>/dev/null | md5sum)" ] && { echo "no changes"; exit 0; }
[ "$RUN" -eq 1 ] && sudo systemctl restart salvage || sudo systemctl start salvage
echo "restarted"
UPD

cat > backup.sh <<'BAK'
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p backups
systemctl is-active --quiet salvage && {
  screen -S salvage -X stuff "save-off\n"
  screen -S salvage -X stuff "save-all flush\n"; sleep 10; }
tar -czf "backups/world-$(date +%Y%m%d-%H%M).tar.gz" world
systemctl is-active --quiet salvage && screen -S salvage -X stuff "save-on\n"
ls -1t backups/world-*.tar.gz | tail -n +15 | xargs -r rm --
BAK

cat > pending.sh <<'PEN'
#!/usr/bin/env bash
cd "$(dirname "$0")"
grep -h 'not white-listed' logs/latest.log logs/*.log.gz 2>/dev/null |
  grep -oP 'name=\K[A-Za-z0-9_]{3,16}' | sort -u
PEN

chmod +x start.sh update.sh backup.sh pending.sh

say "done"
cat <<DONE

  Server:  $DIR
  RAM:     $RAM   (edit start.sh to change)

  Run it under systemd:

    sudo tee /etc/systemd/system/salvage.service > /dev/null <<UNIT
    [Unit]
    Description=Salvage Minecraft server
    After=network-online.target
    [Service]
    Type=simple
    User=$USER
    WorkingDirectory=$DIR
    ExecStart=/usr/bin/screen -DmS salvage $DIR/start.sh
    Restart=on-failure
    RestartSec=15
    TimeoutStopSec=180
    [Install]
    WantedBy=multi-user.target
    UNIT

    sudo systemctl daemon-reload && sudo systemctl enable --now salvage
    screen -r salvage

  Ports:  25565/tcp  and  25565/udp (voice chat)
  Backups: add to cron -> 0 */6 * * * $DIR/backup.sh
  Whitelist is ON. Have people try to join, then ./pending.sh

DONE

#!/bin/bash
# Salvage Setup for macOS.
#
# Double-click to run. The FIRST time, right-click it and choose
# Open instead, so macOS allows it.
#
# Run with --check to go straight to checking an existing install for
# problems, without the install prompts.
#
# Uses only what ships with macOS -- no Python, no Homebrew.

REPO="TheKingNate/high-seas-modpack"
PACK_URL="https://raw.githubusercontent.com/$REPO/release/pack.toml"
OLD_URL="https://raw.githubusercontent.com/$REPO/main/pack.toml"
BOOTSTRAP="https://github.com/packwiz/packwiz-installer-bootstrap/releases/latest/download/packwiz-installer-bootstrap.jar"
INSTANCE="Salvage"
MC="1.20.1"
FABRIC="0.19.3"
TITLE="Salvage Setup"

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
DATA="$HOME/Library/Application Support/PrismLauncher"

BOLD=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; RED=$'\033[31m'
CYN=$'\033[36m'; OFF=$'\033[0m'

# --- terminal output ------------------------------------------------

banner() {
    clear
    printf '\n'
    printf '  %s====================================%s\n' "$CYN" "$OFF"
    printf '  %sSALVAGE%s  Minecraft modpack setup\n' "$BOLD" "$OFF"
    printf '  %s====================================%s\n\n' "$CYN" "$OFF"
}

step_header() {   # step_header 1 3 "Install Prism Launcher"
    printf '\n  %s[ Step %s of %s ]  %s%s\n' "$BOLD" "$1" "$2" "$3" "$OFF"
    printf '  %s------------------------------------%s\n' "$DIM" "$OFF"
}

info() { printf '  %s\n' "$1"; }
good() { printf '  %s%s%s\n' "$GRN" "$1" "$OFF"; }
bad()  { printf '  %s%s%s\n' "$RED" "$1" "$OFF"; }

focus_terminal() {
    osascript -e 'tell application "Terminal" to activate' >/dev/null 2>&1
}

spinner() {   # spinner <pid> "message"
    local pid=$1 msg=$2 i=0
    local frames='|/-\'
    while kill -0 "$pid" 2>/dev/null; do
        printf '\r  %s %s ' "${frames:i++%4:1}" "$msg"
        sleep 0.15
    done
    printf '\r  %s\r' "$(printf ' %.0s' {1..70})"
}

# --- dialogs --------------------------------------------------------

ask() {
    osascript -e "display dialog \"$1\" buttons {\"Quit\",\"Continue\"} \
default button \"Continue\" with title \"$TITLE\"" >/dev/null 2>&1 \
        || { banner; info "Cancelled. Nothing was changed."; printf '\n'; exit 0; }
}

note() {
    osascript -e "display dialog \"$1\" buttons {\"OK\"} \
default button \"OK\" with title \"$TITLE\"" >/dev/null 2>&1
}

oops() {
    bad "$1"
    printf '\n'
    info "$2"
    printf '\n'
    osascript -e "display dialog \"$1

$2

Nothing was broken. You can close this and try again.\" buttons {\"OK\"} \
default button \"OK\" with title \"$TITLE\" with icon stop" >/dev/null 2>&1
    exit 1
}

ram_mb()  { echo $(( $(sysctl -n hw.memsize) / 1048576 )); }
heap_mb() {
    local h=$(( $(ram_mb) / 2 ))
    [ "$h" -lt 4096 ]  && h=4096
    [ "$h" -gt 12288 ] && h=12288
    echo "$h"
}

find_instances() {
    [ -d "$DATA/instances" ] || return 0
    grep -l "$1" "$DATA"/instances/*/instance.cfg 2>/dev/null
}

# --- work -----------------------------------------------------------

install_prism() {
    local tmp="/tmp/prism.zip" url

    info "Asking GitHub for the latest version..."
    url=$(curl -fsSL \
        "https://api.github.com/repos/PrismLauncher/PrismLauncher/releases/latest" \
        | grep -o 'https://[^"]*macOS[^"]*\.zip' | grep -v Legacy | head -1)
    [ -n "$url" ] || url=$(curl -fsSL \
        "https://api.github.com/repos/PrismLauncher/PrismLauncher/releases/latest" \
        | grep -o 'https://[^"]*macOS[^"]*\.zip' | head -1)
    [ -n "$url" ] || oops "Couldn't find the Prism Launcher download." \
        "Install it yourself from prismlauncher.org, open it once, then run this again."

    good "Found it."
    printf '\n'
    info "Downloading Prism Launcher:"
    printf '\n'
    curl -# -fL -o "$tmp" "$url" \
        || oops "The Prism Launcher download failed." \
                "Check your internet connection and try again."
    printf '\n'
    good "Downloaded $(du -h "$tmp" | cut -f1)."

    rm -rf /tmp/prismx && mkdir -p /tmp/prismx
    ( unzip -qo "$tmp" -d /tmp/prismx ) & spinner $! "Unzipping..."
    wait $!

    local app
    app=$(find /tmp/prismx -maxdepth 2 -name "*.app" | head -1)
    [ -n "$app" ] || oops "The download didn't contain the app." \
        "Install Prism yourself from prismlauncher.org."

    rm -rf "/Applications/$(basename "$app")"
    ( cp -R "$app" /Applications/ ) & spinner $! "Moving it to Applications..."
    wait $!
    [ -d "/Applications/$(basename "$app")" ] || oops \
        "Couldn't move Prism Launcher into Applications." \
        "You may need to drag it there yourself from /tmp/prismx."

    xattr -dr com.apple.quarantine "/Applications/$(basename "$app")" 2>/dev/null
    rm -f "$tmp"
    mkdir -p "$DATA"
    good "Installed to /Applications."
}

make_instance() {
    local inst="$DATA/instances/$INSTANCE" mcdir
    mcdir="$inst/minecraft"

    info "Creating folder..."
    mkdir -p "$mcdir" || oops "Couldn't create $mcdir" \
        "Check you have space and permission in your home folder."
    good "Folder ready."

    info "Setting Minecraft $MC with Fabric $FABRIC..."
    cat > "$inst/mmc-pack.json" <<JSON
{
    "components": [
        { "important": true, "uid": "net.minecraft", "version": "$MC" },
        { "uid": "net.fabricmc.fabric-loader", "version": "$FABRIC" }
    ],
    "formatVersion": 1
}
JSON
    good "Version set."

    local h; h=$(heap_mb)
    info "Allocating ${h} MB of memory (you have $(ram_mb) MB)..."

    local cfg="$inst/instance.cfg" keep="/tmp/salvage-cfg.$$"
    if [ -f "$cfg" ]; then
        grep -v -E '^(InstanceType|name|OverrideCommands|PreLaunchCommand|OverrideMemory|MinMemAlloc|MaxMemAlloc)=' \
            "$cfg" > "$keep" 2>/dev/null || : > "$keep"
    else
        : > "$keep"
    fi

    cat >> "$keep" <<CFG
InstanceType=OneSix
name=$INSTANCE
OverrideCommands=true
PreLaunchCommand=\"\$INST_JAVA\" -jar \"\$INST_MC_DIR/packwiz-installer-bootstrap.jar\" -g -s client $PACK_URL
OverrideMemory=true
MinMemAlloc=4096
MaxMemAlloc=$h
CFG
    mv "$keep" "$cfg"
    good "Instance configured."
}

get_bootstrap() {
    local mcdir="$1" jar
    jar="$mcdir/packwiz-installer-bootstrap.jar"
    if [ -f "$jar" ] && [ "$(wc -c < "$jar")" -gt 10000 ]; then
        good "Updater already present."
        return 0
    fi
    mkdir -p "$mcdir"
    info "Downloading the updater:"
    printf '\n'
    curl -# -fL -o "$jar" "$BOOTSTRAP" \
        || oops "Couldn't download the updater from GitHub." \
                "Check your internet connection and try again."
    printf '\n'
    [ "$(wc -c < "$jar")" -gt 10000 ] \
        || oops "The updater downloaded but looks damaged." \
                "Your network may be interfering. Try a different connection."
    good "Updater ready ($(wc -c < "$jar" | tr -d ' ') bytes)."
}

# --- repair ---------------------------------------------------------
#
# Additive. The fresh-install and switch-to-stable flows use none of this.
#
# One rule holds throughout: nothing is ever deleted. Every action MOVES a
# file into minecraft/.salvage-quarantine/<timestamp>/ keeping its relative
# path. packwiz.json can be out of date, and a player may have added a mod
# on purpose, so every guess this tool makes has to be undoable in Finder.

QUAR=".salvage-quarantine"
WORK=""       # scratch dir, made on first use
STAMP=""      # one timestamp per run; report and quarantine folder share it
REPORT=""
CHANGED=""    # file the current instance's moves are logged to

# Bash has no records, so diagnose_instance fills these in and the report
# and dialog steps read them back.
D_NAME=""; D_PACK=""; D_CHANNEL=""; D_JAVA=""; D_HEAP=""; D_BOOT=""; D_SYNC=""
D_PACKHASH=""; D_PACKHASH_TYPE=""; D_INDEXHASH=""; D_INDEXHASH_TYPE=""
D_TRACKED=0; D_SERVER=0; D_JARS=0
D_ORPHAN=0; D_CORRUPT=0; D_MISSING=0

work_dir() {
    [ -n "$WORK" ] && return 0
    STAMP=$(date +%Y%m%d-%H%M%S)
    WORK=$(mktemp -d /tmp/salvage-check.XXXXXX) \
        || oops "Couldn't create a temporary folder." \
                "Your startup disk may be full."
    trap 'rm -rf "$WORK"' EXIT

    # packwiz.json is 60 KB of JSON and bash has no JSON parser. python3 is
    # not a safe bet here: on a Mac without the Xcode command line tools
    # /usr/bin/python3 is a stub that pops an install dialog instead of
    # running. JavaScript for Automation has shipped inside osascript since
    # OS X 10.10, needs no automation permission for a Foundation-only
    # script, and has a real JSON parser -- so the reading happens there and
    # comes back as tab-separated lines that bash can loop over.
    cat > "$WORK/read.js" <<'JS'
ObjC.import('Foundation');

function run(argv) {
    var src = argv[0], out = argv[1];
    var raw = $.NSString.stringWithContentsOfFileEncodingError(
                  $(src), $.NSUTF8StringEncoding, null);
    var txt = ObjC.unwrap(raw);
    if (txt === null || txt === undefined) { return 'ERR'; }
    var d;
    try { d = JSON.parse(txt); } catch (e) { return 'ERR'; }

    function pair(o) {
        if (o && o.type && o.value) { return [String(o.type), String(o.value)]; }
        return null;
    }

    var L = [], p = pair(d.packFileHash), i = pair(d.indexFileHash);
    if (p) { L.push(['P', p[0], p[1]].join('\t')); }
    if (i) { L.push(['I', i[0], i[1]].join('\t')); }
    if (d.cachedSide) { L.push(['S', String(d.cachedSide)].join('\t')); }

    // Three entry shapes, and they are not interchangeable:
    //   onlyOtherSide   a server-side mod this client correctly skipped
    //   linkedFileHash  a jar; the hash to check is the LINKED one
    //   hash only       a plain file; the hash to check is its own
    var cf = d.cachedFiles || {};
    Object.keys(cf).forEach(function (k) {
        var e = cf[k] || {};
        if (e.onlyOtherSide) { L.push(['X', k].join('\t')); return; }
        if (!e.cachedLocation) { L.push(['U', k].join('\t')); return; }
        var h = pair(e.linkedFileHash) || pair(e.hash);
        L.push(['F', h ? h[0] : '-', h ? h[1] : '-',
                String(e.cachedLocation), k].join('\t'));
    });

    var ok = $(L.join('\n') + '\n').writeToFileAtomicallyEncodingError(
                 $(out), true, $.NSUTF8StringEncoding, null);
    return ok ? 'OK' : 'ERR';
}
JS
}

read_entries() {   # read_entries <packwiz.json> <output tsv>
    [ "$(osascript -l JavaScript "$WORK/read.js" "$1" "$2" 2>/dev/null)" = "OK" ]
}

hash_file() {   # hash_file <type> <file>
    # Honour the declared type. A real packwiz.json mixes sha512 and sha1 in
    # the same file; assuming sha512 throughout invents dozens of failures.
    case "$1" in
        sha512) shasum -a 512 "$2" 2>/dev/null ;;
        sha256) shasum -a 256 "$2" 2>/dev/null ;;
        sha1)   shasum -a 1   "$2" 2>/dev/null ;;
        md5)    md5 -q "$2" 2>/dev/null ;;
        *)      : ;;
    esac | cut -d' ' -f1 | tr 'A-F' 'a-f'
}

lower() { printf '%s' "$1" | tr 'A-F' 'a-f'; }

verify_hashes() {   # verify_hashes <mcdir> <shasum -a arg> <list> <failures out>
    # <list> holds "expected<TAB>relative path" lines for files known to
    # exist. One shasum invocation per algorithm rather than one per file:
    # 150 jars take well under a second that way.
    local mcdir="$1" algo="$2" list="$3" out="$4"
    [ -s "$list" ] || return 0
    ( cd "$mcdir" && cut -f2 "$list" | tr '\n' '\0' \
        | xargs -0 shasum -a "$algo" 2>/dev/null ) > "$list.actual"
    awk -F'\t' '
        NR == FNR { want[$2] = tolower($1); next }
        { i = index($0, "  "); if (i == 0) next
          got = tolower(substr($0, 1, i - 1)); p = substr($0, i + 2)
          seen[p] = 1
          if (p in want && want[p] != got) print p }
        END { for (p in want) if (!(p in seen)) print p }
    ' "$list" "$list.actual" >> "$out"
}

find_pack_instances() {
    # An instance is ours if its config points at our pack URL or if it has a
    # packwiz.json. Players commonly keep both a stable and a dev copy.
    [ -d "$DATA/instances" ] || return 0
    {
        { find_instances "$OLD_URL"; find_instances "$PACK_URL"; } \
            | while IFS= read -r cfg; do
                  [ -n "$cfg" ] && dirname "$cfg"
              done
        local d
        for d in "$DATA"/instances/*/; do
            [ -f "${d}minecraft/packwiz.json" ] && printf '%s\n' "${d%/}"
        done
    } | LC_ALL=C sort -u
    return 0
}

instance_url() {
    grep -o 'https://[^ "]*pack\.toml' "$1/instance.cfg" 2>/dev/null | head -1
}

instance_java() {   # the version the instance will actually use
    local cfg="$1/instance.cfg" v p
    v=$(sed -n 's/^JavaVersion=//p' "$cfg" 2>/dev/null | head -1)
    if [ -z "$v" ]; then
        p=$(sed -n 's/^JavaPath=//p' "$cfg" 2>/dev/null | head -1)
        [ -x "$p" ] || p=$(command -v java)
        [ -n "$p" ] && v=$("$p" -version 2>&1 | head -1 | sed 's/.*"\(.*\)".*/\1/')
    fi
    printf '%s' "${v:-unknown}"
}

instance_heap() {
    local cfg="$1/instance.cfg" v=""
    grep -q '^OverrideMemory=true' "$cfg" 2>/dev/null \
        && v=$(sed -n 's/^MaxMemAlloc=//p' "$cfg" 2>/dev/null | head -1)
    [ -n "$v" ] || v=$(sed -n 's/^MaxMemAlloc=//p' \
        "$DATA/prismlauncher.cfg" 2>/dev/null | head -1)
    printf '%s' "$v"
}

# --- rung 0: diagnose, read-only -------------------------------------

diagnose_instance() {   # diagnose_instance <instance dir> <scratch dir>
    local inst="$1" s="$2" mcdir="$1/minecraft"
    local kind a b loc key url ifile live want pname pver size

    mkdir -p "$s"
    : > "$s/orphan.txt"; : > "$s/corrupt.txt"; : > "$s/missing.txt"
    : > "$s/note.txt";   : > "$s/changed.txt"; : > "$s/loc.txt"
    : > "$s/h.sha512";   : > "$s/h.sha256";    : > "$s/h.sha1"; : > "$s/h.md5"

    D_NAME=$(basename "$inst")
    D_PACK="unknown"; D_SYNC="unknown"
    D_PACKHASH=""; D_PACKHASH_TYPE=""; D_INDEXHASH=""; D_INDEXHASH_TYPE=""
    D_TRACKED=0; D_SERVER=0; D_JARS=0
    D_ORPHAN=0; D_CORRUPT=0; D_MISSING=0

    url=$(instance_url "$inst")
    case "$url" in
        */release/*) D_CHANNEL="release" ;;
        */main/*)    D_CHANNEL="main" ;;
        *)           D_CHANNEL="unknown" ;;
    esac
    D_JAVA=$(instance_java "$inst")
    D_HEAP=$(instance_heap "$inst")

    # Counted even when there is no packwiz.json to compare against, because
    # "145 jars and no tracking file" is itself the useful line in a report.
    ( cd "$mcdir" && find mods -type f -name '*.jar' 2>/dev/null ) \
        | LC_ALL=C sort > "$s/jars.txt"
    D_JARS=$(wc -l < "$s/jars.txt" | tr -d ' ')

    if [ -f "$mcdir/packwiz-installer-bootstrap.jar" ]; then
        size=$(wc -c < "$mcdir/packwiz-installer-bootstrap.jar" | tr -d ' ')
        if [ "$size" -gt 10000 ]; then
            D_BOOT="present ($size bytes)"
        else
            D_BOOT="damaged ($size bytes, too small to be the real updater)"
        fi
    else
        D_BOOT="missing"
    fi

    if [ ! -f "$mcdir/packwiz.json" ]; then
        printf 'no packwiz.json: this copy has never finished an update run\n' \
            >> "$s/note.txt"
    elif ! read_entries "$mcdir/packwiz.json" "$s/entries.tsv"; then
        printf 'packwiz.json could not be read: the update tracking file is damaged\n' \
            >> "$s/note.txt"
    else
        while IFS=$'\t' read -r kind a b loc key; do
            case "$kind" in
            P) D_PACKHASH_TYPE="$a"; D_PACKHASH="$b" ;;
            I) D_INDEXHASH_TYPE="$a"; D_INDEXHASH="$b" ;;
            S) : ;;
            X) D_SERVER=$((D_SERVER + 1)) ;;   # server-side: never missing here
            U) printf 'entry with no file recorded: %s\n' "$a" >> "$s/note.txt" ;;
            F)
                D_TRACKED=$((D_TRACKED + 1))
                printf '%s\n' "$loc" >> "$s/loc.txt"
                if [ ! -e "$mcdir/$loc" ]; then
                    # Prism disables a mod by renaming it, so a missing jar
                    # with a .disabled twin is the player's doing, not damage.
                    [ -e "$mcdir/$loc.disabled" ] && continue
                    printf '%s\n' "$loc" >> "$s/missing.txt"
                    continue
                fi
                case "$a" in
                sha512|sha256|sha1|md5)
                    printf '%s\t%s\n' "$b" "$loc" >> "$s/h.$a" ;;
                *)
                    printf 'no usable hash recorded for %s\n' "$loc" \
                        >> "$s/note.txt" ;;
                esac ;;
            esac
        done < "$s/entries.tsv"

        verify_hashes "$mcdir" 512 "$s/h.sha512" "$s/corrupt.txt"
        verify_hashes "$mcdir" 256 "$s/h.sha256" "$s/corrupt.txt"
        verify_hashes "$mcdir" 1   "$s/h.sha1"   "$s/corrupt.txt"
        while IFS=$'\t' read -r want loc; do
            [ -n "$loc" ] || continue
            [ "$(hash_file md5 "$mcdir/$loc")" = "$(lower "$want")" ] \
                || printf '%s\n' "$loc" >> "$s/corrupt.txt"
        done < "$s/h.md5"

        # Orphans: jars in mods/ that no entry claims. packwiz-installer only
        # removes what it recorded, so these survive every update. This is the
        # real mechanism behind "a clean reinstall fixed it". Only meaningful
        # with a readable packwiz.json -- without one, everything would look
        # like an orphan.
        LC_ALL=C sort -u "$s/loc.txt" > "$s/loc.sorted"
        LC_ALL=C comm -23 "$s/jars.txt" "$s/loc.sorted" > "$s/orphan.txt"

        # Stale tracking. Load-bearing: without it a copy that never synced
        # reports zero problems, because its packwiz.json still lists
        # everything it once had.
        if [ -n "$url" ] && curl -fsSL --max-time 20 -o "$s/pack.toml" "$url" 2>/dev/null
        then
            pname=$(sed -n 's/^name *= *"\(.*\)"/\1/p' "$s/pack.toml" | head -1)
            pver=$(sed -n 's/^version *= *"\(.*\)"/\1/p' "$s/pack.toml" | head -1)
            D_PACK="${pname:-Salvage} ${pver:-unknown version}"

            D_SYNC="current"
            live=$(hash_file "${D_PACKHASH_TYPE:-sha256}" "$s/pack.toml")
            if [ -z "$live" ] || [ -z "$D_PACKHASH" ]; then
                D_SYNC="unknown"
            elif [ "$live" != "$(lower "$D_PACKHASH")" ]; then
                D_SYNC="stale"
            fi

            ifile=$(sed -n 's/^file *= *"\(.*\)"/\1/p' "$s/pack.toml" | head -1)
            if curl -fsSL --max-time 20 -o "$s/index.toml" \
                    "${url%/*}/${ifile:-index.toml}" 2>/dev/null; then
                live=$(hash_file "${D_INDEXHASH_TYPE:-sha256}" "$s/index.toml")
                if [ -n "$live" ] && [ -n "$D_INDEXHASH" ] \
                    && [ "$live" != "$(lower "$D_INDEXHASH")" ]; then
                    D_SYNC="stale"
                fi
            elif [ "$D_SYNC" = "current" ]; then
                D_SYNC="unknown"
            fi
        else
            printf 'could not reach GitHub, so the update tracking was not checked\n' \
                >> "$s/note.txt"
        fi
    fi

    D_ORPHAN=$(wc -l < "$s/orphan.txt" | tr -d ' ')
    D_CORRUPT=$(wc -l < "$s/corrupt.txt" | tr -d ' ')
    D_MISSING=$(wc -l < "$s/missing.txt" | tr -d ' ')
}

crash_lines() {   # crash_lines <mcdir> -- the exception line and three frames
    local newest
    newest=$(ls -t "$1/crash-reports"/*.txt 2>/dev/null | head -1)
    [ -n "$newest" ] || return 0
    printf '\n  Last crash (%s)\n' "$(basename "$newest")"
    awk -v n=-1 '
        /^Description:/ && !desc { print "    " $0; desc = 1; next }
        n < 0 && $0 !~ /^[ \t]/ && ($0 ~ /Exception/ || $0 ~ /Error/) {
            print "    " $0; n = 0; next }
        n >= 0 && n < 3 && $0 ~ /^[ \t]*at / {
            sub(/^[ \t]*/, ""); print "      " $0; n++ }
    ' "$newest"
}

append_report() {   # append_report <instance dir> <scratch dir>  -- to stdout
    local inst="$1" s="$2"

    printf '\nInstance: %s\n' "$D_NAME"
    printf '  path:              %s\n' "$inst"
    printf '  pack:              %s\n' "$D_PACK"
    printf '  channel:           %s\n' "$D_CHANNEL"
    [ "$D_CHANNEL" = "main" ] && printf '%s\n' \
        "                     (should be release; main is the untested channel)"
    printf '  java:              %s\n' "$D_JAVA"
    if [ -n "$D_HEAP" ]; then
        printf '  memory allocated:  %s MB of %s MB physical\n' "$D_HEAP" "$(ram_mb)"
    else
        printf '  memory allocated:  launcher default, of %s MB physical\n' "$(ram_mb)"
    fi
    printf '  updater jar:       %s\n' "$D_BOOT"
    printf '  update tracking:   %s\n' "$D_SYNC"
    printf '  tracked files:     %s (plus %s server-side, not expected here)\n' \
        "$D_TRACKED" "$D_SERVER"
    printf '  jars in mods:      %s\n' "$D_JARS"
    printf '  orphans:           %s\n' "$D_ORPHAN"
    printf '  failed hash:       %s\n' "$D_CORRUPT"
    printf '  missing:           %s\n' "$D_MISSING"

    if [ -s "$s/orphan.txt" ] || [ -s "$s/corrupt.txt" ] || [ -s "$s/missing.txt" ]
    then
        printf '\n  Problems found\n'
        sed 's/^/    orphan        /' "$s/orphan.txt"
        sed 's/^/    failed hash   /' "$s/corrupt.txt"
        sed 's/^/    missing       /' "$s/missing.txt"
    elif [ "$D_TRACKED" -eq 0 ]; then
        printf '\n  No file check was possible. See Notes below.\n'
    else
        printf '\n  No file problems found.\n'
    fi

    if [ -s "$s/note.txt" ]; then
        printf '\n  Notes\n'
        sed 's/^/    /' "$s/note.txt"
    fi

    crash_lines "$inst/minecraft"
    return 0
}

publish_report() {
    {
        cat "$WORK/report.txt"
        printf '\nWhat this run changed\n'
        if [ -s "$WORK/changed.txt" ]; then
            sed 's/^/  /' "$WORK/changed.txt"
            printf '\n  Nothing was deleted. Everything above was moved into\n'
            printf '  minecraft/%s/%s/ inside that copy.\n' "$QUAR" "$STAMP"
        else
            printf '  nothing (diagnose only)\n'
        fi
        printf '\nSend this file to your server operator.\n'
    } > "$REPORT" 2>/dev/null
}

# --- rungs 1-3: repair ------------------------------------------------

quarantine() {   # quarantine <mcdir> <relative path>
    local mcdir="$1" rel="$2" dest
    [ -n "$rel" ] || return 0
    [ -e "$mcdir/$rel" ] || return 0
    # The player's own folders are off limits to every rung, even when
    # packwiz happens to track a file inside one. That restraint is the whole
    # reason to run this instead of reinstalling. The .. guard is paranoia
    # about a hand-edited packwiz.json pointing outside the instance.
    case "$rel" in
        *..*|"$QUAR"|"$QUAR"/*|saves|saves/*|screenshots|screenshots/*|\
        shaderpacks|shaderpacks/*|resourcepacks|resourcepacks/*|\
        logs|logs/*|crash-reports|crash-reports/*|\
        options.txt|servers.dat|config/*.txt)
            printf 'left alone, yours not the pack: %s\n' "$rel" >> "$CHANGED"
            return 0 ;;
    esac
    dest="$mcdir/$QUAR/$STAMP/$rel"
    mkdir -p "$(dirname "$dest")" 2>/dev/null || return 1
    if mv "$mcdir/$rel" "$dest" 2>/dev/null; then
        printf 'moved aside: %s\n' "$rel" >> "$CHANGED"
    else
        printf 'could not move: %s\n' "$rel" >> "$CHANGED"
    fi
    return 0
}

run_rung() {   # run_rung <instance dir> <scratch dir> <1|2|3>
    local inst="$1" s="$2" rung="$3" mcdir="$1/minecraft" rel
    CHANGED="$s/changed.txt"
    : > "$CHANGED"

    # Every rung begins with the targeted work, so the ladder only ever adds.
    while IFS= read -r rel; do quarantine "$mcdir" "$rel"; done < "$s/orphan.txt"
    while IFS= read -r rel; do quarantine "$mcdir" "$rel"; done < "$s/corrupt.txt"

    if [ "$rung" -ge 3 ]; then
        # Child by child, not the whole folder: the targeted step above may
        # already have created mods/ inside the quarantine, and moving a
        # folder onto an existing one nests it instead of merging.
        ( cd "$mcdir" && find mods config -mindepth 1 -maxdepth 1 2>/dev/null ) \
            > "$s/wipe.txt"
        while IFS= read -r rel; do quarantine "$mcdir" "$rel"; done < "$s/wipe.txt"
        mkdir -p "$mcdir/mods" "$mcdir/config"
    fi

    if [ "$rung" -ge 2 ]; then
        # Last, so the lists above were built while it was still in place.
        # Rung 3 needs this too: without it packwiz.json would still claim
        # every file had been fetched, and the copy would come back with no
        # mods at all.
        quarantine "$mcdir" "packwiz.json"
    fi

    if [ -s "$CHANGED" ]; then
        printf '\n%s\n' "$D_NAME" >> "$WORK/changed.txt"
        sed 's/^/  /' "$CHANGED" >> "$WORK/changed.txt"
    fi
    return 0
}

# --- the check flow ---------------------------------------------------

pick() {   # pick <prompt> <item>...  -- echoes the chosen item, or nothing
    local prompt="$1" list="" first="" item
    shift
    for item in "$@"; do
        item=$(printf '%s' "$item" | sed 's/\\/\\\\/g; s/"/\\"/g')
        [ -n "$first" ] || first="$item"
        list="$list, \"$item\""
    done
    osascript -e "choose from list {${list#, }} with title \"$TITLE\" \
with prompt \"$prompt\" default items {\"$first\"} \
OK button name \"Continue\" cancel button name \"Cancel\"" 2>/dev/null \
        | grep -v '^false$'
}

stop_here() {   # nothing was changed; the report still stands
    focus_terminal
    printf '\n'
    info "Stopped. Nothing was changed."
    info "The report is at: $REPORT"
    printf '\n'
    exit 0
}

check_flow() {
    local list count i inst item s chosen rung
    local sum_orphan=0 sum_corrupt=0 sum_missing=0 sum_stale=0

    banner
    info "Checking your Salvage install for problems."
    info "This only reads files. Nothing changes until you say so."
    printf '\n'

    list=$(find_pack_instances)
    [ -n "$list" ] || oops "Couldn't find a Salvage install to check." \
        "Run this installer with no options first to create one."

    work_dir
    REPORT="$HOME/Desktop/salvage-report-$STAMP.txt"
    [ -d "$HOME/Desktop" ] || REPORT="$HOME/salvage-report-$STAMP.txt"
    : > "$WORK/changed.txt"
    : > "$WORK/instances.txt"
    count=$(printf '%s\n' "$list" | wc -l | tr -d ' ')

    {
        printf 'Salvage repair report\n'
        printf 'generated:  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf 'tool:       Salvage Setup for macOS\n'
        printf '\nSystem\n'
        printf '  macOS:            %s (%s)\n' \
            "$(sw_vers -productVersion 2>/dev/null)" "$(uname -m)"
        printf '  physical memory:  %s MB\n' "$(ram_mb)"
        printf '  copies found:     %s\n' "$count"
    } > "$WORK/report.txt"

    i=0
    while IFS= read -r inst; do
        [ -n "$inst" ] || continue
        i=$((i + 1))
        printf '%s\n' "$inst" >> "$WORK/instances.txt"
        step_header "$i" "$count" "Checking $(basename "$inst")"
        s="$WORK/i$i"
        diagnose_instance "$inst" "$s"
        append_report "$inst" "$s" >> "$WORK/report.txt"

        info "$D_TRACKED tracked files, $D_JARS jars in mods, channel $D_CHANNEL"
        if [ "$D_ORPHAN" -gt 0 ]
            then bad "$D_ORPHAN leftover file(s) the pack does not know about"
            else good "no leftover files"
        fi
        if [ "$D_CORRUPT" -gt 0 ]
            then bad "$D_CORRUPT file(s) failed their checksum"
            else good "every tracked file matches its checksum"
        fi
        if [ "$D_MISSING" -gt 0 ]
            then bad "$D_MISSING tracked file(s) missing"
            else good "nothing missing"
        fi
        case "$D_SYNC" in
            stale)   bad "update tracking is out of date with the current pack" ;;
            current) good "update tracking is current" ;;
            *)       info "update tracking could not be checked" ;;
        esac

        sum_orphan=$((sum_orphan + D_ORPHAN))
        sum_corrupt=$((sum_corrupt + D_CORRUPT))
        sum_missing=$((sum_missing + D_MISSING))
        [ "$D_SYNC" = "stale" ] && sum_stale=$((sum_stale + 1))
    done <<LIST
$list
LIST

    publish_report
    printf '\n'
    good "Report written to $REPORT"
    printf '\n'

    note "Check finished.

$sum_orphan leftover file(s), $sum_corrupt failed checksum(s), $sum_missing missing file(s), $sum_stale copy(s) with out-of-date update tracking.

The full report is on your Desktop:

$(basename "$REPORT")

Send that file to your server operator. The next box offers to fix what was found."

    # Rung 0 covers every copy. A repair should not: pick one.
    inst=$(head -1 "$WORK/instances.txt")
    s="$WORK/i1"
    if [ "$count" -gt 1 ]; then
        set --
        while IFS= read -r item; do
            set -- "$@" "$(basename "$item")"
        done < "$WORK/instances.txt"
        chosen=$(pick "You have more than one copy of Salvage. Which one should be repaired?" "$@")
        [ -n "$chosen" ] || stop_here
        i=0; inst=""
        while IFS= read -r item; do
            i=$((i + 1))
            if [ "$(basename "$item")" = "$chosen" ]; then
                inst="$item"; s="$WORK/i$i"
            fi
        done < "$WORK/instances.txt"
        # Never fall back to "the first one" here: silently repairing a copy
        # the player did not choose is the one mistake with no undo prompt.
        [ -n "$inst" ] || stop_here
        # The D_ facts currently describe whichever copy was checked last.
        diagnose_instance "$inst" "$s"
    fi

    rung=$(pick "Repairing $(basename "$inst").

Nothing is deleted. Everything a repair touches is moved into a dated quarantine folder inside that copy, and your world, settings, keybinds, screenshots and shaders are never touched.

Start with the smallest one that could work." \
        "0  Nothing, I will just send the report" \
        "1  Targeted: move aside the wrong files, let the game re-download them" \
        "2  Resync: targeted, and also reset the update tracking" \
        "3  Full reset: move aside all mods and config, then re-download everything")

    case "$rung" in
        1*) rung=1 ;;
        2*) rung=2 ;;
        3*) rung=3 ;;
        *)  stop_here ;;
    esac

    osascript -e "display dialog \"Last check before anything moves.

Copy:  $(basename "$inst")
Option $rung

Files are moved into $QUAR inside that copy, never deleted. If this makes things worse you can drag them back out in Finder.\" buttons {\"Quit\",\"Do it\"} \
default button \"Do it\" with title \"$TITLE\"" >/dev/null 2>&1 || stop_here

    focus_terminal
    step_header 1 2 "Moving files aside"
    run_rung "$inst" "$s" "$rung"
    if [ -s "$s/changed.txt" ]; then
        while IFS= read -r item; do info "$item"; done < "$s/changed.txt"
    else
        info "Nothing needed moving."
    fi

    # Write the report before the updater check: get_bootstrap can bail out
    # on a failed download, and the record of what just moved must survive
    # that.
    publish_report

    step_header 2 2 "Checking the updater"
    get_bootstrap "$inst/minecraft"

    publish_report
    printf '\n'
    good "Done. Report updated: $REPORT"
    printf '\n'

    note "Repair finished.

Launch the game now. If it still crashes, run this again and pick the next option.

Nothing was deleted. Anything moved is in $QUAR inside the instance folder.

The report on your Desktop has been updated with what changed. Send it to your server operator.

Keep this file so you can run it again."
    exit 0
}

# --- flow -----------------------------------------------------------

banner

# The check has to be reachable on its own: "run this and send me the
# report" should not mean walking a player through the install prompts.
case "$1" in
    --check|--repair) check_flow ;;
esac

RAM=$(ram_mb)
HEAP=$(heap_mb)
info "Your Mac has ${RAM} MB of memory."
info "Looking for an existing setup..."

EXISTING=$(find_instances "$OLD_URL"; find_instances "$PACK_URL")

if [ -n "$EXISTING" ]; then
    COUNT=$(echo "$EXISTING" | wc -l | tr -d ' ')
    good "Found $COUNT existing Salvage copy(s)."

    CHOICE=$(osascript -e "display dialog \"You already have Salvage installed.

Found: $COUNT copy(s).

Switch to stable  --  point it at the stable release channel, so you only get changes once they have been tested. A backup of your settings file is saved first.

Check for problems  --  look for damaged, leftover or missing mod files, write a report you can send on, and offer to fix what it finds.

Neither one touches your world, settings, keybinds or shaders.\" \
buttons {\"Quit\",\"Check for problems\",\"Switch to stable\"} \
default button \"Switch to stable\" with title \"$TITLE\"" 2>/dev/null)

    case "$CHOICE" in
        *"Check for problems"*) check_flow ;;
        *"Switch to stable"*)   : ;;
        *) banner; info "Cancelled. Nothing was changed."; printf '\n'; exit 0 ;;
    esac

    focus_terminal
    step_header 1 2 "Switching to stable updates"
    echo "$EXISTING" | while read -r cfg; do
        [ -n "$cfg" ] || continue
        name=$(basename "$(dirname "$cfg")")
        cp "$cfg" "$cfg.backup-$(date +%Y%m%d-%H%M%S)"
        info "$name: settings backed up"
        sed -i '' "s|$OLD_URL|$PACK_URL|g" "$cfg"
        good "$name: switched to stable"
    done

    step_header 2 2 "Checking the updater"
    echo "$EXISTING" | while read -r cfg; do
        [ -n "$cfg" ] || continue
        get_bootstrap "$(dirname "$cfg")/minecraft"
    done

    printf '\n'
    good "All done."
    printf '\n'

    note "Done.

Just launch Salvage from Prism as normal. Nothing else to do.

Your world and settings were left exactly as they were."
    [ -f "$SELF" ] && mv "$SELF" "$HOME/.Trash/" 2>/dev/null
    exit 0
fi

# --- fresh install ---------------------------------------------------

good "No existing setup -- doing a fresh install."

ask "This will set up the Salvage Minecraft modpack on your Mac.

Three steps:

1.  Install Prism Launcher (the app that runs modded Minecraft)
2.  Create the Salvage instance
3.  Turn on automatic updates

Your Mac has $RAM MB of memory, so Minecraft will be given $HEAP MB.

Progress is shown in the window behind these boxes. Nothing happens until you click Continue on each step."

# step 1
if [ -d "$DATA/instances" ] || [ -d "/Applications/Prism Launcher.app" ]; then
    step_header 1 3 "Prism Launcher"
    good "Already installed -- skipping."
    mkdir -p "$DATA"
    note "Step 1 of 3 -- Prism Launcher

You already have it installed, so this step is skipped."
else
    ask "Step 1 of 3 -- Install Prism Launcher

Prism Launcher is the free, open-source app that runs modded Minecraft.

This downloads it and puts it in your Applications folder. It is around 100 MB.

You will see a progress bar in the window behind this box."
    focus_terminal
    step_header 1 3 "Installing Prism Launcher"
    install_prism
    note "Prism Launcher installed.

It is now in your Applications folder."
fi

# step 2
ask "Step 2 of 3 -- Create the Salvage instance

This adds an entry in Prism called Salvage, set to Minecraft $MC with the Fabric mod loader, and gives it $HEAP MB of memory.

This one is quick."
focus_terminal
step_header 2 3 "Creating the instance"
make_instance
note "Instance created.

Minecraft $MC, Fabric, $HEAP MB of memory."

# step 3
ask "Step 3 of 3 -- Turn on automatic updates

This adds a small file that checks the mod list every time you play.

It means you never have to reinstall or re-download anything when the pack changes."
focus_terminal
step_header 3 3 "Setting up automatic updates"
get_bootstrap "$DATA/instances/$INSTANCE/minecraft"

printf '\n'
good "===================================="
good "  Setup complete."
good "===================================="
printf '\n'

note "All done.

Next:

1.  Open Prism Launcher
2.  Sign in with your Microsoft account, top right
3.  Click Salvage, press Launch

The first launch downloads about 150 mods, so give it several minutes.

After that, try joining the server once. It will say you are not whitelisted -- that is expected, and it is how you get added. Just say you tried."

[ -f "$SELF" ] && mv "$SELF" "$HOME/.Trash/" 2>/dev/null

if [ -d "/Applications/Prism Launcher.app" ]; then
    osascript -e "display dialog \"Open Prism Launcher now?\" \
buttons {\"Not yet\",\"Open Prism\"} default button \"Open Prism\" \
with title \"$TITLE\"" 2>/dev/null | grep -q "Open Prism" \
        && open -a "/Applications/Prism Launcher.app"
fi

exit 0

#!/bin/bash
# Salvage Setup for macOS.
#
# Double-click to run. The FIRST time, right-click it and choose
# Open instead, so macOS allows it.
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

esc() {   # escape a string for embedding in an AppleScript literal
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

ask() {
    # AppleScript only raises an error for a button it recognises as the
    # cancel one, and that is decided by the name "Cancel" alone. Quit
    # would otherwise exit 0 and the run would carry on regardless, so the
    # answer is read back and matched instead of trusting the exit status.
    case "$(osascript -e "display dialog \"$(esc "$1")\" buttons {\"Quit\",\"Continue\"} \
default button \"Continue\" with title \"$TITLE\"" 2>/dev/null)" in
        *Continue*) : ;;
        *) banner; info "Cancelled. Nothing was changed."; printf '\n'; exit 0 ;;
    esac
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

# --- flow -----------------------------------------------------------

banner

RAM=$(ram_mb)
HEAP=$(heap_mb)
info "Your Mac has ${RAM} MB of memory."
info "Looking for an existing setup..."

EXISTING=$(find_instances "$OLD_URL"; find_instances "$PACK_URL")

if [ -n "$EXISTING" ]; then
    COUNT=$(echo "$EXISTING" | wc -l | tr -d ' ')
    good "Found $COUNT existing Salvage copy(s)."

    ask "You already have Salvage installed.

This will point it at the stable release channel, so you only get changes once they have been tested.

Your world, settings, keybinds and shaders will NOT be touched. A backup of your settings file is saved first.

Found: $COUNT copy(s)."

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

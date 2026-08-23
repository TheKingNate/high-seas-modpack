#!/usr/bin/env bash
URL="https://raw.githubusercontent.com/TheKingNate/high-seas-modpack/release/install/salvage-setup.py"
PY="/tmp/salvage-setup.py"

printf '\n  Salvage - Minecraft modpack setup\n\n'

if ! command -v python3 >/dev/null 2>&1; then
    printf '  Python 3 is not installed.\n\n'
    printf '    Ubuntu/Debian:  sudo apt install -y python3 python3-tk\n'
    printf '    Fedora:         sudo dnf install -y python3 python3-tkinter\n\n'
    read -p "  Press Enter to close"
    exit 1
fi

if ! python3 -c "import tkinter" 2>/dev/null; then
    printf '  Python is installed but tkinter is missing.\n\n'
    printf '    Ubuntu/Debian:  sudo apt install -y python3-tk\n'
    printf '    Fedora:         sudo dnf install -y python3-tkinter\n'
    printf '    Arch:           sudo pacman -S tk\n\n'
    read -p "  Press Enter to close"
    exit 1
fi

echo "  Fetching the setup app..."
if ! curl -fsSL -o "$PY" "$URL"; then
    printf '\n  Could not download the setup app.\n'
    printf '  Check your internet connection and try again.\n\n'
    read -p "  Press Enter to close"
    exit 1
fi

python3 "$PY"
rm -f "$PY"

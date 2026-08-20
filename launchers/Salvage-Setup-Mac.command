#!/bin/bash
cd "$(dirname "$0")"
URL="https://raw.githubusercontent.com/TheKingNate/high-seas-modpack/release/install/salvage-setup.py"
PY="/tmp/salvage-setup.py"

printf '\n  Salvage - Minecraft modpack setup\n\n'

if ! command -v python3 >/dev/null 2>&1; then
    osascript -e 'display dialog "Salvage Setup needs Python, which is not installed on this Mac.

Click Get Python to open the download page. Install it, then double-click this file again." buttons {"Cancel","Get Python"} default button "Get Python" with title "Salvage Setup" with icon caution' -e 'if button returned of result is "Get Python" then open location "https://www.python.org/downloads/macos/"' >/dev/null 2>&1
    exit 1
fi

echo "  Fetching the setup app..."
if ! curl -fsSL -o "$PY" "$URL"; then
    osascript -e 'display dialog "Could not download the setup app.

Check your internet connection and try again. If it keeps failing, tell Josh." buttons {"OK"} default button "OK" with title "Salvage Setup" with icon stop' >/dev/null 2>&1
    exit 1
fi

python3 "$PY"
rm -f "$PY"

#!/usr/bin/env bash
# Switch named mods from CurseForge to Modrinth metadata.
# Match is by substring against mods/*.pw.toml basenames.
#
#   ./cf-to-mr.sh structory entityculling mossylib
#   ./cf-to-mr.sh --apply structory entityculling mossylib

set -uo pipefail

MC="1.20.1"
LOADER="fabric"
API="https://api.modrinth.com/v2"

APPLY=0
if [ "${1:-}" = "--apply" ]; then APPLY=1; shift; fi

command -v jq >/dev/null 2>&1 || { echo "need jq" >&2; exit 1; }
[ -f pack.toml ] || { echo "run from the pack dir" >&2; exit 1; }
[ "$#" -gt 0 ] || { echo "usage: $0 [--apply] <name> ..." >&2; exit 1; }

norm() { echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g'; }

for want in "$@"; do
    f="$(ls mods/*.pw.toml 2>/dev/null | grep -i "$want" | head -1)"
    if [ -z "$f" ]; then
        echo "no .pw.toml matching: $want"
        continue
    fi

    pwname="$(basename "$f" .pw.toml)"
    title="$(sed -n 's/^name *= *"\(.*\)"/\1/p' "$f" | head -1)"
    [ -n "$title" ] || title="$pwname"

    hits="$(curl -sf --get "$API/search" \
        --data-urlencode "query=$title" \
        --data-urlencode 'limit=5' \
        --data-urlencode \
"facets=[[\"categories:$LOADER\"],[\"versions:$MC\"]]" \
        | jq -r '.hits[] | "\(.slug)\t\(.title)"')"

    if [ -z "$hits" ]; then
        echo "no Modrinth match: $title"
        continue
    fi

    nt="$(norm "$title")"
    match=""
    while IFS="$(printf '\t')" read -r slug mtitle; do
        [ -n "$slug" ] || continue
        nm="$(norm "$mtitle")"
        case "$nt" in "$nm"*) match="$slug"; break;; esac
        case "$nm" in "$nt"*) match="$slug"; break;; esac
    done <<< "$hits"

    if [ -z "$match" ]; then
        echo "ambiguous: $title"
        echo "$hits" | sed 's/^/    /'
        continue
    fi

    echo "$pwname -> $match"
    if [ "$APPLY" -eq 1 ]; then
        packwiz remove "$pwname" && packwiz modrinth add "$match"
    fi
done

if [ "$APPLY" -eq 1 ]; then
    echo
    packwiz refresh
fi

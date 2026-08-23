#!/usr/bin/env bash
# Search Modrinth, verifying each hit actually has a build for this
# pack's loader AND version (search facets alone don't guarantee that).
set -euo pipefail
[ $# -gt 0 ] || { echo 'usage: ./find-mod.sh "search terms"' >&2; exit 1; }

MC=$(grep '^minecraft' pack.toml | sed 's/.*"\(.*\)".*/\1/')
LOADER=fabric

hits=$(curl -s --get "https://api.modrinth.com/v2/search" \
  --data-urlencode "query=$*" \
  --data-urlencode "facets=[[\"categories:$LOADER\"],[\"versions:$MC\"],[\"project_type:mod\"]]" \
  --data-urlencode 'limit=20' \
| python3 -c "
import sys,json
for h in json.load(sys.stdin)['hits']:
    print(f\"{h['project_id']}|{h['slug']}|{h['downloads']}|{h['title']}|{h['description'][:64]}\")
")

[ -n "$hits" ] || { echo "  nothing found"; exit 0; }

found=0
while IFS='|' read -r id slug dl title desc; do
    [ -n "$id" ] || continue
    n=$(curl -s --get "https://api.modrinth.com/v2/project/$id/version" \
        --data-urlencode "loaders=[\"$LOADER\"]" \
        --data-urlencode "game_versions=[\"$MC\"]" \
        | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    if [ "$n" -gt 0 ]; then
        printf '%-38s %10s  %s\n' "$slug" "$dl" "$title"
        printf '%42s%s\n' '' "$desc"
        found=$((found+1))
    fi
done <<< "$hits"

[ "$found" -gt 0 ] || echo "  nothing with a real $LOADER $MC build"

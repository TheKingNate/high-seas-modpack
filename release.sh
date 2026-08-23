#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

BUMP="${1:-patch}"
MSG="${2:-}"
[ -n "$MSG" ] || { echo 'usage: ./release.sh <patch|minor|major|X.Y.Z> "message"' >&2; exit 1; }

REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]([^/]+/[^/.]+).*#\1#')
CUR=$(grep '^version' pack.toml | sed 's/.*"\(.*\)".*/\1/')
PREV=$(git describe --tags --abbrev=0 2>/dev/null || true)
IFS=. read -r MA MI PA <<< "$CUR"
case "$BUMP" in
    major) NEW="$((MA+1)).0.0" ;;
    minor) NEW="$MA.$((MI+1)).0" ;;
    patch) NEW="$MA.$MI.$((PA+1))" ;;
    *)     NEW="$BUMP" ;;
esac

echo "== $CUR -> $NEW"
if [ -n "$(git status --porcelain)" ]; then
    git add -A && git commit -m "wip before v$NEW" >/dev/null
fi
sed -i.bak "s/^version = .*/version = \"$NEW\"/" pack.toml && rm pack.toml.bak

[ -x ./make-readme.sh ] && ./make-readme.sh
packwiz refresh
packwiz modrinth export
packwiz curseforge export

git add -A
git commit -m "v$NEW: $MSG"
git tag -a "v$NEW" -m "$MSG"
git push origin main --tags
git branch -f release main
git push -f origin release

command -v gh >/dev/null 2>&1 || { echo "gh not installed - no release published"; exit 0; }

MCV=$(grep '^minecraft' pack.toml | sed 's/.*"\(.*\)".*/\1/')
COUNT=$(ls -1 mods/*.pw.toml 2>/dev/null | wc -l | tr -d ' ')

# human-readable mod name from a .pw.toml at a given ref ("HEAD" = worktree)
mod_name() {
    local n
    if [ "$1" = HEAD ]; then n=$(grep -m1 '^name' "$2" 2>/dev/null | sed 's/name = "\(.*\)"/\1/')
    else n=$(git show "$1:$2" 2>/dev/null | grep -m1 '^name' | sed 's/name = "\(.*\)"/\1/'); fi
    [ -n "$n" ] && printf '%s' "$n" || basename "$2" .pw.toml
}
jar_at() {
    if [ "$1" = HEAD ]; then grep -m1 '^filename' "$2" 2>/dev/null | sed 's/filename = "\(.*\)"/\1/'
    else git show "$1:$2" 2>/dev/null | grep -m1 '^filename' | sed 's/filename = "\(.*\)"/\1/'; fi
}
bullets() {  # bullets <ref-for-names> <newline-list>
    while IFS= read -r f; do [ -n "$f" ] && printf -- '- %s\n' "$(mod_name "$1" "$f")"; done
}

{
printf '%s\n\n' "$MSG"

if [ -n "$PREV" ]; then
    ADDED=$(git diff --name-status "$PREV"..HEAD -- mods/ | awk '$1=="A"{print $2}')
    GONE=$(git diff --name-status "$PREV"..HEAD -- mods/ | awk '$1=="D"{print $2}')
    BUMPED=""
    for f in $(git diff --name-status "$PREV"..HEAD -- mods/ | awk '$1=="M"{print $2}'); do
        [ "$(jar_at "$PREV" "$f")" != "$(jar_at HEAD "$f")" ] && BUMPED="$BUMPED$f\n"
    done
    BUMPED=$(printf '%b' "$BUMPED" | sed '/^$/d')

    if [ -n "$ADDED$GONE$BUMPED" ]; then
        printf '## Mod changes\n\n'
        [ -n "$ADDED" ]  && { printf '**Added (%s)**\n\n' "$(printf '%s\n' "$ADDED" | wc -l | tr -d ' ')"
                              printf '%s\n' "$ADDED"  | bullets HEAD;   printf '\n'; }
        [ -n "$GONE" ]   && { printf '**Removed (%s)**\n\n' "$(printf '%s\n' "$GONE" | wc -l | tr -d ' ')"
                              printf '%s\n' "$GONE"   | bullets "$PREV"; printf '\n'; }
        [ -n "$BUMPED" ] && { printf '**Updated (%s)**\n\n' "$(printf '%s\n' "$BUMPED" | wc -l | tr -d ' ')"
                              printf '%s\n' "$BUMPED" | bullets HEAD;   printf '\n'; }
    else
        printf '## Mod changes\n\nNone - config, quests or tooling only.\n\n'
    fi

    printf '## Commits\n\n'
    git log --no-merges --pretty='- %s' "$PREV"..HEAD | grep -v -- "^- v$NEW:" || true
    printf '\n'
    printf '[Full diff](https://github.com/%s/compare/%s...v%s)\n\n' "$REPO" "$PREV" "$NEW"
fi

printf '**This build:** %s mods - Minecraft %s - Fabric\n\n' "$COUNT" "$MCV"
printf -- '---\n\n'
cat install/RELEASE-NOTES.md
} > /tmp/salvage-notes.md

gh release create "v$NEW" launchers/Salvage-Setup-Windows.bat launchers/Salvage-Setup-Mac.command launchers/Salvage-Setup-Linux.sh install/setup-server.sh \
    --repo "$REPO" --title "Salvage v$NEW" --notes-file /tmp/salvage-notes.md

echo
echo "  https://github.com/$REPO/releases/tag/v$NEW"
echo

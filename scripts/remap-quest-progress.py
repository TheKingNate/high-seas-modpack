#!/usr/bin/env python3
"""
Translates saved FTB Quests player progress from one questline revision to another.

    # see what would change, touching nothing:
    python3 scripts/remap-quest-progress.py --from release --to . --progress /path/to/ftbquests
    # write it, leaving .bak files next to each:
    python3 scripts/remap-quest-progress.py --from release --to . --progress /path/to/ftbquests --apply

Why this exists: FTB Quests stores progress BY ID, never by name. `world/ftbquests/*.snbt`
holds task_progress (task ids), started / completion_count (quest ids) and claimed_rewards
(reward ids). Regenerating the questline with different ids therefore silently resets every
player: completed quests go back to incomplete and claimed rewards become claimable again.

That is exactly the state main is in. Measured against the live server:

    release chapters   225 ids        main chapters   342 ids
    release n main       0 ids in common
    live progress      213 ids     n release  91     n main  0

Not one recorded completion survives the switch. But the questline is mostly the SAME
quests with new ids - 51 of release's 53 quests still exist in main under an identical
chapter+title - so the progress can be carried across by matching on position rather than id:

    quest  -> (chapter, quest title)
    task   -> (chapter, quest title, task index)
    reward -> (chapter, quest title, reward index)

which is the same key scheme scripts/make-quests.py hashes its ids from.

Only `beyond/Nullscape` and `shipwright/Under Sail` have no counterpart in main; progress on
those two cannot be carried and is reported as dropped rather than silently lost.

This never touches a server. Point --progress at a COPY of world/ftbquests/.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID = r"[0-9A-F]{16}"


def read_chapters(ref):
    """{relative path: text} for a git ref, or for the working tree when ref is '.'."""
    rel = "config/ftbquests/quests/chapters"
    if ref == ".":
        out = {}
        for f in sorted(glob.glob(os.path.join(PACK, rel, "*.snbt"))):
            out[os.path.basename(f)] = open(f).read()
        return out
    names = subprocess.run(["git", "-C", PACK, "ls-tree", "-r", "--name-only", ref, "--", rel],
                           capture_output=True, text=True).stdout.split()
    out = {}
    for n in names:
        if n.endswith(".snbt"):
            out[os.path.basename(n)] = subprocess.run(
                ["git", "-C", PACK, "show", f"{ref}:{n}"], capture_output=True, text=True).stdout
    return out


def index(chapters):
    """Position key -> id, for quests, their tasks and their rewards."""
    keys = {}
    for fname, text in chapters.items():
        ch = fname[:-5]
        for blk in re.split(r"\n\t\t\{\n", text)[1:]:
            qid = re.search(r'\bid: "(%s)"' % ID, blk)
            qt = re.search(r'title: "([^"]+)"', blk)
            if not (qid and qt):
                continue
            quest = qt.group(1)
            keys[("quest", ch, quest)] = qid.group(1)
            body, _, rest = blk.partition("rewards: [")
            for kind, chunk in (("task", body.partition("tasks: [")[2]), ("reward", rest)):
                for i, sub in enumerate(re.split(r"\n\t\t\t\t\{\n", chunk)[1:]):
                    m = re.search(r'\bid: "(%s)"' % ID, sub)
                    if m:
                        keys[(kind, ch, quest, i)] = m.group(1)
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="release", help="git ref the progress was recorded against")
    ap.add_argument("--to", dest="dst", default=".", help="git ref (or '.') to migrate to")
    ap.add_argument("--progress", required=True, help="directory of player *.snbt (use a COPY)")
    ap.add_argument("--apply", action="store_true", help="write the files (default is a dry run)")
    a = ap.parse_args()

    old, new = index(read_chapters(a.src)), index(read_chapters(a.dst))
    print(f"{a.src}: {len(old)} keyed ids     {a.dst}: {len(new)} keyed ids")

    remap, dropped = {}, []
    for k, oid in old.items():
        nid = new.get(k)
        if nid is None:
            dropped.append((k, oid))
        elif nid != oid:
            remap[oid] = nid
    lost_q = sorted({(k[1], k[2]) for k, _ in dropped if k[0] == "quest"})
    lost_sub = sorted({(k[1], k[2]) for k, _ in dropped if k[0] != "quest"})
    print(f"  {len(remap)} id(s) change, {len(dropped)} have no counterpart in {a.dst}")
    print(f"    quests removed outright: {len(lost_q)}")
    for ch, q in lost_q[:10]:
        print(f"        {ch}/{q}")
    # A task/reward index that no longer exists does NOT mean the quest is gone - the
    # quest survives and is re-checkable; only that one task's tick is dropped. Keeping
    # these separate, because lumping them together overstates the loss badly.
    print(f"    quests kept, but with a task/reward whose position moved: {len(lost_sub)}")

    files = sorted(glob.glob(os.path.join(a.progress, "*.snbt")))
    if not files:
        print(f"\nNo *.snbt in {a.progress}")
        return 2
    print()
    old_ids, new_ids = set(old.values()), set(new.values())
    tot_hit = tot_stale = tot_orphan = 0
    for f in files:
        text = open(f).read()
        ids = set(re.findall(ID, text)) - {"0" * 15 + "1"}
        hit = len([i for i in ids if i in remap])
        # Already dead BEFORE this migration: ids from questline revisions older than
        # --from. The old sequential-id generator renumbered on every edit, so a lot of
        # historical progress was orphaned long ago. Not caused by this migration.
        stale = len([i for i in ids if i not in old_ids and i not in new_ids])
        orphan = len(ids) - hit - stale - len([i for i in ids if i in new_ids])
        tot_hit += hit
        tot_stale += stale
        tot_orphan += max(0, orphan)
        print(f"  {os.path.basename(f)[:20]:<22} {len(ids):>4} ids  {hit:>4} carried  "
              f"{max(0, orphan):>4} lost now  {stale:>4} already dead")
        if a.apply and hit:
            shutil.copy2(f, f + ".bak")
            open(f, "w").write(re.sub(ID, lambda m: remap.get(m.group(0), m.group(0)), text))

    print(f"\n  total: {tot_hit} carried across, {tot_orphan} lost by this migration, "
          f"{tot_stale} already orphaned before it")
    if a.apply:
        print("  written; .bak kept beside each file")
    else:
        print("  DRY RUN - nothing written. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

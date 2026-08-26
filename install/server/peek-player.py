#!/usr/bin/env python3
"""Print what a player was carrying, from a playerdata .dat.

Used by rollback.sh. Self-contained on purpose - this has to run on the server with
nothing installed.

    peek-player.py <file>              full inventory
    peek-player.py <file> --summary    one line, for scanning many snapshots

The summary line is the point: run it across every snapshot newest-first and the
moment someone's gear disappears is obvious at a glance, so you restore from the
newest snapshot that still has it instead of guessing.
"""
import gzip
import struct
import sys

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE = 0, 1, 2, 3, 4, 5, 6
BARRAY, STRING, LIST, COMPOUND, IARRAY, LARRAY = 7, 8, 9, 10, 11, 12


class Reader:
    def __init__(self, b):
        self.b, self.i = b, 0

    def u1(self):
        v = self.b[self.i]; self.i += 1; return v

    def num(self, fmt, size):
        v = struct.unpack_from(fmt, self.b, self.i)[0]; self.i += size; return v

    def string(self):
        n = self.num(">H", 2)
        v = self.b[self.i:self.i + n].decode("utf-8", "replace"); self.i += n
        return v


def payload(r, t):
    if t == BYTE:   return r.num(">b", 1)
    if t == SHORT:  return r.num(">h", 2)
    if t == INT:    return r.num(">i", 4)
    if t == LONG:   return r.num(">q", 8)
    if t == FLOAT:  return r.num(">f", 4)
    if t == DOUBLE: return r.num(">d", 8)
    if t == BARRAY:
        n = r.num(">i", 4); v = r.b[r.i:r.i + n]; r.i += n; return v
    if t == STRING: return r.string()
    if t == LIST:
        it = r.u1(); n = r.num(">i", 4)
        if it == END or n <= 0:
            return []
        return [payload(r, it) for _ in range(n)]
    if t == COMPOUND:
        out = {}
        while True:
            ct = r.u1()
            if ct == END:
                return out
            # The name must be bound before the value is read. Written as
            # out[r.string()] = payload(r, ct) Python evaluates the right-hand
            # side first, so every field is read one step out of alignment and
            # the parse desyncs a few thousand bytes in.
            name = r.string()
            out[name] = payload(r, ct)
    if t == IARRAY:
        n = r.num(">i", 4); return [r.num(">i", 4) for _ in range(n)]
    if t == LARRAY:
        n = r.num(">i", 4); return [r.num(">q", 8) for _ in range(n)]
    raise ValueError("unknown tag %d at %d" % (t, r.i))


def load(path):
    raw = open(path, "rb").read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    r = Reader(raw); r.u1(); r.string()
    return payload(r, COMPOUND)


def enchants(stack):
    tag = stack.get("tag") or {}
    out = []
    for e in (tag.get("Enchantments") or []) + (tag.get("StoredEnchantments") or []):
        out.append("%s %s" % (str(e.get("id", "?")).split(":")[-1], e.get("lvl", "")))
    return out


def short(item_id):
    return str(item_id).split(":")[-1]


ARMOUR = {100: "boots", 101: "leggings", 102: "chestplate", 103: "helmet"}


def backpack_contents(stack):
    """Traveler's Backpack keeps its inventory in the item's own tag."""
    tag = stack.get("tag") or {}
    inv = tag.get("Inventory")
    items = []
    if isinstance(inv, dict):
        items = inv.get("Items", [])
    elif isinstance(inv, list):
        items = inv
    real = [i for i in items if i.get("id") not in (None, "minecraft:air")]
    return tag.get("Tier"), tag.get("StorageSlots"), real


def main():
    path = sys.argv[1]
    summary = "--summary" in sys.argv
    try:
        p = load(path)
    except Exception as exc:
        print("(unreadable: %s)" % exc)
        return

    inv = p.get("Inventory", [])
    ender = p.get("EnderItems", [])
    carried = [i for i in inv if i.get("Slot", 99) not in ARMOUR and i.get("Slot", 99) != -106]
    ench_count = sum(1 for i in inv if enchants(i))

    if summary:
        # Name the things worth noticing rather than every stack: a weapon, a tool,
        # and any backpack with contents. That is what disappears when someone is
        # robbed by a bug, and what makes the losing snapshot obvious in a list.
        notable = []
        for i in inv:
            iid = str(i.get("id", ""))
            if iid.startswith("travelersbackpack:"):
                tier, slots, real = backpack_contents(i)
                notable.append("%s(T%s,%d items)" % (short(iid), tier, len(real)))
            elif any(w in iid for w in ("sword", "pickaxe", "axe", "bow", "trident", "rapier", "staff")):
                notable.append(short(iid))
        pos = p.get("Pos") or [0, 0, 0]
        line = "%2d carried | %2d enchanted | lvl %-3s | %s" % (
            len(carried), ench_count, p.get("XpLevel", "?"),
            ", ".join(notable[:4]) if notable else "-")
        if len(notable) > 4:
            line += " +%d" % (len(notable) - 4)
        line += "   @ %.0f %.0f %.0f" % (pos[0], pos[1], pos[2])
        print(line)
        return

    pos = p.get("Pos") or [0, 0, 0]
    print("  position   %.0f %.0f %.0f   (%s)" % (pos[0], pos[1], pos[2], p.get("Dimension", "?")))
    print("  health     %s      xp level %s" % (round(p.get("Health", 0), 1), p.get("XpLevel", "?")))
    print("  carried    %d stacks     ender chest %d stacks" % (len(carried), len(ender)))
    print()

    for slot in sorted(ARMOUR):
        for i in inv:
            if i.get("Slot") == slot:
                e = enchants(i)
                print("  %-11s %s%s" % (ARMOUR[slot], short(i.get("id")),
                                        ("  [%s]" % ", ".join(e)) if e else ""))
    for i in inv:
        if i.get("Slot") == -106:
            print("  %-11s %s" % ("offhand", short(i.get("id"))))
    print()

    for i in sorted(carried, key=lambda x: x.get("Slot", 99)):
        e = enchants(i)
        line = "   %3s  %s x%s%s" % (i.get("Slot"), i.get("id"), i.get("Count", 1),
                                     ("  [%s]" % ", ".join(e)) if e else "")
        print(line)
        if str(i.get("id", "")).startswith("travelersbackpack:"):
            tier, slots, real = backpack_contents(i)
            print("          tier %s, %s slots, %d stacks inside" % (tier, slots, len(real)))
            for b in real[:12]:
                be = enchants(b)
                print("            %s x%s%s" % (b.get("id"), b.get("Count", 1),
                                                ("  [%s]" % ", ".join(be)) if be else ""))
            if len(real) > 12:
                print("            ... and %d more" % (len(real) - 12))


if __name__ == "__main__":
    main()

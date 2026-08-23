#!/usr/bin/env python3
"""
Generates the Salvage questline as FTB Quests SNBT.

    cd ~/mc/high-seas
    python3 make-quests.py

Writes config/ftbquests/quests/{data.snbt,chapter_groups.snbt,
chapters/*.snbt}. Safe to re-run -- it overwrites.

Task types used: item (vanilla ids only, guaranteed to resolve),
checkmark (player-clicked, never breaks), dimension, kill.
Modded items are checkmarks on purpose -- open the quest in the
editor and drag the real item in to upgrade any of them.

Rewards: xp plus a /puffish_skills command for skill points.
"""

import os
import hashlib

_used = {}


def qid(key):
    """Deterministic id derived from WHAT a thing is, not where it sits.

    This used to draw from a sequential seeded RNG, which meant inserting one
    quest shifted the id of every quest after it. FTB Quests tracks player
    completion by id, so that silently wiped everyone's progress. Hashing a
    stable key means ids only change when the thing itself is renamed.
    """
    h = key
    while True:
        v = "%016X" % int.from_bytes(hashlib.sha256(h.encode("utf-8")).digest()[:8], "big")
        if _used.get(v, key) == key:
            _used[v] = key
            return v
        h += "#"          # collision: perturb and retry


def esc(s):
    return s.replace('"', '\\"')


# --- task / reward builders ----------------------------------------

def t_check(title):
    return {"type": "checkmark", "title": title}


def t_item(item, count=1):
    return {"type": "item", "item": item, "count": count}


def t_dim(dim):
    return {"type": "dimension", "dimension": dim}


def t_kill(entity, count=1):
    return {"type": "kill", "entity": entity, "value": count}


def r_xp(n):
    return {"type": "xp", "xp": n}


def r_item(item, count=1):
    return {"type": "item", "item": item, "count": count}


def r_skill(n, cat="combat"):
    return {"type": "command", "title": "%d Skill Points" % n,
            "command": "/puffish_skills points add @p %s %d" % (cat, n),
            "player_command": False}


# --- chapter data ---------------------------------------------------
# (title, subtitle, icon, [ (x, y, title, [desc], [tasks], [rewards]) ])

CHAPTERS = [
 ("Castaway", "Start here", "minecraft:oak_boat", [
  (0, 0, "Ashore",
   ["You woke up on a beach. Everything else follows from here."],
   [t_item("minecraft:oak_log", 8)],
   [r_xp(10), r_item("minecraft:bread", 8)]),
  (2, 0, "Something To Carry It In",
   ["Craft a Traveler's Backpack.",
    "Inventory space is the first thing this pack takes from you."],
   [t_check("Craft a Traveler's Backpack")],
   [r_xp(20), r_skill(2)]),
  (4, 0, "Know Where You Are",
   ["Craft an Explorer's Compass.",
    "There are sixteen structure mods loaded. You will need this."],
   [t_check("Craft an Explorer's Compass")],
   [r_xp(20), r_skill(1)]),
  (6, 0, "A Way Back",
   ["Place a Waystone.",
    "Do not put one on a ship. It will misbehave."],
   [t_check("Place a Waystone")],
   [r_xp(20), r_skill(1)]),
 ]),

 ("Shipwright", "Everything else is gated behind this", "minecraft:oak_boat", [
  (0, 0, "The Helm",
   ["Craft a Ship Helm.",
    "This is the single most important block in the pack."],
   [t_check("Craft a Ship Helm")],
   [r_xp(40), r_skill(3)]),
  (2, 0, "Assemble",
   ["Build a hull, place the helm, shift-right-click to assemble.",
    "",
    "Start small. Large hulls ride the waves far more gently --",
    "a raft will show you the swell, a galleon will not."],
   [t_check("Assemble your first ship")],
   [r_xp(60), r_skill(3)]),
  (4, 0, "Under Steam",
   ["Craft a Ship Engine and mount it on your ship.",
    "",
    "Balloons give you lift. Engines give you somewhere to go."],
   [t_check("Mount a Ship Engine on your ship")],
   [r_xp(40), r_skill(2)]),
  (6, 0, "Blue Water",
   ["Sail 1000 blocks from spawn."],
   [t_check("Sail 1000 blocks")],
   [r_xp(80), r_skill(4)]),
 ]),

 ("Charting", "Wander", "minecraft:filled_map", [
  (0, 0, "Ruins",
   ["Find a Structory ruin."],
   [t_check("Find a Structory ruin")],
   [r_xp(30), r_skill(2)]),
  (2, 0, "Somewhere Inhabited",
   ["Find a Towns and Towers settlement."],
   [t_check("Find a Towns and Towers settlement")],
   [r_xp(30), r_skill(2)]),
  (4, 0, "Three Coasts",
   ["Visit three biomes you have not seen before."],
   [t_check("Visit 3 new biomes")],
   [r_xp(40), r_skill(2)]),
  (6, 0, "Underground",
   ["Clear a YUNG's dungeon."],
   [t_check("Clear a YUNG's dungeon")],
   [r_xp(50), r_skill(3)]),
  (8, 0, "The Board",
   ["Complete a bounty from a Bountiful board.",
    "",
    "These repeat forever. When you do not know what to do,",
    "this is the answer."],
   [t_check("Complete a Bountiful bounty")],
   [r_xp(40), r_skill(2)]),
 ]),

 ("The Forge", "Wheels and current", "minecraft:iron_ingot", [
  (0, 0, "Kinetics",
   ["Craft a Create mechanical press."],
   [t_check("Craft a Mechanical Press")],
   [r_xp(40), r_skill(2, "mining")]),
  (2, 0, "Something That Moves",
   ["Build a powered contraption."],
   [t_check("Build a working contraption")],
   [r_xp(50), r_skill(2, "mining")]),
  (4, 0, "First Current",
   ["Craft a Powah generator -- Furnator, Magmator or Solar Panel."],
   [t_check("Craft a Powah generator")],
   [r_xp(50), r_skill(2, "mining")]),
  (6, 0, "Storage",
   ["Craft a Powah Energy Cell."],
   [t_check("Craft an Energy Cell")],
   [r_xp(60), r_skill(3, "mining")]),
 ]),

 ("Below", "The ocean has a floor", "minecraft:heart_of_the_sea", [
  (0, 0, "Lungs",
   ["Craft Hybrid Aquatic diving armor."],
   [t_check("Craft diving armor")],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Sunken",
   ["Find a Hopo underwater ruin."],
   [t_check("Find an underwater ruin")],
   [r_xp(50), r_skill(2)]),
  (4, 0, "The Monument",
   ["Reach an ocean monument."],
   [t_item("minecraft:prismarine_shard", 16)],
   [r_xp(80), r_skill(3)]),
  (6, 0, "Salvaged Air",
   ["Collect 8 nautilus shells."],
   [t_item("minecraft:nautilus_shell", 8)],
   [r_xp(60), r_item("minecraft:heart_of_the_sea", 1), r_skill(3)]),
 ]),

 ("Salvage", "The name on the tin", "minecraft:gunpowder", [
  (0, 0, "Powder And Shot",
   ["Craft a Supplementaries cannon."],
   [t_check("Craft a cannon")],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Broadside",
   ["Mount cannons on your ship."],
   [t_check("Mount a cannon on a ship")],
   [r_xp(60), r_skill(3)]),
  (4, 0, "Silence A Gun",
   ["Kill a pirate cannoneer.",
    "",
    "Each cannoneer runs one cannon. Kill them and that gun",
    "stops firing."],
   [t_check("Kill a pirate cannoneer")],
   [r_xp(80), r_skill(4)]),
  (6, 0, "Dead In The Water",
   ["Kill a pirate helmsman.",
    "",
    "The helmsman drives the ship. Kill them and it stops."],
   [t_check("Kill a pirate helmsman")],
   [r_xp(100), r_skill(5)]),
  (8, 0, "Plunder",
   ["Board a pirate ship and take its cargo."],
   [t_check("Loot a pirate ship")],
   [r_xp(120), r_item("minecraft:gold_ingot", 16), r_skill(5)]),
  (10, 0, "Wrecks",
   ["Find a shipwreck structure."],
   [t_check("Find a shipwreck")],
   [r_xp(50), r_skill(2)]),
 ]),

 ("The Deep", "Optional. Bring a friend.", "minecraft:prismarine_crystals", [
  (0, 0, "Ship Graveyard",
   ["Enter the Aquamirae ship graveyard.",
    "",
    "Do not come here before you have diving gear."],
   [t_check("Enter the ship graveyard")],
   [r_xp(100), r_skill(4)]),
  (2, 0, "Something In The Dark",
   ["Survive an Anglerfish."],
   [t_check("Survive an Anglerfish")],
   [r_xp(120), r_skill(5)]),
  (4, 0, "Cornelia",
   ["Kill the Ghost of Captain Cornelia."],
   [t_check("Kill Captain Cornelia")],
   [r_xp(300), r_skill(10)]),
  (6, 0, "Deep City",
   ["Clear a Hopo deep ocean city."],
   [t_check("Clear a deep ocean city")],
   [r_xp(150), r_skill(6)]),
 ]),

 ("The Network", "Your half", "minecraft:redstone", [
  (0, 0, "Certus",
   ["Collect 16 certus quartz."],
   [t_check("Collect 16 certus quartz")],
   [r_xp(40), r_skill(2, "mining")]),
  (2, 0, "Controller",
   ["Craft an ME Controller."],
   [t_check("Craft an ME Controller")],
   [r_xp(100), r_skill(4, "mining")]),
  (4, 0, "Wireless",
   ["Craft a wireless terminal."],
   [t_check("Craft a wireless terminal")],
   [r_xp(80), r_skill(3, "mining")]),
  (6, 0, "Autocraft",
   ["Autocraft something with more than one step."],
   [t_check("Autocraft a multi-step recipe")],
   [r_xp(150), r_skill(6, "mining")]),
  (8, 0, "Reactor",
   ["Build a Powah reactor."],
   [t_check("Build a Powah reactor")],
   [r_xp(200), r_skill(8, "mining")]),
  (10, 0, "Grid",
   ["Move power across a distance with Flux Networks."],
   [t_check("Move power with Flux Networks")],
   [r_xp(120), r_skill(5, "mining")]),
 ]),

 ("Arcana", "Light magic", "minecraft:amethyst_shard", [
  (0, 0, "Binding Table",
   ["Craft a Spell Binding Table.",
    "",
    "2 amethyst shards, 1 gold ingot, 1 book, 3 polished diorite.",
    "Surround it with bookshelves like an enchanting table."],
   [t_item("minecraft:amethyst_shard", 2)],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Ammunition",
   ["Craft runes. They are the fuel; keep a stack on you."],
   [t_check("Craft runes")],
   [r_xp(40), r_skill(2)]),
  (4, 0, "Wand",
   ["Craft a wand."],
   [t_check("Craft a wand")],
   [r_xp(60), r_skill(3)]),
  (6, 0, "First Spell",
   ["Bind a spell to a spell book."],
   [t_check("Bind your first spell")],
   [r_xp(80), r_skill(4)]),
  (8, 0, "Tower",
   ["Raid a Wizard Tower."],
   [t_check("Raid a Wizard Tower")],
   [r_xp(150), r_skill(6)]),
  (10, 0, "Specialise",
   ["Unlock a Simply Skills specialisation."],
   [t_check("Unlock a specialisation")],
   [r_xp(200), r_skill(8)]),
 ]),

 ("Provision", "Between fights", "minecraft:bread", [
  (0, 0, "The Pot",
   ["Craft a Farmer's Delight cooking pot."],
   [t_check("Craft a cooking pot")],
   [r_xp(40), r_skill(2)]),
  (2, 0, "Cook",
   ["Cook five different dishes."],
   [t_check("Cook 5 different dishes")],
   [r_xp(60), r_skill(3)]),
  (4, 0, "Harvest",
   ["Grow ten different Croptopia crops."],
   [t_check("Grow 10 Croptopia crops")],
   [r_xp(80), r_skill(3)]),
  (6, 0, "A Full Net",
   ["Catch six Fish of Thieves species."],
   [t_check("Catch 6 fish species")],
   [r_xp(60), r_skill(3)]),
  (8, 0, "Out Of Season",
   ["Grow and harvest a crop through a season change.",
    "",
    "Fabric Seasons is installed. Wheat, carrots and potatoes",
    "slow right down outside their season -- the calendar matters."],
   [t_check("Harvest a crop after the season turns")],
   [r_xp(80), r_skill(4)]),
 ]),

 ("Beyond", "Endgame", "minecraft:end_crystal", [
  (0, 0, "Hot Rock",
   ["Enter the Nether."],
   [t_dim("minecraft:the_nether")],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Incendium",
   ["Find an Incendium structure."],
   [t_check("Find an Incendium structure")],
   [r_xp(120), r_skill(5)]),
  (4, 0, "The End",
   ["Enter the End."],
   [t_dim("minecraft:the_end")],
   [r_xp(100), r_skill(4)]),
  (6, 0, "Ruins at the Edge",
   ["Find a Moog's End structure.",
    "",
    "Nullscape reshaped the End -- the outer islands are worth",
    "the crossing now."],
   [t_check("Find a Moog's End structure")],
   [r_xp(150), r_skill(6)]),
  (8, 0, "Something Enormous",
   ["Kill a Bosses of Mass Destruction boss."],
   [t_check("Kill a BOMD boss")],
   [r_xp(400), r_skill(12)]),
 ]),
]


# --- emit -----------------------------------------------------------

def snbt_strlist(lines):
    return "[" + ", ".join('"%s"' % esc(l) for l in lines) + "]"


def emit_task(t, key):
    out = ['\t\t\t\t{']
    out.append('\t\t\t\t\tid: "%s"' % qid(key))
    for k, v in t.items():
        if isinstance(v, str):
            out.append('\t\t\t\t\t%s: "%s"' % (k, esc(v)))
        elif isinstance(v, bool):
            out.append('\t\t\t\t\t%s: %s' % (k, "true" if v else "false"))
        else:
            out.append('\t\t\t\t\t%s: %dL' % (k, v)
                       if k == "value" else '\t\t\t\t\t%s: %d' % (k, v))
    out.append('\t\t\t\t}')
    return "\n".join(out)


def emit_reward(r, key):
    out = ['\t\t\t\t{']
    out.append('\t\t\t\t\tid: "%s"' % qid(key))
    for k, v in r.items():
        if isinstance(v, str):
            out.append('\t\t\t\t\t%s: "%s"' % (k, esc(v)))
        elif isinstance(v, bool):
            out.append('\t\t\t\t\t%s: %s' % (k, "true" if v else "false"))
        else:
            out.append('\t\t\t\t\t%s: %d' % (k, v))
    out.append('\t\t\t\t}')
    return "\n".join(out)


def emit_chapter(idx, title, subtitle, icon, quests):
    fname = title.lower().replace("'", "").replace(" ", "_")
    lines = ["{"]
    lines.append('\tid: "%s"' % qid("chapter:" + title))
    lines.append('\tgroup: ""')
    lines.append('\ticon: "%s"' % icon)
    lines.append('\tdefault_quest_shape: ""')
    lines.append('\tfilename: "%s"' % fname)
    lines.append('\ttitle: "%s"' % esc(title))
    lines.append('\tsubtitle: ["%s"]' % esc(subtitle))
    lines.append('\torder_index: %d' % idx)
    lines.append('\tquests: [')

    prev = None
    for (x, y, qtitle, desc, tasks, rewards) in quests:
        this = qid("quest:%s:%s" % (title, qtitle))
        lines.append('\t\t{')
        lines.append('\t\t\tx: %.1fd' % x)
        lines.append('\t\t\ty: %.1fd' % y)
        lines.append('\t\t\tid: "%s"' % this)
        lines.append('\t\t\ttitle: "%s"' % esc(qtitle))
        lines.append('\t\t\tdescription: %s' % snbt_strlist(desc))
        if prev:
            lines.append('\t\t\tdependencies: ["%s"]' % prev)
        lines.append('\t\t\ttasks: [')
        lines.append(",\n".join(
            emit_task(t, "task:%s:%s:%d" % (title, qtitle, i))
            for i, t in enumerate(tasks)))
        lines.append('\t\t\t]')
        lines.append('\t\t\trewards: [')
        lines.append(",\n".join(
            emit_reward(r, "reward:%s:%s:%d" % (title, qtitle, i))
            for i, r in enumerate(rewards)))
        lines.append('\t\t\t]')
        lines.append('\t\t}')
        prev = this

    lines.append('\t]')
    lines.append('}')
    return fname, "\n".join(lines) + "\n"


DATA = """{
	default_reward_team: false
	default_team_consume_items: false
	default_quest_disable_jei: false
	emergency_items_cooldown: 300
	drop_loot_crates: false
	disable_gui: false
	grid_scale: 0.5d
	pause_game: false
	lock_message: ""
}
"""

GROUPS = """{
	chapter_groups: [ ]
}
"""


def main():
    base = os.path.join("config", "ftbquests", "quests")
    chdir = os.path.join(base, "chapters")
    os.makedirs(chdir, exist_ok=True)

    with open(os.path.join(base, "data.snbt"), "w") as f:
        f.write(DATA)
    with open(os.path.join(base, "chapter_groups.snbt"), "w") as f:
        f.write(GROUPS)

    for i, (title, subtitle, icon, quests) in enumerate(CHAPTERS):
        fname, body = emit_chapter(i, title, subtitle, icon, quests)
        with open(os.path.join(chdir, fname + ".snbt"), "w") as f:
            f.write(body)
        print("%-14s %2d quests" % (fname, len(quests)))

    print("\nwrote %d chapters to %s" % (len(CHAPTERS), chdir))


if __name__ == "__main__":
    main()

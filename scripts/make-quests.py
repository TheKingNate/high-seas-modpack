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


# FTB Quests 2001.4.22 registers far more task types than this generator used to
# emit. These are the ones that let an exploration quest verify itself instead of
# being a checkmark the player ticks by hand. Field names are read from the jar's
# writeData(): StructureTask->"structure", BiomeTask->"biome",
# AdvancementTask->"advancement"+"criterion", StatTask->"stat"+"value".
#
# NOTE: a quest requires ALL of its tasks, so "any one of several" must be a TAG
# (leading #), never several tasks.

def t_structure(structure):
    """structure id, or #tag to accept any structure in that tag."""
    return {"type": "structure", "structure": structure}


def t_biome(biome):
    """biome id, or #tag."""
    return {"type": "biome", "biome": biome}


def t_advancement(advancement, criterion="-"):
    return {"type": "advancement", "advancement": advancement, "criterion": criterion}


def t_stat(stat, count=1):
    # StatTask.value is an int, unlike KillTask.value which is a long.
    return {"type": "stat", "stat": stat, "value": count}


def r_xp(n):
    return {"type": "xp", "xp": n}


def r_item(item, count=1):
    return {"type": "item", "item": item, "count": count}


# SimplySkills is the only thing in the pack that defines Puffish Skills
# categories, and "tree" is the ONLY one unlocked by default; the other nine are
# specialisations the player unlocks later. The questline used to award to
# "combat" and "mining", which do not exist at all - every reward silently failed.
#
# "tree" also has spent_points_limit 42, and the questline was handing out 193.
# Points are therefore stored as raw WEIGHTS here and scaled to the budget at
# emit time, so adding quests re-divides the same pot instead of overflowing it.
# The tree category caps at 42 spent points (simplyskills tree/category.json) AND
# grants points from leveling (experience.json: 8*level+13 per level, plus kill
# sources). So the questline must NOT consume the whole 42 or playing the game
# earns nothing. This is the share quests contribute; the rest is earned.
# Tune this one number to make quest rewards more or less generous.
SKILL_POINT_BUDGET = 20          # of the 42-point tree cap


def r_skill(n, cat="tree"):
    return {"type": "command", "_pts": n, "_cat": cat, "player_command": False}


_skill_award = {}


def scale_skill_rewards():
    """Distribute SKILL_POINT_BUDGET across quests by largest remainder.

    Proportional scaling plus rounding put every award on the wrong side of a
    cliff - six of eleven chapters ended up with nothing. Largest-remainder
    (Hare quota) hands out exactly the budget and gives the leftovers to the
    quests with the strongest claim, so the spread follows the original weights.
    """
    items = [(ch, q, r["_pts"])
             for ch, _, _, qs in CHAPTERS
             for (_, _, q, _, _, rewards) in qs
             for r in rewards if "_pts" in r]
    raw = sum(w for _, _, w in items)
    if not raw:
        return 0
    base = {(ch, q): 0 for ch, q, _ in items}

    # Reserve one point for each chapter's most significant quest first. Pure
    # proportional allocation left four chapters with nothing, because it was
    # faithfully reproducing weights that were only ever guesses.
    reserved = 0
    for ch in dict.fromkeys(c for c, _, _ in items):
        best = max((t for t in items if t[0] == ch), key=lambda t: t[2])
        base[(best[0], best[1])] = 1
        reserved += 1

    # Distribute what's left by largest remainder, weighted as before.
    rest = SKILL_POINT_BUDGET - reserved
    if rest > 0:
        quota = [(ch, q, w * rest / raw) for ch, q, w in items]
        for ch, q, v in quota:
            base[(ch, q)] += int(v)
        left = SKILL_POINT_BUDGET - sum(base.values())
        for ch, q, v in sorted(quota, key=lambda t: -(t[2] - int(t[2])))[:max(0, left)]:
            base[(ch, q)] += 1
    _skill_award.update(base)
    return raw


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
   [r_xp(40), r_skill(2)]),
  (2, 0, "Something That Moves",
   ["Build a powered contraption."],
   [t_check("Build a working contraption")],
   [r_xp(50), r_skill(2)]),
  (4, 0, "First Current",
   ["Craft a Powah generator -- Furnator, Magmator or Solar Panel."],
   [t_check("Craft a Powah generator")],
   [r_xp(50), r_skill(2)]),
  (6, 0, "Storage",
   ["Craft a Powah Energy Cell."],
   [t_check("Craft an Energy Cell")],
   [r_xp(60), r_skill(3)]),
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
   [r_xp(40), r_skill(2)]),
  (2, 0, "Controller",
   ["Craft an ME Controller."],
   [t_check("Craft an ME Controller")],
   [r_xp(100), r_skill(4)]),
  (4, 0, "Wireless",
   ["Craft a wireless terminal."],
   [t_check("Craft a wireless terminal")],
   [r_xp(80), r_skill(3)]),
  (6, 0, "Autocraft",
   ["Autocraft something with more than one step."],
   [t_check("Autocraft a multi-step recipe")],
   [r_xp(150), r_skill(6)]),
  (8, 0, "Reactor",
   ["Build a Powah reactor."],
   [t_check("Build a Powah reactor")],
   [r_xp(200), r_skill(8)]),
  (10, 0, "Grid",
   ["Move power across a distance with Flux Networks."],
   [t_check("Move power with Flux Networks")],
   [r_xp(120), r_skill(5)]),
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
 ("Airships", "The pack's whole point", "vs_clockwork:propeller_blade", [
  (0, 0, "Lift",
   ["Craft four Balloons.", "",
    "Eureka balloons are the cheapest way off the water."],
   [t_item("vs_eureka:balloon", 4)],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Trim The Boat",
   ["Craft a Ballast.", "",
    "Balloons push up. Ballast argues back. You want both."],
   [t_item("vs_eureka:ballast")],
   [r_xp(40), r_skill(2)]),
  (2, -2, "Cheap Buoyancy",
   ["Craft sixteen Floaters.", "",
    "Bulk lift for a hull that isn't worth balloons."],
   [t_item("vs_eureka:floater", 16)],
   [r_xp(40), r_skill(2)]),
  (4, 0, "Hold Her Still",
   ["Craft an Anchor."],
   [t_item("vs_eureka:anchor")],
   [r_xp(40), r_skill(2)]),
  (6, 0, "Physics Infuser",
   ["Craft a Physics Infuser.", "",
    "Clockwork starts here. Everything below needs one."],
   [t_item("vs_clockwork:physics_infuser")],
   [r_xp(80), r_skill(4)]),
  (8, 0, "First Rotor",
   ["Craft a Jury-rigged Propeller Bearing and four Blades."],
   [t_item("vs_clockwork:juryrigged_propeller_bearing"),
    t_item("vs_clockwork:propeller_blade", 4)],
   [r_xp(100), r_skill(5)]),
  (10, 0, "Proper Rotor",
   ["Craft a Brass Propeller Bearing and four Wide Blades.", "",
    "More bite per rotation. Costs more brass."],
   [t_item("vs_clockwork:brass_propeller_bearing"),
    t_item("vs_clockwork:wide_propeller_blade", 4)],
   [r_xp(120), r_skill(5)]),
  (10, -2, "Instruments",
   ["Craft an Altimeter and a Gyro.", "",
    "Knowing which way is up stops being obvious very quickly."],
   [t_item("vs_clockwork:alt_meter"), t_item("vs_clockwork:gyro")],
   [r_xp(80), r_skill(4)]),
  (12, 0, "Controls",
   ["Craft a Blade Controller and a Command Seat."],
   [t_item("vs_clockwork:blade_controller"), t_item("vs_clockwork:command_seat")],
   [r_xp(120), r_skill(5)]),
  (14, 0, "Power",
   ["Craft a Combustion Engine."],
   [t_item("vs_clockwork:combustion_engine")],
   [r_xp(140), r_skill(6)]),
  (16, 0, "Aeronaut",
   ["Craft a pair of Aeronaut Goggles."],
   [t_item("vs_clockwork:aeronaut_goggles")],
   [r_xp(100), r_skill(4)]),
  (18, 0, "Take To The Air",
   ["Assemble an airship and fly it.", "",
    "Nothing can verify this one. On your honour."],
   [t_check("Fly an airship")],
   [r_xp(300), r_skill(10)]),
 ]),

 ("Ordnance", "Guns, and things to put in them", "createbigcannons:he_shell", [
  (0, 0, "The Foundry",
   ["Craft a Basin Foundry Lid.", "",
    "Cannons are cast, not crafted. This melts the metal."],
   [t_item("createbigcannons:basin_foundry_lid")],
   [r_xp(60), r_skill(3)]),
  (2, 0, "Sand",
   ["Gather eight Casting Sand."],
   [t_item("createbigcannons:casting_sand", 8)],
   [r_xp(40), r_skill(2)]),
  (4, 0, "First Casting",
   ["Cast a Cast Iron Cannon Barrel."],
   [t_item("createbigcannons:cast_iron_cannon_barrel")],
   [r_xp(100), r_skill(4)]),
  (6, 0, "Bore It Out",
   ["Craft a Cannon Drill.", "",
    "It needs water as well as rotation, and its speed must",
    "match the lathe."],
   [t_item("createbigcannons:cannon_drill")],
   [r_xp(100), r_skill(4)]),
  (8, 0, "A Complete Gun",
   ["Cast a chamber and a cannon end.", "",
    "Barrel, chamber, end. The end is the sealed rear, not the muzzle."],
   [t_item("createbigcannons:cast_iron_cannon_chamber"),
    t_item("createbigcannons:cast_iron_cannon_end")],
   [r_xp(120), r_skill(5)]),
  (10, 0, "Mount It",
   ["Craft a Cannon Mount.", "",
    "Power the hammer face to assemble. Power the lit face to fire."],
   [t_item("createbigcannons:cannon_mount")],
   [r_xp(120), r_skill(5)]),
  (12, 0, "Powder And Ram",
   ["Craft eight Powder Charges and a Ram Rod.", "",
    "Cast iron takes two charges. A third bursts it."],
   [t_item("createbigcannons:powder_charge", 8),
    t_item("createbigcannons:ram_rod")],
   [r_xp(100), r_skill(4)]),
  (14, 0, "Shells",
   ["Craft four HE and four AP shells."],
   [t_item("createbigcannons:he_shell", 4), t_item("createbigcannons:ap_shell", 4)],
   [r_xp(140), r_skill(6)]),
  (16, 0, "Mark One",
   ["Craft an HE Shell Mk.I and an AP Shell Mk.I.", "",
    "Needs two charges. A cast iron gun will fire these."],
   [t_item("salvage_ordnance:he_shell_mk1"), t_item("salvage_ordnance:ap_shell_mk1")],
   [r_xp(160), r_skill(6)]),
  (18, 0, "Bronze Founding",
   ["Cast a Bronze Cannon Barrel and a Bronze Cannon End.", "",
    "Bronze takes four charges and up to six barrels."],
   [t_item("createbigcannons:bronze_cannon_barrel"),
    t_item("createbigcannons:bronze_cannon_end")],
   [r_xp(180), r_skill(7)]),
  (20, 0, "Mark Two",
   ["Craft an HE Shell Mk.II and an AP Shell Mk.II.", "",
    "Three charges. Cast iron cannot fire these."],
   [t_item("salvage_ordnance:he_shell_mk2"), t_item("salvage_ordnance:ap_shell_mk2")],
   [r_xp(200), r_skill(8)]),
  (22, 0, "Built Up",
   ["Build a Steel Cannon Barrel and a Steel Screw Breech.", "",
    "Steel cannons are layered and heat-treated, not cast.",
    "There is no steel cannon end - steel needs a breech."],
   [t_item("createbigcannons:steel_cannon_barrel"),
    t_item("createbigcannons:steel_screw_breech")],
   [r_xp(250), r_skill(9)]),
  (24, 0, "Mark Three",
   ["Craft an HE Shell Mk.III and an AP Shell Mk.III.", "",
    "Five charges. Steel or nethersteel only."],
   [t_item("salvage_ordnance:he_shell_mk3"), t_item("salvage_ordnance:ap_shell_mk3")],
   [r_xp(300), r_skill(10)]),
  (26, 0, "Sink Something",
   ["Put a Mk.III through someone else's hull.", "",
    "Nothing can verify this one."],
   [t_check("Sink a ship")],
   [r_xp(350), r_skill(12)]),
 ]),

 ("The Aether", "Up, not down", "aether:ambrosium_shard", [
  (0, 0, "Above The Clouds",
   ["Reach the Aether.", "",
    "Glowstone frame, water bucket."],
   [t_dim("aether:the_aether")],
   [r_xp(150), r_skill(6)]),
  (2, 0, "Ground Stone",
   ["Gather sixteen Holystone."],
   [t_item("aether:holystone", 16)],
   [r_xp(60), r_skill(3)]),
  (4, 0, "First Fuel",
   ["Gather four Ambrosium Shards."],
   [t_item("aether:ambrosium_shard", 4)],
   [r_xp(60), r_skill(3)]),
  (6, 0, "Skyroot",
   ["Gather eight Skyroot Logs and craft a Skyroot Pickaxe."],
   [t_item("aether:skyroot_log", 8), t_item("aether:skyroot_pickaxe")],
   [r_xp(80), r_skill(3)]),
  (8, 0, "Harder Stone",
   ["Craft a Holystone Pickaxe."],
   [t_item("aether:holystone_pickaxe")],
   [r_xp(80), r_skill(3)]),
  (10, 0, "Zanite",
   ["Mine four Zanite Gemstones and craft a Zanite Pickaxe."],
   [t_item("aether:zanite_gemstone", 4), t_item("aether:zanite_pickaxe")],
   [r_xp(120), r_skill(5)]),
  (10, -2, "Amber",
   ["Find Golden Amber.", "",
    "It hides in Golden Oak. You need a Zanite axe to get it out."],
   [t_item("aether:golden_amber")],
   [r_xp(100), r_skill(4)]),
  (12, 0, "A Mount",
   ["Obtain a Blue Moa Egg."],
   [t_item("aether:blue_moa_egg")],
   [r_xp(120), r_skill(5)]),
  (14, 0, "Bronze Dungeon",
   ["Find a Bronze Key."],
   [t_item("aether:bronze_dungeon_key")],
   [r_xp(160), r_skill(6)]),
  (16, 0, "The Slider",
   ["Kill the Slider."],
   [t_kill("aether:slider")],
   [r_xp(300), r_skill(10)]),
  (18, 0, "Gravitite",
   ["Craft a Gravitite Pickaxe."],
   [t_item("aether:gravitite_pickaxe")],
   [r_xp(250), r_skill(9)]),
  (20, 0, "The Valkyrie Queen",
   ["Kill the Valkyrie Queen."],
   [t_kill("aether:valkyrie_queen")],
   [r_xp(400), r_skill(12)]),
 ]),
]

# --- progression graph ----------------------------------------------
#
# Every chapter head used to be unlocked at world start, including "Beyond -
# Endgame", while Shipwright's subtitle claimed "Everything else is gated
# behind this" and gated nothing. This is that claim made real.
#
# Content-addressed ids are what make this expressible: a chapter can point at
# another chapter's quest by name, without anyone needing to know its id.
CHAPTER_GATES = {
    # chapter        must first complete   in chapter
    "Shipwright":   ("A Way Back",         "Castaway"),
    "Provision":    ("Ashore",             "Castaway"),
    "The Forge":    ("A Way Back",         "Castaway"),
    "Arcana":       ("A Way Back",         "Castaway"),
    "Charting":     ("Blue Water",         "Shipwright"),
    "Salvage":      ("Blue Water",         "Shipwright"),
    "Below":        ("Three Coasts",       "Charting"),
    "The Deep":     ("The Monument",       "Below"),
    "The Network":  ("First Current",      "The Forge"),
    # a list gates on several prerequisites at once
    "Beyond":       [("Reactor", "The Network"), ("Specialise", "Arcana")],
    "Airships":     [("Blue Water", "Shipwright"), ("First Current", "The Forge")],
    "Ordnance":     [("Powder And Shot", "Salvage"), ("First Current", "The Forge")],
    "The Aether":   ("Three Coasts", "Charting"),
}

# Chapters the pack itself calls optional. Marking the quests optional stops them
# counting toward completion and greys the lock icon instead of implying a wall.
OPTIONAL_CHAPTERS = {"The Deep"}

# Chapter groups - the sidebar was one flat list of 11 chapters.
CHAPTER_GROUPS = [
    ("Ashore",     ["Castaway", "Provision"]),
    ("The Sea",    ["Shipwright", "Charting", "Below", "The Deep", "Salvage"]),
    ("Industry",   ["The Forge", "The Network", "Ordnance"]),
    ("Aloft",      ["Airships", "The Aether"]),
    ("Elsewhere",  ["Arcana", "Beyond"]),
]
GROUP_OF = {c: g for g, cs in CHAPTER_GROUPS for c in cs}


# --- verified task overrides ----------------------------------------
#
# 47 of 56 tasks were "checkmark" - the player ticks them by hand and the game
# verifies nothing. These ids were resolved from the installed jars and then
# adversarially re-verified; only ids a second pass could not refute are here.
#
# Quests absent from this table keep their inline checkmark ON PURPOSE - see
# CHECKMARK_REASONS below. An unresolvable item id does not error at load, it
# renders a Missing Item placeholder in a permanently uncompletable quest, so
# guessing is worse than leaving a checkmark.
TASKS = {
    ("Castaway", "Something To Carry It In"): [t_item("travelersbackpack:standard")],
    ("Castaway", "Know Where You Are"):       [t_item("explorerscompass:explorerscompass")],
    ("Castaway", "A Way Back"):               [t_item("waystones:waystone")],

    ("Shipwright", "The Helm"):               [t_item("vs_eureka:oak_ship_helm")],
    ("Shipwright", "Under Steam"):            [t_item("vs_eureka:engine")],

    ("Charting", "Ruins"):                    [t_structure("structory:ruin_grassy")],
    ("Charting", "Somewhere Inhabited"):      [t_structure("#towns_and_towers:town")],
    ("Charting", "Three Coasts"):             [t_biome("#minecraft:is_jungle"),
                                               t_biome("#minecraft:is_badlands"),
                                               t_biome("#minecraft:is_deep_ocean")],
    ("Charting", "Underground"):              [t_structure("#betterdungeons:better_dungeons")],
    ("Charting", "The Board"):                [t_item("bountiful:bountyboard")],

    ("The Forge", "Kinetics"):                [t_item("create:mechanical_press")],
    ("The Forge", "Something That Moves"):    [t_advancement("create:windmill", "0")],
    ("The Forge", "First Current"):           [t_item("powah:furnator_starter")],
    ("The Forge", "Storage"):                 [t_item("powah:energy_cell_starter")],

    ("Below", "Lungs"):                       [t_item("hybrid_aquatic:diving_helmet"),
                                               t_item("hybrid_aquatic:diving_suit"),
                                               t_item("hybrid_aquatic:diving_leggings"),
                                               t_item("hybrid_aquatic:diving_boots")],
    ("Below", "Sunken"):                      [t_structure("#hopo:underwaterstructure")],

    ("Salvage", "Powder And Shot"):           [t_item("supplementaries:cannon")],
    ("Salvage", "Silence A Gun"):             [t_kill("pirates:pirate", 3)],
    ("Salvage", "Dead In The Water"):         [t_kill("pirates:pirate", 8)],
    ("Salvage", "Wrecks"):                    [t_structure("minecraft:shipwreck")],

    ("The Deep", "Ship Graveyard"):           [t_biome("#aquamirae:ice_maze")],
    ("The Deep", "Something In The Dark"):    [t_kill("aquamirae:anglerfish")],
    ("The Deep", "Cornelia"):                 [t_kill("aquamirae:captain_cornelia")],
    ("The Deep", "Deep City"):                [t_structure("hopo:underwater/underwater_city")],

    ("The Network", "Certus"):                [t_item("ae2:certus_quartz_crystal", 16)],
    ("The Network", "Controller"):            [t_item("ae2:controller")],
    ("The Network", "Wireless"):              [t_item("ae2:wireless_terminal")],
    ("The Network", "Reactor"):               [t_item("powah:reactor_starter", 36)],
    ("The Network", "Grid"):                  [t_item("fluxnetworks:flux_plug"),
                                               t_item("fluxnetworks:flux_point")],

    ("Arcana", "Binding Table"):              [t_item("spell_engine:spell_binding")],
    ("Arcana", "Ammunition"):                 [t_item("runes:fire_stone", 8)],
    ("Arcana", "Wand"):                       [t_item("wizards:wand_novice")],
    ("Arcana", "First Spell"):                [t_item("wizards:arcane_spell_book")],
    ("Arcana", "Tower"):                      [t_structure("structory_towers:wizard_tower")],

    ("Provision", "The Pot"):                 [t_item("farmersdelight:cooking_pot")],
    ("Provision", "Cook"):                    [t_item("farmersdelight:vegetable_soup"),
                                               t_item("farmersdelight:chicken_soup"),
                                               t_item("farmersdelight:beef_stew"),
                                               t_item("farmersdelight:fish_stew"),
                                               t_item("farmersdelight:pumpkin_soup")],
    ("Provision", "Harvest"):                 [t_item("croptopia:" + c) for c in
                                               ("tomato", "corn", "onion", "strawberry", "blueberry",
                                                "cucumber", "lettuce", "pepper", "grape", "rice")],
    ("Provision", "A Full Net"):              [t_item("fishofthieves:" + f) for f in
                                               ("splashtail", "pondie", "islehopper",
                                                "ancientscale", "plentifin", "wildsplash")],

    ("Beyond", "Incendium"):                  [t_structure("incendium:forbidden_castle")],
    ("Beyond", "Ruins at the Edge"):          [t_structure("structory_towers:end/end_tower")],
    ("Beyond", "Something Enormous"):         [t_kill("bosses_of_mass_destruction:obsidilith")],
}

# Deliberately still checkmarks. Recorded so nobody "fixes" one by guessing.
CHECKMARK_REASONS = {
    ("Shipwright", "Assemble"):     "VS2 ships are not entities; nothing observes assembly",
    ("Shipwright", "Blue Water"):   "riding a ship ticks no stat; there is no distance task",
    ("Salvage", "Broadside"):       "'mounted on a ship' is runtime state with no id",
    ("Salvage", "Plunder"):         "barrel loot is vanilla or craftable; no unique drop",
    ("The Network", "Autocraft"):   "no AE2 advancement or item proves autocrafting",
    ("Arcana", "Specialise"):       "no item or advancement proves a specialisation",
    ("Provision", "Out Of Season"): "Fabric Seasons registers no items, blocks or entities",
}

# Descriptions the new tasks make inaccurate.
RETEXT = {
    ("Charting", "Three Coasts"): ["Visit a jungle, a badlands, and a deep ocean."],
    ("Charting", "Underground"):  ["Find your way into a YUNG's dungeon."],
    ("Charting", "The Board"):    ["Craft a Bounty Board.", "",
                                   "Bounties are taken and turned in here."],
    ("The Deep", "Deep City"):    ["Find a Hopo deep ocean city."],

    # An item task proves you obtained it, not that you placed or mounted it.
    ("Castaway", "A Way Back"):   ["Craft a Waystone, then place it.", "",
                                   "Do not put one on a ship. It will misbehave."],
    # vs_eureka:ship_helms is a real item tag, but no item-filter provider is
    # installed, so a task can only name one wood. Say which.
    ("Shipwright", "The Helm"):   ["Craft an Oak Ship Helm.",
                                   "This is the single most important block in the pack.", "",
                                   "Other woods work in-game; the quest checks oak."],
    ("Shipwright", "Under Steam"):["Craft a Ship Engine.", "",
                                   "Balloons give you lift. Engines give you somewhere to go."],
    # Structory ships no structure tag, so this names one ruin of the seven.
    ("Charting", "Ruins"):        ["Find a grassy Structory ruin."],
}


# --- emit -----------------------------------------------------------

def snbt_strlist(lines):
    return "[" + ", ".join('"%s"' % esc(l) for l in lines) + "]"


# Which numeric task fields the mod stores as longs, read from each task class:
#   KillTask.value  -> long      StatTask.value -> int
#   ItemTask.count  -> long (putLong)
# Reading an int literal into a long field works, but emitting what FTB Quests
# itself writes keeps a round-trip through the in-game editor byte-identical.
LONG_FIELDS = {("value", "kill"), ("count", "item")}


def emit_task(t, key):
    out = ['\t\t\t\t{']
    out.append('\t\t\t\t\tid: "%s"' % qid(key))
    for k, v in t.items():
        if isinstance(v, str):
            out.append('\t\t\t\t\t%s: "%s"' % (k, esc(v)))
        elif isinstance(v, bool):
            out.append('\t\t\t\t\t%s: %s' % (k, "true" if v else "false"))
        elif (k, t.get("type")) in LONG_FIELDS:
            out.append('\t\t\t\t\t%s: %dL' % (k, v))
        else:
            out.append('\t\t\t\t\t%s: %d' % (k, v))
    out.append('\t\t\t\t}')
    return "\n".join(out)


def emit_reward(r, key, ctx_chapter=None, ctx_quest=None):
    if "_pts" in r:                      # skill reward: pre-allocated by budget
        n = _skill_award.get((ctx_chapter, ctx_quest), 0)
        if n < 1:
            return None                  # budget went to quests with a stronger claim

        r = {"type": "command", "title": "%d Skill Point%s" % (n, "" if n == 1 else "s"),
             "command": "/puffish_skills points add @p %s %d" % (r["_cat"], n),
             "player_command": False}
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
    lines.append('\tgroup: "%s"' % (qid("group:" + GROUP_OF[title]) if title in GROUP_OF else ""))
    lines.append('\ticon: "%s"' % icon)
    lines.append('\tdefault_quest_shape: ""')
    lines.append('\tfilename: "%s"' % fname)
    lines.append('\ttitle: "%s"' % esc(title))
    lines.append('\tsubtitle: ["%s"]' % esc(subtitle))
    lines.append('\torder_index: %d' % idx)
    lines.append('\tquests: [')

    prev = None
    for (x, y, qtitle, desc, tasks, rewards) in quests:
        tasks = TASKS.get((title, qtitle), tasks)
        desc = RETEXT.get((title, qtitle), desc)
        this = qid("quest:%s:%s" % (title, qtitle))
        lines.append('\t\t{')
        lines.append('\t\t\tx: %.1fd' % x)
        lines.append('\t\t\ty: %.1fd' % y)
        lines.append('\t\t\tid: "%s"' % this)
        lines.append('\t\t\ttitle: "%s"' % esc(qtitle))
        lines.append('\t\t\tdescription: %s' % snbt_strlist(desc))
        deps = [prev] if prev else []
        if not deps and title in CHAPTER_GATES:
            g = CHAPTER_GATES[title]
            if isinstance(g, tuple):
                g = [g]
            deps = [qid("quest:%s:%s" % (gc, gq)) for gq, gc in g]
        if deps:
            lines.append('\t\t\tdependencies: [%s]'
                         % ", ".join('"%s"' % d for d in deps))
            if len(deps) > 1:
                # any ONE prerequisite chapter is enough to open this one
                lines.append('\t\t\tmin_required_dependencies: 1')
        if title in OPTIONAL_CHAPTERS:
            lines.append('\t\t\toptional: true')
        lines.append('\t\t\ttasks: [')
        lines.append(",\n".join(
            emit_task(t, "task:%s:%s:%d" % (title, qtitle, i))
            for i, t in enumerate(tasks)))
        lines.append('\t\t\t]')
        lines.append('\t\t\trewards: [')
        emitted = [e for e in (emit_reward(r, "reward:%s:%s:%d" % (title, qtitle, i), title, qtitle)
                               for i, r in enumerate(rewards)) if e]
        lines.append(",\n".join(emitted))
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


def emit_groups():
    out = ["{", "\tchapter_groups: ["]
    for i, (name, _) in enumerate(CHAPTER_GROUPS):
        out += ["\t\t{", '\t\t\tid: "%s"' % qid("group:" + name),
                '\t\t\ttitle: "%s"' % esc(name), "\t\t}"]
    out += ["\t]", "}", ""]
    return "\n".join(out)


def main():
    raw = scale_skill_rewards()
    base = os.path.join("config", "ftbquests", "quests")
    chdir = os.path.join(base, "chapters")
    os.makedirs(chdir, exist_ok=True)

    with open(os.path.join(base, "data.snbt"), "w") as f:
        f.write(DATA)
    with open(os.path.join(base, "chapter_groups.snbt"), "w") as f:
        f.write(emit_groups())

    for i, (title, subtitle, icon, quests) in enumerate(CHAPTERS):
        fname, body = emit_chapter(i, title, subtitle, icon, quests)
        with open(os.path.join(chdir, fname + ".snbt"), "w") as f:
            f.write(body)
        print("%-14s %2d quests" % (fname, len(quests)))

    print("\nwrote %d chapters to %s" % (len(CHAPTERS), chdir))


if __name__ == "__main__":
    main()

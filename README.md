# Salvage

A Minecraft **1.20.1 Fabric** modpack. Version **1.0.0**, 160 mods.

Ships that actually sail, pirates that shoot back, and enough
tech and magic to keep a small group busy for months.

---

## What it is

You start on a beach. You build a hull, mount a helm, and the sea
becomes the road. Ocean waves physically lift and roll your ship.
Hostile crewed pirate vessels sail the open water with working
cannons -- kill the cannoneer to silence a gun, kill the helmsman
to stop the ship, then board it and take the cargo.

Underneath that there's a full tech stack (Applied Energistics,
Create, Powah reactors, Flux Networks), a light magic system,
skill trees, seasons, farming, and sixteen structure mods' worth
of things to find.

It's built for a small co-op group where people play differently:
some explore and fight, some build and automate. Both halves have
depth, and there's a quest book with 11 chapters if you want
direction.

---

## Install

**Windows** -- download and right-click -> Run with PowerShell:

    install/install-salvage.ps1

**macOS / Linux** -- download, then in a terminal:

    chmod +x install-salvage.sh && ./install-salvage.sh

The installer finds or installs Prism Launcher, builds the
instance, sets memory based on your RAM, and wires up
auto-updating. Then open Prism, sign in, and launch.

First launch downloads all the mods. After that the pack updates
itself every time you play -- you never re-download anything.

---

## Joining the server

Try to connect once. You'll be told you aren't whitelisted --
that's expected, and it's how the admin gets your exact username.
Say you tried and you'll be added.

Server address: ask.

---

## Notes

**Don't put a Waystone on a ship.** Long-distance teleport to a
waystone on a moving vessel misbehaves.

**Start small.** Large hulls ride the waves gently. A raft shows
you the swell; a galleon barely moves.

**Shaders** are bundled. If they're off: Options -> Video
Settings -> Shader Packs -> pick the Complementary +
EuphoriaPatches entry.

**Distant Horizons** is included. Ships fade out at long range --
that's a known conflict with the physics mod, not a broken
install.

---

## For the maintainer

    ./push.sh "message"        # export + commit + push to main
    ./release.sh patch "msg"   # bump version, tag, promote to release
    ./make-readme.sh           # regenerate this file

Clients and the server follow the `release` branch. Work on
`main`, promote when stable.

On the server:

    ./update.sh     # pull changes, restart only if mods changed
    ./restart.sh
    ./console.sh    # attach to the server console
    ./pending.sh    # names that tried to join and got rejected

---

## Mod list

<details>
<summary>160 mods</summary>

- [EMF] Entity Model Features [Fabric & Forge]
- [ETF] Entity Texture Features - [Fabric & Forge]
- 3D Skin Layers
- Advancement Plaques [Fabric]
- AE2 Things
- AmbientSounds 6
- Amendments
- AppleSkin
- Applied Energistics 2
- Applied Energistics 2 Wireless Terminals
- Aquamirae
- Architectury API
- AzureLib
- AzureLib Armor
- Balm
- Better Advancements
- Better Combat
- Biolith
- Bosses of Mass Destruction
- Bountiful
- Camera Overhaul
- Cardinal Components API
- Chunky (Fabric)
- Cloth Config API
- Continuity
- Controlling
- Create Crafts & Additions
- Create Fabric
- Create: Numismatics
- CreativeCore
- Cristel Lib
- Croptopia
- Cupboard
- Deeper Oceans
- Distant Horizons
- Easy Anvils
- Easy Magic
- Eating Animation
- Enhanced Block Entities
- Entity Culling
- EpheroLib
- Essential Commands
- Essential Mod
- Euphoria Patches
- Explorer's Compass
- Fabric API
- Fabric Language Kotlin
- Fabric Seasons
- Farmer's Delight Refabricated
- FerriteCore
- First-person Model
- Fish of Thieves
- Flux Networks [Fabric]
- Footprint
- Forge Config API Port
- Fragmentum
- FTB Chunks (Fabric)
- FTB Library (Fabric)
- FTB Quests (Fabric)
- FTB Teams (Fabric)
- Fzzy Config
- Geckolib
- Global Packs
- Grappling Hook: Restitched
- Hopo Better Underwater Ruins
- HT's TreeChop
- Hybrid Aquatic
- Iceberg [Fabric]
- ImmediatelyFast
- Incendium Legacy
- Indium
- Inventory Particles
- Iris Shaders
- Jade 🔍
- Jade VS
- Kambrik
- Krypton
- LambDynamicLights - Dynamic Lights
- Lithium (Fabric/NeoForge)
- Lithostitched
- Loot Integrations
- Loot Integrations: Moog's Voyager, Soaring, End & Nether Structures
- Lost Trinkets Renewed
- LuckPerms
- Make Bubbles Pop
- MCA Capitals | A Monarchy Mod for MCA Reborn
- MCA Reborn
- MEGA Cells
- MES - Moog's End Structures
- MMV - Moog's Missing Villages
- MNS - Moog's Nether Structures
- Mob Player Animator
- Mobbility [Addon: Spell Engine]
- Mobbility [Core]
- Mod Menu
- ModernFix
- Moog's Structure Lib (moogs_structures)
- Moonlight Lib
- MossyLib
- Mouse Tweaks
- MSS - Moog's Soaring Structures
- MTR - Moog's Temples Reimagined
- MVS - Moog's Voyager Structures
- Naturalist
- Nature's Compass
- Noisium
- Not Enough Animations
- Nullscape
- oωo (owo-lib)
- Ore Vein Miner
- Particle Rain
- playerAnimator
- Polytone
- Powah!
- Presence Footsteps
- Pufferfish's Attributes
- Pufferfish's Skills
- Puzzles Lib
- Reese's Sodium Options
- Roughly Enough Items Fabric/Forge/NeoForge (REI)
- Runes
- Searchables
- Ship In A Bottle
- Simple Voice Chat
- Simply Skills
- Sodium
- Sodium Extra
- Sound Physics Remastered
- spark
- Spell Engine
- Spell Power Attributes
- Structory
- Structory: Towers
- Subtle Effects
- Supplementaries
- Tectonic
- Terralith
- Tom's Simple Storage Mod
- Towns and Towers
- Traveler's Backpack
- Trinkets
- Universal Graves
- Valkyrien Pirates
- Valkyrien Sails
- Valkyrien Skies + Supplementaries Cannon Fix
- Valkyrien Skies 2 - Unofficial
- Visuality
- VLib
- VS Safe and Sound
- Wakes
- Waystones
- When Dungeons Arise
- Wizards (RPG Series)
- Xaero's Minimap
- Xaero's World Map
- YetAnotherConfigLib (YACL)
- YUNG's API (Fabric)
- YUNG's Better Desert Temples (Fabric)
- YUNG's Better Dungeons (Fabric)
- YUNG's Better Ocean Monuments (Fabric)

</details>

---

*Every mod belongs to its author. This pack is just a list.*

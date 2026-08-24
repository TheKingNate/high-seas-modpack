# salvage-pirates

Three things the Valkyrien Pirates config cannot do on its own. All verified by
disassembling `pirates-1.20.1-1.9.3-fabric.jar`.

## 1. The sky ship crashed the physics thread

`wreckerideal.nbt` stores its `pirates:motion_invoking_block` with an **empty Properties
compound**; all 13 sea ships store `{armed: true, compat: 2}`. Empty means the block falls
back to its default state, and defaults are the first value of each property -
`BooleanProperty.of("armed")` -> true, `IntProperty.of("compat", 0, 2)` -> 0.

`armed=true, compat=0` takes `MotionInvokingBlockEntity.tick` past the Sails/Eureka
lookupswitch into its default branch, `moveShipForward`:

    rotation.getEulerAnglesZXY(new Vector3d()).normalize().mul(mass * 10.0)

A freshly generated structure ship has identity rotation, so that euler vector is (0,0,0),
JOML's `normalize()` divides by zero, and the force is rebuilt as `(-x, 0.0, -z)` =
`(NaN, 0.0, NaN)` - matching the logged vector exactly, including the literal 0.0 in Y:

    java.lang.IllegalArgumentException: (      NaN  0.000E+0       NaN) is not finite!
        at PhysShipImpl.applyWorldForceToBodyPos
    !!!!!!! VS PHYSICS THREAD CRASHED !!!!!!!

The physics thread does not restart. Everything downstream - multi-second freezes, the game
frame queue backing up, ships never moving - follows from that one line. Setting
`armed=true, compat=2` routes it to `EurekaCompat.moveTowards` instead, and the ship already
carries a `vs_eureka:oak_ship_helm` directly above the block, which is what
`EurekaCompat.checkHelm` tests.

## 2. Flying pirates have no config switch

`should-enable-flying-pirates` is parsed into `Pirates.shouldEnableFlyingPirates` and never
read again - the only two references in the jar are the declaration and the `putstatic`.
The real switch is the `flying_ships` datapack bundled inside the jar, which
`BuiltinPackSourceMixin` never registers (it registers only `eureka_ships`). Lifting it out
here is the only way to turn sky ships on.

`max-ship-blocks` is dead in the same way.

## 3. The crew config was unreachable

`custom-crew-entity-N` / `custom-crew-equipment-N` are read, but only by
`CrewSpawnerBlockEntity.makeCustomCrew(world, N)`, reached only when a crew spawner's
`crew_spawn_type` blockstate is `custom_0..custom_3`. Every spawner in every shipped
structure is `pirate`, `villager` or `skeleton_pirate`, so that path had never executed.
This rewrites ~28% of each ship's `pirate` spawners, spread evenly rather than clustered.

The matching entity and equipment definitions live in `config/pirates/config.acfg`. **Without
that file the defaults apply** - `minecraft:zombie` in `0,0,0,0,0,0` - i.e. naked zombies,
strictly worse than the pirates they replace. The two ship together or not at all.

### Why illagers rather than armoured pirates

`AbstractPirateEntity.initGoals` adds only LookAtEntity, LookAround and Swim. The single
attack goal is `PirateBowAttackGoal`, added by `PirateEntity`, and its `canStart` requires
`isHoldingBow()`. A pirate holding anything else has no attack goal at all and stands and
stares. Melee pressure has to come from a mob that brings its own AI.

One consequence: `AbstractPirateEntity.remove` calls `DisarmUtils.disarm` on the cannon that
pirate was manning, so killing pirates silences a ship. Custom crew are not
`AbstractPirateEntity` and disarm nothing - clearing the deck no longer stops the guns.

Left alone deliberately: `villager` spawners (the prisoners), and both all-`skeleton_pirate`
ships (`the-phantom-leviathan`, `whydah-ghost`).

## Density

`data/pirates_sky/worldgen/structure_set/ships.json` is **192 / 64**, not the author's 26 / 8.

Sea ships are gated to `#pirates:deep_n_warm`; sky ships are `#minecraft:is_overworld` - every
biome - so identical spacing numbers are not comparable densities. The multiplier is Distant
Horizons: both the server and the clients run `enableDistantGeneration = true` with
`lodChunkRenderDistanceRadius = 256` chunks, pre-generating a ~52.7M block^2 disc that nobody
has to travel to. A dev world produced **75 sky ships in 34 minutes** at the author's spacing.

    spacing  26 -> ~304 ships inside DH's disc
    spacing  40 -> ~129
    spacing 128 -> ~13
    spacing 192 -> ~6

## Scope

Structure NBT is baked at generation time, so all of this only affects ships in **newly
generated chunks**. Existing ships keep the crews they were built with.

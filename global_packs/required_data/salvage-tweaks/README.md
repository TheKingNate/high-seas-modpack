# salvage-tweaks

A GlobalPacks datapack holding the pack's own overrides of other mods' data.

## The directory matters, do not move this

It must live in `global_packs/required_data/`. GlobalPacks 19.3.7 writes its own
config to `config/global_packs.toml` and reads only the paths listed there:

    [datapacks]
    required = ["datapacks/", "resourcepacks/", "global_packs/required_data/"]
    optional = ["global_packs/optional_data/"]

`globalpacks/datapacks/` - which is where this pack shipped its datapacks until
2026-08-23 - appears nowhere in that list, so nothing in it ever loaded. That was
not a silent no-op either: BlazeandCave's Advancements Pack had been shipped there
since the pack began and had never once loaded. Verified by reading a live player's
`saves/<world>/advancements/<uuid>.json`, which contained zero `blazeandcave` keys.

GlobalPacks accepts an unzipped folder as readily as a zip: its `IS_VALID_DATA_PACK`
predicate takes any path with a `data/` directory and a `pack.mcmeta` file, so these
ship as plain packwiz-indexed files with no archive to build or host.

## `simplyskills` tree spend cap: 42 -> 70

SimplySkills' `tree` category defines **339 skills** but ships
`spent_points_limit: 42`, so a player unlocks about 12% of it. Points come from
two places: quest rewards, and levelling (`8 * level + 13` XP per point, with
per-chunk anti-farming).

At 42 the pack's 35 chapter capstones would have handed out 35 of the 42 points -
83% of a player's entire build before they had levelled at all, which made the
choose-your-path tension the cap exists to create almost meaningless.

Raised to 70. The 35 capstone points are now exactly half a full build, and the
other half is earned by playing. Only this one field differs from SimplySkills'
original; everything else in the file is copied verbatim so the category keeps
its title, icon, background and connection colours.

The nine class categories (wizard, rogue, berserker, ...) have no
`spent_points_limit` at all and are untouched.

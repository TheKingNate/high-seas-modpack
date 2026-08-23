# salvage-tweaks

A GlobalPacks datapack holding the pack's own overrides of other mods' data.
Loaded from `globalpacks/datapacks/`, which GlobalPacks adds as a pack source;
it handles unzipped folders as well as zips, so these files ship as-is.

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

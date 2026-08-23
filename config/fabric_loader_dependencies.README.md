# Why `fabric_loader_dependencies.json` exists

`rpgsp` 1.0.4 declares `"rpgmana": "=1.0.8.2"`. Fabric enforces a bare/exact
version literally, so the pack refuses to launch against rpgmana 1.0.8.4:

    Mod 'rpgsp' (rpgsp) 1.0.4 requires version 1.0.8.2 of mod 'arch-pgmana'
    (rpgmana), but only the wrong version is present: 1.0.8.4!

**Downgrading rpgmana does not work.** 1.0.8.2 in turn pins `"archon": "0.6.2"`,
also exact, and the pack ships archon 0.8.1. It just moves the crash one link
down the chain.

The pin is an upstream oversight. rpgsp 1.0.4 shipped 2025-03-20, eight months
after rpgmana's final 1.0.8.4 (2024-07-17) - it points backwards past a release
that already existed. Verified at bytecode level: the only signature difference
between the two rpgmana builds is a removed *private* method,
`ManaComponentMixin.getRegenSpeed`. The four classes rpgsp actually references -
`Rpgmana`, `api/ManaInterface`, `api/SpellcostMixinInterface`, `config/ServerConfig` -
are signature-identical.

## Editing this file

The loader accepts **only** `version` and `overrides` as root keys. A `_comment`
key is a hard parse error that aborts launch before any mod loads - which is why
this explanation is in a separate .md file. Operations are `+depends` (add),
`-depends` (remove), `depends` (replace outright).

Validate any change before pushing:

    python3 scripts/check-loader-overrides.py

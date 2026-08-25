# Salvage: build plan

*Written 2026-08-25. Verified against `/Users/joshg/mc/high-seas` @ `4091341` and `/Users/joshg/Dev/Minecraft Website`. Everything marked VERIFIED was read this session; everything else is marked.*

---

## The shape of it

Eight phases. The first three build and ship the app with **zero portal involvement** — if you stop after Phase 2 you have a signed, self-updating desktop app that replaces all three installers, and the portal stays exactly as dead as it is today. That is a complete outcome, not a half-finished one. The portal work (Phases 3–7) is a separate arc that happens to end by feeding the app its config.

Phases 0–5 are entirely Mac-local. Only Phase 6 needs your home network.

The three installers stay live and downloadable through Phase 7. They are retired in Phase 8, by a named event, not by drift.

---

## Load-bearing decisions

| # | Decision | Rejected | Why |
|---|---|---|---|
| D1 | **Tauri v2** | Electron; egui/WinForms; restyle the three natives | Electron ships a Node runtime for a status screen. egui/WinForms is a week of work to look like 2012, and the point is escaping dated. Cost, stated plainly: **`cargo` and `rustup` are both absent from this Mac (VERIFIED)** — this is a new toolchain on your machine. No other blocker found. |
| D2 | **macOS + Windows only. Linux stays on `install/salvage-setup.py` permanently.** | Port Linux too | Tauri on Linux is a ~90 MB webkit2gtk AppImage for a player base that may be zero people. The Python installer is the one of the three that is already a readable program; it becomes the Linux answer and stops being a third copy of the Windows/Mac logic. |
| D3 | **Source at `/Users/joshg/mc/high-seas/app/`, released on `app-v*` tags** | Its own repo; the portal repo | Your scar is *implementations drifting from one document*. `REPAIR-SPEC.md` and `LAUNCHER-SPEC.md` live at `install/`. Putting the one implementation in a different repo from its specification recreates that failure with a git remote in between. The `app-v*` tag prefix keeps `release.sh`'s `v*` tags from firing a two-platform signed build on every mod tweak. |
| D4 | **App updates come from GitHub Releases. Never from the portal.** | Portal serves manifest + bytes; portal serves manifest, GitHub serves bytes | This contradicts one of the research strands and I think the strand is wrong. Routing bug fixes through your house means a tunnel outage is an outage of your ability to fix the app. There is no control worth exercising here — you cannot meaningfully stage a rollout to four people. If you want a kill switch, `minAppVersion` on the config endpoint (Phase 7) already is one, and it fails safe. |
| D5 | **New `app_devices` table + opaque bearer token + a *separate* `requireApp` Fastify guard** | Teach `server/plugins/session.ts` to read `Authorization: Bearer`; reuse the `sessions` table; embedded-webview cookie login | Widening the existing session plugin would instantly make **every** guarded route app-callable with a device token — including the RCON command routes and admin system-config secret reveal. Your own laptop's token would become a full admin credential in a file. Reusing `sessions` means password reset and logout-all silently unpair every player's launcher. Webview login leaves the Rust half — the part that actually launches Prism and runs the repair ladder — unable to authenticate at all. |
| D6 | **Paste-once token now. Device-code pairing is optional polish, later or never.** | Build RFC 8628 pairing first | The app's steady-state code is identical either way — it holds a bearer token. Paste-once is ~130 lines and testable offline; pairing is ~450 and needs browser and app coordinated in one sitting, which is the thing you cannot test well away from home. For four adults, one copy-paste on first run is not a real cost. |
| D7 | **Docker on the home box** | plain node + systemd | Three concrete reasons, not preference: `better-sqlite3` and `@node-rs/argon2` are native and the Dockerfile already solves the build; `release.yml` already publishes the images; and `packages/db/src/paths.ts:12` resolves relative paths via `process.env.INIT_CWD`, which **npm** sets and **systemd does not** — under a bare unit, `DATABASE_PATH=./data/portal.sqlite` silently resolves to a second, empty database. Worst failure mode available. |
| D8 | **Cloudflare Access in front of the tunnel, with a path exception for `/api/app/*`** | Rely on app-level auth alone | This is a dashboard change, not code, and it authenticates before any request reaches 24,431 lines of never-typechecked, never-security-reviewed Node. It is worth more than every code fix in the security gate combined. The path exception must be configured *at the same time* or the app's first request gets an HTML login page instead of JSON. |
| D9 | **Play never blocks on the portal.** | Fetch config on launch | Today three installers work with zero server dependency. The moment the app requires a handshake, a class of "I can't play" exists that never existed. The app caches last-known-good config; auth failure degrades to *launch with cached config, show a warning*. This must be enforced in the first commit that touches config — it will not be retrofitted. |
| D10 | **Delete, don't fix.** | Repair the support/bans/VPN/revival/self-update subsystems | See the cut list. Every one of them has zero rows and at least one never-written piece. |

---

## Phase 0 — Reconcile the specs (½ day, Mac)

**Nothing gets built until the authority documents are correct**, because the app is going to be written from them and they are currently wrong in five places.

The three installers **are drifting right now, in HEAD**. All VERIFIED this session:

1. **The `.disabled` twin rule is macOS-only.** `launchers/Salvage-Setup-Mac.command:469-470` skips a tracked jar that is absent but has a `.disabled` sibling — Prism disables mods by renaming. `grep '\.disabled'` returns zero hits in the `.bat` and the `.py`. A Windows player who disables one mod gets it reported `missing`. **Not in REPAIR-SPEC.md at all.**
2. **`DRIFT_DIRS` is Windows-only.** `Salvage-Setup-Windows.bat:45` and `:605-606` add a fifth outcome class, `Drifted`, for `config/ftbquests/` because FTB Quests rewrites those `.snbt` on first world load. Mac and Python count those files as corrupt, quarantine them at rung 1, and re-fetch them every run — the exact "repair tool invents problems" failure REPAIR-SPEC.md exists to prevent. `Drifted` is **not in the fixed-vocabulary table** at `REPAIR-SPEC.md:130-139`, so `scripts/check-launchers.py` cannot catch it.
3. **Three definitions of "the player's own files."** Mac's list (`:747-753`) vs Windows' superset (`:406-420`, adds `server-resource-packs/ texturepacks/ optionsof.txt optionsshaders.txt servers.dat_old usercache.json` and a `keybind|keymap` name match) vs **Python, which has no per-path guard inside `quarantine()` at all**.
4. **`LAUNCHER-SPEC.md` §Self-update is unimplementable in Tauri.** It says *"There is deliberately no version manifest"* and *"Applied on next run… does not prompt, and does not restart itself."* Tauri's updater **requires** a semver manifest, and on Windows the NSIS installer force-exits the app to install. Neither is configurable.
5. **`LAUNCHER-SPEC.md` §What does not change** says *"One file per platform, downloaded once, double-clicked. No install step… and no new dependency."* That is the old model, restated as a constraint.

Tasks:

- Add the `.disabled` rule to REPAIR-SPEC.md's Missing check.
- Add the drift class, pick its word, add it to the vocabulary table at `:130-139`. Rule: drifted files are **reported but never quarantined** at rungs 1–2 (rungs 2–3 restore them anyway by dropping `packwiz.json`). Keep `DRIFT_DIRS` as narrow as the Windows comment insists — `config/ftbquests/` only.
- Unify the locked-path list to the Windows superset, plus the `..` guard from Mac `:747`. Specify it as: normalise to lowercase forward-slash, reject any path **component** equal to `..` (Mac's `*..*` glob would also reject a legitimate `foo..bar.jar`), then dir-prefix / exact-file / `config/*.txt` / `config/*keybind|keymap*`.
- Rewrite §Self-update for the Tauri model. The objection the old text was protecting against — *a second file that has to agree with the first* — is answered by **generating the manifest in CI from the build outputs**, so it cannot disagree. Replace silent-next-run with **one quiet "Update available — vX.Y.Z / Update and restart" row on Home**. One behaviour on both platforms instead of two.
- Rewrite §What does not change.
- Note that REPAIR-SPEC.md's hash counts ("104 and 55") are already stale — the live instance measures 95 sha512 / 54 sha1 / 15 sha256 across 179 entries. Mark them illustrative so nobody hardcodes them.

**Start the Developer ID certificate request today, in parallel.** `security find-identity -v -p codesigning` returns exactly two identities (VERIFIED): `Apple Development` and `Apple Distribution`. **Neither notarizes for outside-the-App-Store distribution.** You need a **Developer ID Application** certificate. CSR from Keychain Access → upload at developer.apple.com → download. No Xcode needed (`notarytool`, `stapler`, `codesign` are all present in `/Library/Developer/CommandLineTools`). This is ten minutes of web forms with a wait attached, and it is the single item most likely to stall the finish if discovered at the end.

**Independently valuable if you stop here:** the three installers stop drifting on three known bugs.

---

## Phase 1 — The app, offline (1–2 weeks, Mac)

`rustup`, scaffold `high-seas/app/`, port the engine. No portal, no signing, no updater. Config (`PACK_URL`, server address) is a compiled-in constant, exactly as today.

Rust, ~1,700 lines, replacing ~3,943 across the three installers (VERIFIED: 1186 + 1162 + 1595):

`prism.rs` · `packwiz.rs` · `hash.rs` · `diagnose.rs` (rung 0) · `repair.rs` (quarantine + rungs 1–3) · `report.rs` (**the fixed vocabulary as `const`s, in one place — this is the whole point**) · `install.rs` · `java.rs` · `play.rs` · `commands.rs`.

Frontend: plain HTML/CSS + a few hundred lines of vanilla TS. **No component framework.** Three status rows, one primary button, four secondary actions.

Four things that are not mechanical:

- **Model the three packwiz entry shapes as an enum, not a chain of `if`s.** `enum Entry { OtherSide, Linked{..}, Direct{..} }` with a custom deserializer that checks `onlyOtherSide` first, then `linkedFileHash`, then `hash`. Once that exists, the 54 sha1 false positives and the 15 phantom-missing server mods become structurally impossible instead of a comment you have to remember.
- **The locked-path predicate is the one function you must not get wrong.** Property-test it: no path under `saves/ screenshots/ shaderpacks/ resourcepacks/ logs/ crash-reports/ .salvage-quarantine/` is ever returned as a quarantine target by any rung. This is the test that most deserves to exist.
- **Unzip Prism on macOS with `/usr/bin/ditto -x -k`, not the `zip` crate.** The payload is a `.app` bundle with symlinks and an executable bit; the `zip` crate does not create symlinks and you will ship a broken bundle. Use the crate for the Windows zip only.
- **Detached spawn.** `Stdio::null()` on all three, drop the `Child`. Windows needs `.creation_flags(0x08000008)`. Use `std::process::Command` in a Rust command, **not `tauri-plugin-shell`** — the webview should not be able to name a program.

Async `diagnose` over a `tauri::ipc::Channel<Progress>` so the window paints before the scan resolves (`LAUNCHER-SPEC.md:57-58`).

**Do not sell this on speed.** Measured: 164 files, 444.6 MB, hashed in 0.38 s in Python, and the bash version already batches one `shasum` per algorithm. Rust buys one implementation, one vocabulary, one UI, and a real updater. Claiming performance sets up a disappointment.

**Verify `prismlauncher --launch Salvage --server <addr>` against whatever Prism version the app actually installs.** `LAUNCHER-SPEC.md:74` says it was checked on 11.0.3; the entire Play button rests on it and Prism's CLI has changed shape before.

**Independently valuable if you stop here:** you can hand a friend an unsigned build and watch them use it. The installers still work.

---

## Phase 2 — Signed, notarized, self-updating (3–5 days, Mac + CI)

`tauri signer generate` → minisign keypair. **Back the private key up outside the GitHub secret store the day you generate it.** Lose it and every installed copy is permanently un-updatable, with no recovery path but four manual reinstalls — the exact failure this project exists to escape.

CI: `.github/workflows/app-release.yml`, `on: push: tags: ['app-v*']`, matrix over `macos-latest` (`--target universal-apple-darwin`, needs both rustup targets) and `windows-latest`, then `tauri-apps/tauri-action@v0`. A final job reads each `.sig`, assembles `latest.json`, and attaches everything to an `app-vX.Y.Z` GitHub Release.

macOS signing env: prefer the **App Store Connect API key** trio over Apple-ID + app-specific password — no 2FA, revocable, no personal credential in CI. Stapling happens before the `.app.tar.gz` is made so the ticket travels inside the updater bundle. **Confirm with `stapler validate` on the first signed build** rather than assuming; an unstapled notarized app fails Gatekeeper for someone offline at first launch, which is a confusing bug to chase later.

**Windows: ship unsigned, and tell them.** Honest cost: an unsigned NSIS installer gets the full-screen blue SmartScreen dialog with *Run anyway* hidden behind *More info*, which is materially worse than today's `.bat`. But it only bites on **first install** — Tauri updates thereafter are downloaded and executed by an already-installed app, never touch a browser, and never see SmartScreen. For four known players, a screenshot in the message costs nothing. If you want it gone permanently and you are US/Canada: **Azure Artifact Signing, $9.99/month**, GA, individuals now eligible, works via `signCommand` in Actions. **Do not buy a traditional OV certificate** — ~$200-400/yr, the key must live on a hardware token since the 2023 baseline change, and reputation never accrues across four downloads, so it does not even suppress the warning.

`tauri.conf.json` updater endpoint points at a `raw.githubusercontent.com` (or Release asset) `latest.json`. Per D4 — the portal is not in this loop and never will be.

**Independently valuable if you stop here — and this is the natural stopping point.** One app, signed on macOS, self-updating on both platforms, config compiled in. All three installers are now redundant on Mac and Windows. The portal has not been touched.

---

## Phase 3 — The portal cut (2–3 days, Mac)

Delete before you build. Every subsequent step is cheaper against ~19,000 lines than 24,431, and the type-error count drops for free as the dead subsystems go.

### Cut list (line counts VERIFIED this session)

| subsystem | paths | lines | DB rows |
|---|---|---|---|
| **Support tickets** | `lib/server/support/` 922 · `(admin)/admin/support` 603 · `(app)/dashboard/support` 463 · `server/routes/support.ts` 177 · 4 bot handlers | **2,165+** | 0 / 0 / 0 |
| **Bans + ban appeals** | `(admin)/admin/appeals` 434 · `server/routes/admin-bans.ts` 106 · `server/routes/appeals.ts` 68 · `/banned` page · ban half of `moderation/bans.ts` · ban gate in `hooks.server.ts:75-88` | **~650** | 0 / 0 |
| **Config files / VPN** | `lib/server/files/` 423 · `server/routes/files.ts` 163 | **586** | 0 |
| **Server revival voting** | `server_revival_requests`, `server-lifecycle.ts:78-112`, bot `revival-threshold.ts`, the 5-min poll at `apps/bot/src/index.ts:17` | **~250** | 0 |
| **Portal self-update** | `lib/server/update-status.ts` 193 · `scripts/updater.sh` 91 · `apps/bot/src/update-check.ts` · `ops/systemd/portal-updater.service` · 8 `system_state` columns · the superadmin banner | **~450** | sentinel from 9 May 2026 still unconsumed |
| **Remaining dead Fastify routes** | of `server/routes/` (1,835 total, 514 already counted above) — cut `admin-suspensions`, `admin-system-config`, `audit`, `onboarding`, `rcon` (keep one test-RCON handler), `server-lifecycle`. **Keep `health.ts`, `auth.ts`, `plugins/session.ts`, `plugins/auth-guard.ts`, `server/index.ts`** | **~1,000** | one `fetch('/api…')` in the entire frontend |
| **`docs/`** | 26 endpoints never written; systemd units at `apps/bot/build/index.js`, a path that cannot exist because the bot has no `build` script | **5,014** | — |
| **`discord.js`** | zero imports anywhere; the only match is a comment | dependency | — |

**≈ 5,100 lines of code + 5,014 of documentation.** (The research strand said 6,000–6,500; that double-counts the route files. My arithmetic above avoids it.)

**Salvage two things before they go:** `server/routes/files.ts:36-42` (RFC 6266 `Content-Disposition`) and `:127-149` (streamed, `nosniff`, explicit `Content-Length`). They are the only correct file-serving code in the repo and they become the app's download route if you ever need one.

**Keep:** `lib/server/auth/` (1,025 lines — hashed session tokens, Argon2id, HIBP k-anonymity with fail-open, no user enumeration; the best code in the repo). `lib/server/onboarding/` (1,739 — this *is* the approval mechanism the plan needs, and it has real rows). `servers`/`hosts` schema (`packwizUrl`, `minecraftHost`, `minecraftPort`, `hidePort` already exist and are already editable in admin — **this is the strongest argument for the whole control-plane idea**). Audit log. Notification queue + bot. RCON (0 rows, but auto-whitelist-on-approval is the most valuable automation a Minecraft portal can have and it is ~90% built — the one "0 rows" subsystem I would not cut). `.github/workflows/release.yml`.

**Deleting `docs/` is not tidying.** It is removing a trap that sends you down a wrong path in six months when you have forgotten which parts were ever real. Replace with one `DEPLOY.md` written from what actually runs.

**Consequence to record:** cutting bans removes `bans.ts:211`'s "force logout everywhere". Suspensions are kept but do not delete sessions. So device-token revocation in Phase 7 rests on (a) `requireApp` checking `getActivePlatformSuspension` on every request, and (b) a manual Revoke button. For four players that is correct and sufficient.

---

## Phase 4 — Types, then the gate (1 day, Mac)

182 errors today: **62 in web** (`svelte-check`), **120 in bot** (`tsc --noEmit`). Both run under `tsx`, which strips types without checking them, so this has been invisible.

The argument is not hygiene. It is that **the compiler has been reporting two of the security bugs below into a void**: `Property 'requireUser' does not exist on type 'FastifyInstance'` (×2) and `Property 'DISCORD_BOT_TOKEN' does not exist` (×8, the documented `.env` fallback for Discord notifications silently never works).

Two edits kill ~118 of the 182:

1. Delete the `module`/`moduleResolution: "NodeNext"` overrides from `apps/bot/tsconfig.json`, `packages/rcon/tsconfig.json`, `packages/shared/tsconfig.json` so they inherit `Bundler` from the base. Nothing actually resolves those packages as NodeNext — the bot runs under `tsx`, the web through Vite, neither has a build step. Kills ~95.
2. `packages/db/src/index.ts:22` currently reads `export { schema };` and nothing else (VERIFIED). Add `export * from './schema';`. Kills ~23 across both apps.

Then grind the ~50 that remain. **Budget a day, not an afternoon**, and treat anything taking more than ten minutes as a bug report rather than a type annotation — `requireUser` and `DISCORD_BOT_TOKEN` prove there are real defects wearing type-error clothing.

Land `.github/workflows/ci.yml` **in the same PR** so it is green on day one. A red badge that stays red teaches everyone to ignore CI.

---

## Phase 5 — SECURITY GATE (½ day, Mac)

**This is a boundary, not advice. Nothing faces the tunnel until every line is done.**

| # | Fix | Evidence |
|---|---|---|
| 1 | Assert `NODE_ENV: production` in the `environment:` block of **both** compose files | VERIFIED: `.env:43` is `NODE_ENV=development`; `docker-compose.yml:34` / `.prod.yml:23` apply `env_file: .env`, which **overrides the Dockerfile's `ENV NODE_ENV=production`**; neither compose `environment:` block re-asserts it. `env.ts:63` → `isDev` → `cookie.ts:15` `secure: !isDev` and `server/index.ts:29` `trustProxy: !isDev`. **Net effect: session cookies ship without `Secure` over a public HTTPS origin, and the rate-limit key becomes the tunnel's local address for every caller.** |
| 2 | `ORIGIN=https://<hostname>` in `.env` | VERIFIED: `docker-compose.prod.yml:36` is `ORIGIN: ${ORIGIN}` with no default and `.env` has no `ORIGIN` line. Empty ORIGIN → every form POST rejected as cross-site. This is also SvelteKit's `checkOrigin`, i.e. the only CSRF control on that surface. |
| 3 | `ADDRESS_HEADER=cf-connecting-ip` | Otherwise every IP in `audit_log` is the Docker gateway. |
| 4 | Bind `127.0.0.1:3000:3000` | VERIFIED both files publish bare `'3000:3000'` → reachable from the LAN, bypassing the tunnel and any Access policy. |
| 5 | Delete first-user promotion, **both copies** | VERIFIED verbatim: `auth/service.ts:101-106` promotes to `'operator'`; `auth/service.ts:615-623` (Discord branch) promotes to **`'superadmin'`**. Two paths, same intent, different outcome, same file. Both already redundant — `packages/db/src/seed.ts` exists. Change seed to create `'operator'`, not `'superadmin'`, or a seeded deploy has no operator and no UI path to create one (`schema/auth.ts:18-21`). |
| 6 | Close signup, **inside `signupUser`** | Two doors call it (`(public)/auth/signup/+page.server.ts:20` and `server/routes/auth.ts:42`). One gate, not two. Cheapest complete version: `SIGNUP_ALLOWED_EMAILS` in `env.ts`, checked after the format check at `service.ts:50-52` and in the Discord branch at `:594-600`. ~10 lines, no migration. **For four friends whose addresses you already know, this is complete, not a stopgap.** An `invites` table is only worth it if the invite link literally becomes the distribution URL. |
| 7 | Rate-limit the login path that is **actually used** | `@fastify/rate-limit` is `global: false` and opted into on `/api/auth/login` — which the UI never calls. The real login is the SvelteKit form action. ~30 lines in `hooks.server.ts`, no dependency. |
| 8 | `sameSite: 'lax'` + an `Origin` check on any surviving `/api` mutation, **in the same commit** | VERIFIED `cookie.ts:16` is `'strict'` — every link you send from Discord lands them logged out, and it makes the Discord account-*linking* branch (`service.ts:531-552`) permanently unreachable. But `strict` is currently the only CSRF defence on `/api/*`. Split these two changes across weeks and the reasoning is lost. |
| 9 | `appeals.ts` gone | `:13` and `:42` use `{ preHandler: fastify.requireUser }`, a decorator never declared. Registers unguarded, then dereferences `req.sessionUser!.id` → 500. Both paths are in `hooks.server.ts`'s anonymous allowlist. Deletes itself in Phase 3; confirm it did. |
| 10 | **Cloudflare Access on everything except `/api/app/*`** | Dashboard, not code. Free tier, four one-time-PIN policies. Worth more than 5–8 combined. The path exception must exist before the app's first request. |
| 11 | A backup exists and has produced one file | `sqlite3 …/portal.sqlite ".backup …/$(date +%F).sqlite"`, cron, keep 14. There is no backup today and `scripts/` contains only `updater.sh`. |
| 12 | CI green | Phase 4. |

One thing I could not verify: **whether the home box's `.env` matches the working-tree `.env` I read.** Item 1 is verified against the local file. Re-check that one line on the box before trusting the conclusion — it is the difference between a `Secure` cookie and a plaintext one on a public origin.

---

## Phase 6 — Home box and tunnel (1 day, needs home network)

Everything Cloudflare-related has to be **written from scratch**. VERIFIED: `ops/caddy/` is a README with no Caddyfile. `ops/cloudflared/` is a README with no config. `ops/systemd/` contains only `portal-updater.service` — the two units that would run the app do not exist. `scripts/` contains only `updater.sh`. The Dockerfile and compose files are the only finished part of `ops/`.

Docker + Compose at `/opt/portal`. `cloudflared` as a named tunnel, DNS route, ingress `[{hostname, service: http://127.0.0.1:3000}, {service: http_status:404}]`. **Skip Caddy entirely** — the tunnel terminates TLS at Cloudflare's edge and Caddy is a moving part with no other vhost to justify it. Delete `ops/caddy/`.

Leave `SQLITE_JOURNAL_MODE` unset on Linux. Note `packages/db/src/migrate.ts:17` hardcodes `journal_mode = WAL`, bypassing the escape hatch in `createDb` — harmless on Linux, but it is why the local-Docker loop still fails on your Mac.

Deployment story, entire: `ssh box 'cd /opt/portal && docker compose -f docker-compose.prod.yml pull && up -d'`.

---

## Phase 7 — Control plane (3–4 days; code is Mac-local, wiring needs home)

One table, one plugin, three routes. **~350 lines.**

- **`app_devices`** — `id`, `user_id` FK cascade, `token_hash` UNIQUE, `name`, `platform`, `app_version`, `created_at`, `last_seen_at`, `last_seen_ip`, `expires_at` (365d), `revoked_at`, `revoked_by`. Token generation is a 15-line copy of `auth/session.ts:41-55`: 32 random bytes to the client, `sha256` in the DB. Generate the migration with `db:generate`; **do not hand-write the SQL** — the journal and snapshot must stay consistent or the next generate produces a wrong diff (there is already scar tissue about this at `schema/moderation.ts:12-16`).
- **`server/plugins/app-auth.ts`** — reads `Authorization: Bearer`, hashes, looks up, rejects on revoked/expired, joins `users`, then checks `getActivePlatformSuspension` and returns a **distinct 403 payload** so the app renders a suspension screen instead of retry-looping a 401. `return reply` explicitly. **Throttle the `last_seen_at` write to once per 5 minutes** — better-sqlite3 is synchronous and an unthrottled write serialises the whole server behind the guard. This is required, not an optimisation.
- **Minting** — a form action on the existing settings page, token shown once, plus a paired-devices list with a Revoke button. No new endpoint.
- **`GET /api/app/config`** — bearer. `{ server: {host, port, hidePort}, packwizUrl, packChannel, minAppVersion, motd, status }`, read straight off the `servers` row, gated on the caller having a `completed` onboarding. **This is the payoff of the entire plan: you change the address in one admin form and all four clients follow.**
- **`GET /api/health`** — already public, already returns bot liveness. The Home screen's server-status row needs nothing new.
- **`POST /api/app/diagnostics`** — bearer, rate-limited, 256 KB cap, one table, one admin list page. ~150 lines replacing the 2,165-line support subsystem. The app already knows exactly what failed because REPAIR-SPEC.md defines the ladder.

**On the app side, D9 is a hard rule.** Config is fetched into a cache; Play reads the cache; a failed fetch is a warning row, never a block.

**Honest note on scale:** this is where the value curve flattens. The config endpoint earns its keep. The diagnostics endpoint is nice. Device-code pairing, an `app_releases` table, a binary-upload UI, invite quotas, waitlists — none of that is warranted for four people, and if Phase 7 starts growing any of them, that is the signal to stop. The onboarding state machine is *already* the approval gate; signup only has to answer "may this person have an account at all."

---

## Phase 8 — Retirement

The installers are retired by a **named event**: every one of the four players has successfully installed from the app on Mac or Windows. Then `launchers/Salvage-Setup-Mac.command` and `launchers/Salvage-Setup-Windows.bat` are deleted, `install/salvage-setup.py` is relabelled as the Linux installer, and `scripts/check-launchers.py` collapses to a single-implementation check.

**The genuine risk of this whole plan is a fourth implementation.** If the app ships and the `.command`/`.bat` stay maintained "just in case", the drift problem is worse, not better. Keep the old download links live and *unadvertised* for the whole transition — but name the end, and take it.

---

## First concrete task

**`install/LAUNCHER-SPEC.md` is untracked (VERIFIED: `git status --short` shows `?? install/LAUNCHER-SPEC.md`). Do not commit it as written.**

Rewrite two sections first, then commit:

1. **§Self-update** (lines ~106-146) — replace the sha256-comparison model with Tauri's. Keep the reasoning that motivated "no manifest" and answer it: *the manifest is generated by CI from the build outputs, so it cannot disagree with the artifact.* Replace "applied on next run, does not prompt, does not restart" with **one "Update available — vX.Y.Z / Update and restart" row on Home**, because Windows NSIS force-exits the app to install and cannot be made silent. Keep "Never blocking" verbatim — it is correct and it is the same rule as D9.
2. **§What does not change** (lines ~148-158) — "One file per platform, downloaded once, double-clicked. No install step… and no new dependency" is the old model. Replace with what actually does not change: the repair ladder, the report format, the fixed vocabulary, nothing is ever deleted.

One file, maybe forty lines edited, an hour. It is the document Phase 1 is written from, it is sitting untracked in your working tree right now, and committing it unrevised is how a spec and an implementation start disagreeing on day one.

Then, in the same sitting, open the Apple Developer portal and request the Developer ID Application certificate — it is ten minutes of forms and it has a wait attached.
# Yoneda: three tiers and the instrument app (design, 2026-07-25)

Captured from Jeremy's direction on 2026-07-25 (JLSurface3 session). This supersedes the 2026-07-20 "move the site to yoneda.app" plan: .app is no longer a mirror of .science, it is a different thing.

## The sort: mine / group / public

**Personal (Jeremy alone, never leaves his machines):** the email layer end to end (eM Client SQLite mirror, egres, E:\egres-raw, the `email` schema, the 03:30 sync task), the personal brain instance and the pre-big-bang dump, Paperpile and calendar ingests, the Representable game, morpheus, Wearmark. None of this touches either website.

**Group (levylab.org, behind auth on yoneda.app):** everything instrument-facing. Stem-cell instances on instrument PCs, the watcher / future tray app, the registration server, the live dashboard, FLEX instrument definitions, the AI-guided onboarding flow, backlog ingestion of existing data (Asylum AFM files first). This is the longstanding motivation and the development focus.

**Public (yoneda.science, frozen):** the landing page as it stands, README/FAQ, the /make book demo. No further development until the group is ready to unveil Yoneda outside the lab. The stem cell itself eventually goes public here (and via levylabpitt/yoneda on GitHub, still unpushed), but not yet.

## Domain roles

- **yoneda.app** is where stuff actually gets done. Google-authenticated, levylab.org accounts only, via Cloudflare Access in front of the whole zone. The zone is ALREADY on Cloudflare (verified 2026-07-25: NS = desiree/guss.ns.cloudflare.com, apex proxied), so the remaining work is a worker route, an Access application, and content.
- **yoneda.science** keeps its current landing page and nothing more for now. The /start onboarding staged in site/public moves to .app; do not deploy it to .science.
- Bootstrap carve-out: an instrument PC fetching genesis.md and the stem-cell files is a curl from a machine where nobody is logged in. Scope the Access application to exclude a small public path set (e.g. /genesis.md, /stem-cell.sql, /yoneda-watch.ps1, /docker-compose.yml, /BOOT.md) or keep those five files on .science. Preference TBD; carve-out on .app keeps .science frozen.

## The app vision (Jeremy's words, condensed)

A single app running, humming, in the taskbar of a given Windows machine, monitoring for attached instruments and making sure they get ingested into the yoneda database. A server registers these computers and sucks in their info periodically. When a new instrument is connected, you go to the tray app and add the hardware. If it is an existing type of instrument, just add it (using FLEX); if it is new, an AI-guided process onboards it and starts capturing everything. It can also backlog existing data already on the computer (e.g. Asylum Research AFM files). Super easy, intuitive, with a live dashboard showing what instruments are connected and being backed up. Where the files live is secondary; keeping track of the SHA256 is what matters (consistent with rule oplog-vs-blob-v1: hash is identity, path is a hint).

## What already exists toward this

- `stem-cell/` self-initializes an empty instance on any Docker machine; identity by big-bang uuidv7; verified cross-machine content addressing (uuid_from_sha256).
- `stem-cell/yoneda-watch.ps1` is the seed of the tray app: hashes every save into blobs/, records seen-at, produced-by, revises lineage, detects TDMS-style append growth by prefix hash. Its initial sweep of an existing tree IS backlog ingestion, and window-censoring-v1 already governs what a sweep may claim.
- `stem-cell/genesis.md` is the seed of AI-guided onboarding: instructions an on-site Claude Code follows to birth an instance, ending in a live-scan acceptance test.
- The whitepaper's merge channels are the missing server-side half: instances are born independent, merge is deliberate, divergence-is-data-v1 forbids auto-convergence.

## What does not exist

1. **The tray app itself.** Staged proposal: v0 is the watcher as a scheduled task (exists). v1 wraps it in a real tray icon (small .NET or PowerShell NotifyIcon) with status, last-hash time, and an "Add instrument" menu item that opens the onboarding flow. v2 adds detection of newly attached hardware (WMI/USB/VISA arrival events) and FLEX integration so a known instrument type is a pick-from-list add.
2. **The registration server.** Proposal: no always-on lab server at first. A worker on yoneda.app accepts registration and heartbeats (instance id = big-bang uuid, hostname, instruments, watcher stats) into KV/D1, and accepts periodic dump/blob-manifest drops into R2. The main PC (or any authorized machine) pulls from R2 to merge. This keeps the server serverless and the merge deliberate.
3. **The live dashboard.** A page on yoneda.app reading the heartbeat store: which PCs, which instruments, last save seen, backlog progress. First real content behind the auth wall.
4. **Auth.** Cloudflare Access application covering yoneda.app, policy = emails ending in @levylab.org. Google SSO as IdP needs a one-time Google OAuth client created by Jeremy; until then Access's one-time PIN (emailed code, same @levylab.org restriction) works with zero Google-side setup.
5. **FLEX bridge.** Instrument definitions for known types so "add existing instrument" is a selection, not an onboarding. Depends on what FLEX exposes; design with the first MFP3D/Cypher onboarding.

## Open decisions (Jeremy's)

- Google SSO now (needs his OAuth client) vs one-time PIN first (works today).
- Bootstrap files: public carve-out on .app vs staying on .science.
- Where R2-landed dumps get merged and by whom (main PC pull is the default).

## Blocker for all Cloudflare work

No Cloudflare credentials on JLSurface3. Either `npx wrangler login` here (browser approve) or an API token (Workers + Access + DNS scopes) unblocks: deploying workers to both zones, creating the Access application, and the heartbeat/R2 plumbing.

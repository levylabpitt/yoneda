# Design: federating yonedas you own across machines (2026-07-29)

Status: design phase, nothing set. This note records the decisions we are making now and the prototype that backs them (`proto/federation-borrow.py`, run output reproduced at the end). Supersedes the "just push into a hub" sketch in the notebook v1 sync story: push-only consolidates many machines into one readable place but never feeds the others back, so no single machine ever holds the union. What follows is the model that does.

## The core move

A relation is `(o1, o2, d)`: two object ids and a payload. If object **ids are global** (the same object carries the same id on every machine), then a relation authored on one machine is **meaningful on another with zero translation**, because `o1` and `o2` already denote the same things there. No foreign-key remapping, no identity merge, no conflict on identity. That single property is what makes relations borrowable, and it holds **iff the object layer is content-addressed** (same content, same id, minted identically anywhere, no coordination).

Consequence, and the shape of the whole system:

- **Objects are the shared coordinate frame.** Content-addressed, 1:1, small, fully replicated to every sibling. Unioning them is `INSERT ... ON CONFLICT(i) DO NOTHING`.
- **Relations are federated.** Large, and where the knowledge lives (`|o| << |r|`). Each sibling authors its own; a machine can **borrow** them (query a sibling live, import nothing) or **incorporate** them (copy locally for offline/speed). Three states per relation: `local`, `borrowed`, `incorporated`.

## The Yoneda reading (why this is the right model, not just a convenient one)

An object's meaning is its presheaf `Hom(-, X)`, the totality of arrows touching it. Each sibling holds **part of** `Hom(-, X)`; your full knowledge of `X` is the **colimit (union) of every sibling's `Hom(-, X)`**. Because the object base is shared 1:1, those presheaves **glue over a common base**, which is exactly what makes them composable across machines. Federating relations over a replicated object frame is *assembling representables*. Borrowing is fetching more of an object's co-presheaf on demand; the object is the same representable everywhere, and machines differ only in how much of its neighborhood they currently hold.

## Decisions

1. **The object layer is fully content-addressed.** Id = UUID v8 truncation of `sha256(canonical-content)` (as the Timescale build already does for blobs; `cid()` in the prototype). This makes 1:1 hold *by construction* rather than by luck. Persons stay non-objects (connected components of `same` witnesses), consistent with the existing schema principle.

2. **Events are witnesses, not frame-objects.** A measurement-run / snapshot / observation is "this happened, here, then", which two machines cannot content-address to the same id. Modeling them as **relations** (arrows carrying `d`, stamped with the authoring instance) keeps the object layer 1:1 and makes `|o| << |r|` true by construction, not coincidence. (Today `kind:measurement-run` etc. are objects; this is the change.)

3. **Relation identity = authored `uuidv7`, plus provenance in `b`.** A relation keeps the globally-unique id its author minted, and `b` = the author's big-bang id. Two machines independently asserting the "same" claim produce two rows; that is correct under `divergence-is-data-v1` (keep both, never force-merge), and the stable id makes incorporation idempotent. Collapsing genuinely-identical claims is an optional, separate step (content-address the claim), never automatic.

4. **Borrow returns `r_active` with outcomes, never raw `r`.** Truth flows through the latest outcome. A borrow query returns `(relation + latest outcome status)`, so a retraction on the sibling is visible immediately. Retraction stays append-only (an outcome row), so the whole model remains union-only in both directions; nothing is ever mutated or deleted.

5. **Incorporate = union by id of the relation and its outcomes.** Idempotent (`ON CONFLICT(i) DO NOTHING`). An incorporated relation is a **revalidatable cache**, not a snapshot: re-pull outcomes to catch later retractions, or carry "last confirmed against sibling S at t". Because it is union-only, staleness is the only failure mode, never corruption.

6. **The `.db` file is never the sync channel.** Two machines opening one file-synced SQLite is the corruption trap (already flagged in the project CLAUDE.md). Sync moves *rows*, not files: each machine keeps its own local instance and exchanges append-only row deltas.

## What the prototype proves (`proto/federation-borrow.py`)

Two throwaway SQLite instances, "office" and "home", each with its own big bang. "Remote" is simulated by opening the sibling read-only; in production that read is a network call to the sibling's `Hom(-, X)` endpoint and nothing else changes.

1. The same four nouns minted independently on both instances get **identical ids** (1:1 object frame verified).
2. office authors 3 relations on a shared sample, home authors 1. Home borrows office's active `Hom(-, sample)` and renders the **full neighborhood from relations it does not own, with zero remapping** (every borrowed endpoint equals home's own sample id).
3. office retracts one run (append-only outcome). Home re-borrows and the retracted run **drops out** via `r_active`.
4. Home incorporates one borrowed relation twice; the second call is a **no-op**. It now appears in home's local `Hom(-, sample)`, available offline.

Final counts: office `(o=5, r=3, r_active=2)`, home `(o=5, r=2, r_active=2)` -- shared object frame, divergent-but-unionable relation sets.

## Forks resolved (2026-07-29, Jeremy)

- **Hub topology: per-machine append-only delta files, and fully automatic.** Each machine writes only its *own* delta file into cloud storage (OneDrive/Nextcloud), every machine imports all siblings' deltas by id (the git-fetch model: no shared mutable file, offline-eventual). Chosen over an always-on hub because it fits local-first and survives disconnection. **No manual push/pull**: sync is a background watcher (the `yoneda-watch.ps1` shape), so consistency is a property of the system, not a chore. Live *borrow* rides on top whenever a sibling is reachable. Kept separate from the office server, which is reserved for instruments ("only sucks in from instruments, never people", 2026-07-25).
- **Identity of an owner-authored thought: keep both, link with `same`, earliest-`t` is the original.** A thought at home and the same-worded thought at work are distinct events; place (authoring instance `b`) and time (`t`) are part of the thought's identity, and that context is information we refuse to destroy. Never collapse by text. A `same` witness links them deliberately, leaving both standing; within that cluster the minimum-`t` row is the origin and the rest are its lineage.

## The lab clock: a GPS stratum-1 time source

"Earliest-`t` is the original" is only trustworthy if machines agree on time, and the honest constraint is clock skew (no global "now"). The lab already owns the fix: a **LeoNTP** GPS-disciplined stratum-1 NTP server (Leo Bodnar Electronics), purchased ~2021-08-30 for exactly this purpose (Asana "Purchase Requests" task 1200883703153983, quote `v3.airspy.us/product/upu-leontp`, $350). **Confirmed physically present 2026-07-29** (serial 1048, MAC 70:B3:D5:E3:D6:18, mfg 01-2021, PoE/USB), powered and keeping time, just not serving the lab. `t_universe()` supplies the shared time *axis* (declared epoch, comparable across machines that never talked); the LeoNTP supplies the shared *clock* on that axis. For data-taking, an instrument's own monotonic sequence since its big bang remains the finest-grained origin order, with GPS `t` as the coarse cross-instance sort.

**Key point that lowers the urgency:** `min(t)` ordering needs low *relative* skew across the lab's machines, not absolute UTC accuracy. So a "good enough" clock everyone shares suffices.

**Interim setup (decided 2026-07-29):** a server proxies the LeoNTP as a stratum-2 source (disciplines to it when the GPS fix is up, holds over when it drops); lab PCs sync to that server, not the box directly; PCs poll more frequently (`w32tm` `SpecialPollInterval` ~64-256s vs the ~1024s default) for smaller, more frequent corrections. Deferred (not crucial now): the box currently sees sunlight but struggles for 4 satellites; the real fix is **position-hold / survey-in mode**, which holds time on a single satellite once position is known (matters more than antenna placement), plus eventually an antenna with clear sky. The clock itself enters the graph as a content-addressed cell keyed by its MAC (a hardware `ref`, same id on every instance); every authored cell's `t` traces back to it.

## Category theory backbone

Not decoration; each piece lands on a concrete schema feature.

1. **Reification -> presheaf topos, licensed by Yoneda.** The moment an outcome row *points at a relation's `i`*, a relation is being treated as an object. Promoting the morphisms of a category `C` to objects is the move to the presheaf category `[Cᵒᵖ, Set]`, where relations-of-`C` are objects. The Yoneda embedding `y: C ↪ [Cᵒᵖ, Set]`, `X ↦ Hom(-, X)`, is **fully faithful**: replacing an object by all arrows into it loses nothing. This is the theorem behind the whole design -- a thin shared object frame plus rich distributed relations is not lossy, because an object *is* its relations. Borrowing = gluing `Hom(-, X)` from siblings that each hold a piece.
2. **The level tower is an (∞,1)-category, made durable.** Level 0 objects (`o`), level 1 relations (`r`), level 2 relations-between-relations (an outcome retracting a witness is a 2-cell), level 3+ rules about rules. The schema already carries this as **rules-as-rows with a `level` column** -- that column is the `n` in n-morphism. No top level escapes revision, so it is an (∞,1)-category, matching Jeremy's own working-method framing exactly. "2nd-order" is just level 2 of a tower already committed to.
3. **`divergence-is-data` = keep the profunctor, refuse the function.** A relation holding many witnesses from many instances is a profunctor `Cᵒᵖ × D → Set`, not a function; a function forces one output per input (forced convergence). CRDT/OT force functions; keeping the witness set keeps the profunctor. `coauthor`/`co_attended` are already "composed profunctors". Restated: a function is a profunctor forced to converge, and we keep the profunctor.
4. **Provenance/time = a fibration (Grothendieck construction).** Each instance is its own category; the federated brain is fibered over the base of instances via `∫` of the functor sending each instance to its category. "Two big bangs in one frame" = two fibers in one total category; a merge is a colimit over the base that leaves both parents standing. Earliest-`t` is the origin within a fiber's timeline; the LeoNTP makes the base's time coordinate physical.

**Schema stance (decided 2026-07-29, reversing an earlier two-table lean):** go **fully uniform, one cell table**. A relation is a cell that carries face pointers; the two-table `o`/`r` split is a 1-truncation of the globular presentation below. Rationale: human legibility of raw rows is valued at zero (Jeremy will never read them), and the long-run criterion favors the model with nothing to migrate.

### Uniform "cell" model

The standard presentation of an (∞,1)-category is a **globular set**: one collection of cells of every dimension, with source/target (face) maps. A 0-cell is an object; a 1-cell's faces are 0-cells; a 2-cell's faces are 1-cells; no ceiling. A relation-node's endpoint pointers *are* its face maps, so "everything is a cell that may point at other cells" is exactly that presentation in one table. Two tables keeps dimensions 0 and 1 first-class and bolts on everything higher (the prototype already needed a third `outcome` table the moment retraction appeared; uniform makes it vanish, a retraction being just a cell pointing at a cell).

Long-run wins:
- **Zero schema migration for any new order of statement.** node-vs-edge is the boundary that events, rules, and provenance all straddle; removing it removes the migrations. Same finding as the stem cell's "adds zero tables", taken to its limit: one table, for everything, forever.
- **Identity-discipline decouples from nounhood.** id-scheme becomes a per-cell property orthogonal to whether the cell has faces. Immutable cells (a `doi`, a definitional edge) get content-addressed ids (`uuid_from_sha256`) and dedupe 1:1 across machines; observed cells (a scan, a thought, a retraction) get authored `uuidv7` + `b` + `t` and are kept with provenance. This dissolves the "demote events from objects to witnesses" migration: an event is simply an authored cell. The content-addressed federation frame then extends as far as immutability reaches, nouns and edges alike, not stopping at a table wall.

Two honest costs, neither real here:
- **Traversal speed.** endpoints in JSON index slower than native columns. Fix: a derived endpoint index (generated columns or a trigger-maintained `(cell, endpoint, role)` companion). It is an accelerator, not a materialized fact, so it does not violate "derived structure is computed" -- an index is not a truth claim.
- **Referential integrity.** an FK could forbid dangling edges, but federation already permits (indeed requires) borrowing an edge whose endpoint is not yet synced. Dangling-until-resolved is the normal state; FK enforcement was surrendered by the choice to borrow. Uniform loses nothing keepable.

Concrete shape: one table `cell(i uuid pk, j jsonb)` + a derived endpoint index. In `j`: **faces** as a role map generalizing `o1`/`o2` (`{"src":id,"tgt":id}`, or `{"instrument":id,"sample":id}`, or `{"of":rel_id,"status":"retracted"}`); **identity** = content-hash (no `b`/`t`) or authored (`b`+`t`). `r_active`, `same`-clusters, and borrow become queries over the index, not tables. This replaces the `o`/`r` genome in the stem cell with a single-cell genome, making the handed-out substrate more minimal, not less.

## Next steps (forks now settled)

- **Delta-file sync**: each instance exports new `o`/`r`/`outcome` rows to its own append-only delta file in the cloud folder, keyed by big-bang id + monotonic seq; import unions all unseen deltas by id (`ON CONFLICT DO NOTHING`). Generalize `sync.py` from Postgres-push to this file transport.
- **Automatic, no manual step**: drive it from the `yoneda-watch.ps1`-style background watcher so export/import happen on change, never by command.
- **Live borrow endpoint**: a `Hom(-, X)` query on each instance (the notebook already serves `127.0.0.1:8787`), used when a sibling is reachable.
- **Migration**: demote existing `kind:event`/`measurement-run` objects to witness relations in the genome; re-mint any non-content-addressed frame-objects to their `cid()`.
- **Clock**: bring the LeoNTP online in NPL1 and point lab machines/instruments at it (confirm the unit exists first).

## Built and proven (2026-07-29)

`cell/` implements the uniform substrate in SQLite (stdlib only): `cell.sql` (genome), `cell.py` (reference lib), `test_federation.py` (all green), `migrate_from_or.py`. The federation test proves: 1:1 content-addressed frame; per-cell identity discipline (a definitional edge dedups across machines, an authored observation is kept with provenance); live cross-instance borrow with zero remapping; cell->cell retraction with latest-outcome-wins plus append-only reactivation; native higher order (a note cell points at an outcome that points at a relation that points at objects, all through one edge index); and idempotent delta union. Migrating the live `o`/`r` dump (367 objects + 165 relations) yields 533 cells / 330 edges (exactly 2.0 per relation), and `Hom(-, X)` renders on the migrated copy. Nothing touched the live instance; a fresh backup was taken (`backups/ydb/ydb-2026-07-29.dump`).

**Finding (time precision), from actually building it.** Storing `t_universe` (unix + 4.354e17) as a float64 destroys ~100 s of resolution, so closely spaced events cannot be ordered and latest-outcome-wins silently breaks. Fix, and it is the design's own "the epoch is a coordinate, declared not measured" taken literally: **store unix time at full precision and apply the epoch offset only at read time**. A constant shift leaves all orderings and differences invariant, so storing unix loses nothing; the huge number was pure precision loss. Break exact ties with a monotonic per-instance sequence (SQLite `rowid`). Absolute universal time is a display transform, never a stored magnitude.

## Also built (2026-07-29, same session)

- **Delta-file sync** (`cell/sync.py`): each instance publishes only its own rows to `<syncdir>/<bigbang>/<seq>.ndjson` and imports siblings' unseen deltas; union by id, machine-local watermarks, no amplification loop (a sibling's authored cells are never re-exported). `tick()` = publish+absorb; `watch()` = the automatic polling loop (no manual step). Test converges two instances through a shared folder with no direct connection, is idempotent at steady state, and propagates new cells on the next tick.
- **Live borrow endpoint** (`cell/serve.py`): stdlib HTTP `GET /hom?x=` serving active `Hom(-, X)` read-only; `borrow_http()` client. Tested against a live server on an ephemeral port.
- **Postgres genome + live cutover** (`cell/cell.pg.sql`, `cell/migrate-live.pg.sql`): the substrate in Postgres (schema `cell`), and the live instance migrated **additively** -> 367 objects + 165 relations = **532 cells, 330 edges, 532 active**, with `public.o`/`public.r` left intact. Reversible: `DROP SCHEMA cell CASCADE`. `Hom(-, X)` runs natively over the `edge` index.

## Still to build

- Wire `watch()` into the notebook app as an OS-level background service (login/boot), and add filesystem-change triggering on top of the polling floor.
- Point the notebook's local server at the cell substrate so borrow is exposed by the running app.
- Retire `public.o`/`public.r` once the parallel `cell` schema is trusted; swap the stem-cell genome to `cell.sql` for newly birthed instances.

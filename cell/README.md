# cell/ — the uniform-cell substrate (prototype)

The single-table substrate from [../design-federation-2026-07-29.md](../design-federation-2026-07-29.md). One `cell` table holds cells of every dimension; a relation is a cell carrying face pointers (its source/target maps). This is the globular-set presentation of the (∞,1)-category, replacing the two-table `o`/`r` genome.

- `genome.py` — **THE specification.** One schema, two dialects. `cell.sql` and `cell.pg.sql` are generated from it; `python genome.py --write` regenerates them and `--check` fails if a committed file is stale. Edit this, never the .sql files.
- `cell.sql` — GENERATED. The genome in SQLite: `cell` table, derived `edge` endpoint index (trigger-maintained), `active` view (latest-outcome-wins).
- `cell.py` — stdlib-only reference library: content-addressed `put`, authored `author`/`relate`, `retract`/`reactivate`, `hom` (Hom(-,X)), delta `export_rows`/`import_rows`, and `borrow` (read-only query of a sibling).
- `test_federation.py` — end-to-end proof (all green): 1:1 frame, per-cell identity discipline, cross-instance borrow with zero remapping, cell→cell retraction + append-only reactivation, native higher order, idempotent delta union.
- `sync.py` — delta-file sync (Fork-1 transport): `export_deltas`/`import_deltas`/`tick`/`watch`. Each machine writes only its own delta files to a shared folder; union by id; automatic via `watch()`.
- `serve.py` — live borrow endpoint: stdlib HTTP `GET /hom?x=` serving active `Hom(-, X)`; `borrow_http()` client.
- `cell.pg.sql` — GENERATED. The same genome in Postgres/TimescaleDB (schema `cell`, the hub/upgrade target). Also emitted to `site/public/` and `stem-cell/`, because a hand-kept copy under site/public is exactly how a fourth divergent genome got there.
- `test_genome.py` — the two dialects must not drift: asserts the committed files match the spec, that both declare the same columns in the same order, and that the SQLite genome actually executes.

Run tests: `python test_genome.py`, `python test_federation.py` and `python test_sync_serve.py` (all green).

One spec, two engines: a laptop runs SQLite and the hub runs Timescale, and an instance copies between them column for column. That only holds because both dialects come from `genome.py`; hand-maintained, they drifted twice in one afternoon.

Status: SQLite substrate + sync + borrow proven; the `o`/`r` genome is gone from the repo and Yoneda Notebook runs the cell substrate. Not yet: the watcher as an OS service.

The prose explanation, with worked examples of corrections, order of statement, identity and merging, is in the top-level [README](../README.md#what-a-cell-is).

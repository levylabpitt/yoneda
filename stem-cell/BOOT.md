# Yoneda stem cell: boot instructions

> **Note.** This is the SERVER bring-up. Instrument and personal machines run
> the Yoneda Notebook instead (see /start), on the same uniform-cell genome.
> Server and laptop now boot from one specification: `cell.pg.sql` here and
> `cell.sql` there, both generated from `cell/genome.py`, so they cannot drift.
> The two-table o/r genome it used to boot is gone. Everything this file says
> about the design (nothing deleted, entities as components, truth as a view)
> is unchanged.

You are getting an **empty** categorical database, not a copy of anyone else's.
It initializes itself on first boot and you fill it with your own data.

## What you need

Docker Desktop. That is the whole list. (Windows: it may need IT approval to
install. Ask early, it is the only slow step.)

## Boot

```
cd stem-cell
docker compose up -d
```

First boot takes about 20 seconds. Then:

```
docker exec -it yoneda psql -U postgres -d yoneda
```

You should see two tables (`o`, `r`), three views (`consensus`, `r_active`,
`blobs`), and ten objects: nine rules, plus the record of your instance being
born. If you do, you are done.

Sanity check:

```sql
SELECT j->>'name' FROM o WHERE j->>'type'='rule';   -- 9 rows
SELECT instance_id();   -- who you are: the id of your own big bang
SELECT age();           -- how many seconds your database has existed
SELECT t_universe();    -- seconds since the Big Bang of our universe
```

That last one deserves a warning, because it is a convention and not a
measurement. The age of the universe is 13.797 +/- 0.023 Gyr, and that
uncertainty is about 7.3e14 seconds, so only about four of the eighteen digits
mean anything and none of them mean anything as an absolute. The origin is
declared exact by fiat, the same way SI fixes the speed of light rather than
measuring it. Differences are exact. The absolute is a shared convention, and it
is written down as rule `universal-epoch-v1` where you can read it and argue
with it.

Your database has a big bang. It is the moment you ran `docker compose up -d`,
and nothing precedes it. That is not a gap to be backfilled: an instance is
never migrated from the beginning of time, it is given an origin. Your instance
is identified by that birth event, which is why there is no id in a config file
anywhere. The event's own row id is who you are, and it is unique across every
machine in the group without any of you having to coordinate.

To wipe yours and start over: `docker compose down -v && docker compose up -d`.

## What you actually got

Two tables. That is not a simplification for teaching purposes, it is the
design.

- **`o` = objects.** Anything at all: a sample, a device, a cooldown, a rule.
  Everything lives in one JSONB column `j`. There is no schema to migrate,
  because there is no schema.
- **`r` = relations.** Typed witnesses between objects. Each row says *someone
  or something claimed this, with this confidence `c`, on this branch `b`, at
  this time `t`.*

Three things that will feel wrong at first and are load-bearing:

1. **Nothing is ever deleted.** No `DELETE`, no `UPDATE`. Bad run? You add an
   *outcome* row that retracts the witness (`SELECT retract(<id>, 'why')`), and
   query through `r_active`, which honours the latest verdict. The bad run stays
   in `r` forever. It is not clutter, it is the calibration data.
2. **Entities are not stored.** There is no `samples` table. A sample is a
   *connected component* of `same` witnesses, computed on demand:
   `SELECT * FROM component('sample','LAO-STO-0417B')`. If you later learn two
   labels were the same sample, you add a `same` witness. You never merge rows.
3. **Truth is a view.** `consensus` computes it by weighting witnesses by `c`.
   The weighting law is *not settled* (`status: seed-prior` in the rule row). It
   is an open empirical question, which is why we keep disagreements.

## Where the data goes

**Raw traces do not go in the database.** Ever. This is rule `oplog-vs-blob-v1`,
and it is the one rule most likely to be violated by accident.

A ten-million-point sweep is *not* ten million rows. The bytes go into the
content-addressed blob store (`./blobs/`), and the database holds:

- a **ref** to the sha256 hash: `SELECT blob('<sha256>', '{"bytes":...}')`
- the **provenance** around it: which sample, which instrument, which cooldown,
  whose hands, what settings.

The dividing line is **concurrency, not size**. Nobody co-edits a fridge sweep,
so it is a blob. A lab notebook entry three people are editing is not.

**Address blobs by hash, never by path.** Paths are lies waiting to happen:
files move, get overwritten, get re-saved by the DAQ with the same name and
different bytes. If you record the path, use `blob_seen_at(hash, path, host)`,
which stores it as a *dated observation of where the bytes were last seen*. Then
reorganizing your folders never breaks anything, and re-ingesting the same file
is silently recognized instead of duplicated.

## The instrument lineage

There is no instrument add-on to apply, and that is the point: the lineage
added **zero new tables**, so it had nothing to say that the genome does not
already say. A sample, a device, a cooldown, a blob, a provenance record and a
retraction are all cells; what distinguishes them is what they point at.

If you find yourself adding a table for measurement points, stop. You are about
to put the sweep in `r`.

## Getting help

The rules are *in the database*, with their reasoning:

```sql
SELECT jsonb_pretty(j) FROM o WHERE j->>'type'='rule';
```

That is deliberate. When you hit a design question, the answer and the argument
for it are queryable, not buried in someone's head or a comment.

New lessons about your data become **new rule rows**, not code fixes. If you
learn something the substrate should know, write it down as a row and tell
Jeremy.

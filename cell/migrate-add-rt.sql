-- Add record time and the time indexes to an existing cell instance.
-- Idempotent. Postgres/TimescaleDB above, SQLite below.
--
-- t is unchanged and stays unix seconds. An earlier revision of this migration
-- claimed t was losing 64 seconds of resolution; that was wrong. The 64-second
-- ulp applies at t_universe magnitude (4.354e17), and t has always stored unix
-- (~1.79e9), where the ulp is 238 ns. The epoch is a read-time transform. See
-- the header of cell.sql.
--
-- What was actually missing: an index on time, and a second time. An event
-- happening and an event being written down are different facts; measured over
-- 20,699 notebook pages, 58% were written after the day they describe.

BEGIN;

ALTER TABLE cell.cell ADD COLUMN IF NOT EXISTS rt double precision;

-- Record time is unknown for rows that predate the column. Seeding it from the
-- event time asserts nothing new: for those rows the two were never separated.
UPDATE cell.cell SET rt = t WHERE rt IS NULL AND t IS NOT NULL;

CREATE INDEX IF NOT EXISTS cell_t_idx   ON cell.cell(t);
CREATE INDEX IF NOT EXISTS cell_rt_idx  ON cell.cell(rt);
CREATE INDEX IF NOT EXISTS cell_b_t_idx ON cell.cell(b, t DESC);

COMMIT;

-- Optional, on a Timescale instance whose cells all carry a time. Content-addressed
-- cells have NULL t and cannot be partitioned, so check before enabling:
--   SELECT count(*) FROM cell.cell WHERE t IS NULL;
--   SELECT create_hypertable('cell.cell', 't', chunk_time_interval => 604800,
--                            if_not_exists => TRUE, migrate_data => TRUE);

-- ---------------------------------------------------------------------------
-- SQLite equivalent:
--
--   ALTER TABLE cell ADD COLUMN rt REAL;
--   UPDATE cell SET rt = t WHERE rt IS NULL AND t IS NOT NULL;
--   CREATE INDEX IF NOT EXISTS cell_t_idx   ON cell(t);
--   CREATE INDEX IF NOT EXISTS cell_rt_idx  ON cell(rt);
--   CREATE INDEX IF NOT EXISTS cell_b_t_idx ON cell(b, t DESC);
-- ---------------------------------------------------------------------------

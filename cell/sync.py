#!/usr/bin/env python3
"""Delta-file sync for the uniform-cell substrate (the chosen Fork-1 transport).

Each machine writes ONLY its own delta files into a shared folder (Nextcloud/OneDrive);
every machine imports all siblings' deltas it has not seen. No shared mutable db file, no
concurrent-open hazard; union by id is idempotent, so re-runs and re-propagation are free.

Layout:  <syncdir>/<bigbang-id>/<00000001>.ndjson   (one cell row per line)

A machine exports rows it ORIGINATED: its own authored cells (b == self) plus content-addressed
cells (b IS NULL, identical everywhere so re-propagation is harmless). It never re-exports a
sibling's authored cell, so there is no amplification loop. Watermarks live in a machine-local
`_sync` table, not in the shared data.
"""
import os, json

def _ensure(db): db.execute("CREATE TABLE IF NOT EXISTS _sync(k TEXT PRIMARY KEY, v TEXT)"); db.commit()
def _get(db, k, d): r = db.execute("SELECT v FROM _sync WHERE k=?", (k,)).fetchone(); return r[0] if r else d
def _set(db, k, v): db.execute("INSERT INTO _sync(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v))); db.commit()

def export_deltas(inst, syncdir):
    _ensure(inst.db)
    last = int(_get(inst.db, "out_rowid", "0"))
    rows = inst.db.execute(
        "SELECT rowid,i,j,b,t,rt FROM cell WHERE rowid>? AND (b=? OR b IS NULL) ORDER BY rowid",
        (last, inst.id)).fetchall()
    if not rows: return 0
    outdir = os.path.join(syncdir, inst.id); os.makedirs(outdir, exist_ok=True)
    seq = int(_get(inst.db, "out_seq", "0")) + 1
    with open(os.path.join(outdir, f"{seq:08d}.ndjson"), "w", encoding="utf8") as f:
        for rid, i, j, b, t, rt in rows:
            f.write(json.dumps({"i": i, "j": j, "b": b, "t": t, "rt": rt}) + chr(10))
    _set(inst.db, "out_rowid", rows[-1][0]); _set(inst.db, "out_seq", seq)
    return len(rows)

def import_deltas(inst, syncdir):
    _ensure(inst.db)
    total = 0
    if not os.path.isdir(syncdir): return 0
    for src in sorted(os.listdir(syncdir)):
        if src == inst.id: continue
        srcdir = os.path.join(syncdir, src)
        if not os.path.isdir(srcdir): continue
        lastseq = int(_get(inst.db, f"in:{src}", "0"))
        for fn in sorted(os.listdir(srcdir)):
            if not fn.endswith(".ndjson"): continue
            seq = int(fn.split(".")[0])
            if seq <= lastseq: continue
            rows = []
            for line in open(os.path.join(srcdir, fn), encoding="utf8"):
                line = line.strip()
                if line:
                    d = json.loads(line)
                    # .get: a delta written by an older peer has no rt. Carrying None is
                    # correct -- we do not know when they recorded it, and inventing a time
                    # would be worse than admitting the gap.
                    rows.append((d["i"], d["j"], d["b"], d["t"], d.get("rt")))
            total += inst.import_rows(rows)
            _set(inst.db, f"in:{src}", seq)
    return total

def tick(inst, syncdir):
    """One sync cycle: publish what's new here, absorb what's new elsewhere."""
    return {"exported": export_deltas(inst, syncdir), "imported": import_deltas(inst, syncdir)}

def watch(inst, syncdir, interval=2.0, stop=None):
    """Automatic: tick on an interval until `stop` (a callable) returns True. No manual step.
    A production watcher would also fire on filesystem-change events; polling is the floor."""
    import time
    while not (stop and stop()):
        tick(inst, syncdir)
        time.sleep(interval)

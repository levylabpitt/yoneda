#!/usr/bin/env python3
"""Yoneda uniform-cell reference library (stdlib only).

One cell table; a relation is a cell carrying face pointers (its source/target maps).
Identity is per-cell, orthogonal to whether a cell has faces:
  - content-addressed cells (immutable nouns, definitional edges): id = sha256(canonical j) in full,
    no provenance. Same content -> same id on every machine (the 1:1 federation frame).
  - authored cells (observations, thoughts, measurements, outcomes): id = uuidv7, stamped with
    b (authoring big-bang) and t (t_universe). Kept distinct across machines, with provenance.

Retraction is a cell of kind 'outcome' pointing (role 'of') at another cell; latest outcome wins
via the `active` view. Higher order is free: a cell may point at a cell at any level.
"""
import sqlite3, hashlib, json, os, time, secrets

EPOCH_OFFSET = 4.354e17  # declared seconds, universal big bang -> unix epoch (rule universal-epoch-v1)
# We STORE unix time (full float precision) and apply the epoch only as a read-time coordinate
# transform. Baking 4.354e17 into a stored float64 destroys ~100 s of resolution, so closely
# spaced events cannot be ordered. Orderings/differences are invariant under the constant shift,
# so storing unix loses nothing; the epoch matters only for the absolute display coordinate.
#
# TWO times per cell, because an event happening and an event being written down are different
# facts. Measured over 20,699 pages of the Levy lab notebook corpus: 58% were created AFTER the
# day they describe, median lag one day, and 3.5% BEFORE it, because the author laid out session
# pages in advance. With one column the write-up timestamp silently becomes the measurement
# timestamp, and every join to instrument data is then wrong by a median of a day.
#   t   event time  -- when the thing happened
#   rt  record time -- when this instance asserted it
def now(): return time.time()
def t_universe(unix): return unix + EPOCH_OFFSET
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _fmt(b16):
    b = bytearray(b16); b[6] = (b[6] & 0x0F) | (b[6] & 0)  # placeholder, set by callers
    x = bytes(b16).hex()
    return f"{x[0:8]}-{x[8:12]}-{x[12:16]}-{x[16:20]}-{x[20:32]}"

def cid(j: dict) -> str:
    """Content id: the sha256 of the canonical content, all of it, 64 hex characters.

    Never truncated. This was once the first sixteen bytes reshaped into a UUID
    v8, because the Postgres column was `uuid` and a uuid is sixteen bytes. That
    produced an identifier which was no longer the hash: it could not be checked
    by hashing the content and comparing, only by remembering and re-applying
    the truncation. The column is text now and the whole digest is kept, so an
    id can be verified by anyone holding the content, which is the entire point
    of content addressing."""
    return hashlib.sha256(canon(j).encode()).hexdigest()

def uuid7() -> str:
    """Time-ordered per-instance unique id for an authored cell."""
    ms = int(time.time() * 1000); r = secrets.token_bytes(10)
    h = bytearray(ms.to_bytes(6, "big") + r)
    h[6] = (h[6] & 0x0F) | 0x70; h[8] = (h[8] & 0x3F) | 0x80
    return _fmt(h)

GENOME = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cell.sql"), encoding="utf8").read()

class Instance:
    def __init__(self, path, fresh=False):
        if fresh and os.path.exists(path): os.remove(path)
        self.db = sqlite3.connect(path)
        self.db.executescript(GENOME)
        row = self.db.execute("SELECT i FROM cell WHERE json_extract(j,'$.kind')='big-bang'").fetchone()
        if row:
            self.id = row[0]
        else:
            self.id = uuid7()
            n = now()
            self._raw(self.id, {"kind": "big-bang"}, self.id, n, n)

    def _raw(self, i, j, b=None, t=None, rt=None):
        cur = self.db.execute("INSERT OR IGNORE INTO cell(i,j,b,t,rt) VALUES(?,?,?,?,?)",
                              (i, canon(j), b, t, rt))
        self.db.commit(); return i, cur.rowcount

    # --- authoring ---
    def put(self, j: dict) -> str:
        """Insert a content-addressed (immutable) cell. Idempotent: same content -> same id.

        t stays NULL: a definitional cell has no event time, it is not something that happened.
        rt is stamped anyway, because when this instance first saw a definition is a fact about
        this instance and costs nothing. It is not part of the id, so federation is unaffected."""
        return self._raw(cid(j), j, None, None, now())[0]

    def author(self, j: dict, t=None) -> str:
        """Insert an authored cell, stamped with this instance's provenance and time.

        t is EVENT time. Omit it and the event is taken to be now, which is the common case.
        Pass it when recording something that happened earlier: a measurement written up days
        later, a notebook page dated before it was typed. rt is RECORD time and is always now."""
        rec = now()
        return self._raw(uuid7(), j, self.id, rec if t is None else t, rec)[0]

    def relate(self, kind, faces: dict, data=None, authored=True, t=None) -> str:
        j = {"kind": kind, "faces": faces}
        if data is not None: j["data"] = data
        return self.author(j, t) if authored else self.put(j)

    def retract(self, cell_i):   return self.author({"kind": "outcome", "faces": {"of": cell_i}, "data": {"status": "retracted"}})
    def reactivate(self, cell_i): return self.author({"kind": "outcome", "faces": {"of": cell_i}, "data": {"status": "active"}})

    # --- reading ---
    def hom(self, X, conn=None):
        """Hom(-, X): active cells that touch X (any role). Ordered by event time: the answer
        to 'what happened to X' is a history, so it is ordered by when things happened."""
        c = conn or self.db
        return c.execute("""SELECT c.i, c.j, c.b FROM cell c JOIN edge e ON e.cell=c.i
                            WHERE e.endpoint=? AND c.i IN (SELECT i FROM active)
                            ORDER BY c.t""", (X,)).fetchall()

    def counts(self):
        q = lambda s: self.db.execute(s).fetchone()[0]
        return (q("SELECT count(*) FROM cell"), q("SELECT count(*) FROM edge"), q("SELECT count(*) FROM active"))

    # --- sync (delta = union of rows by id; edges rebuilt by trigger on import) ---
    def export_rows(self, after_rt=None):
        """Rows to ship, filtered on RECORD time rather than event time.

        This distinction is the reason for the second column. A cell authored today about a
        measurement from 2019 has t=2019 and rt=today; filtering on t would place it behind
        every watermark and it would never reach a sibling. Filtering on rt ships it once,
        when it was written."""
        if after_rt is None:
            return self.db.execute("SELECT i,j,b,t,rt FROM cell").fetchall()
        return self.db.execute("SELECT i,j,b,t,rt FROM cell WHERE rt IS NULL OR rt>?",
                               (after_rt,)).fetchall()

    def import_rows(self, rows) -> int:
        """Accepts 5-tuples (i,j,b,t,rt). 4-tuples from an older peer are taken as (i,j,b,t)
        with rt unknown, so a mixed-version fleet keeps syncing."""
        n = 0
        for r in rows:
            if len(r) == 4: r = (r[0], r[1], r[2], r[3], None)
            n += self.db.execute("INSERT OR IGNORE INTO cell(i,j,b,t,rt) VALUES(?,?,?,?,?)", r).rowcount
        self.db.commit(); return n

def borrow(remote_path, X):
    """Remote query: open a sibling read-only and ask for its active Hom(-, X). Imports nothing."""
    rem = sqlite3.connect(f"file:{remote_path}?mode=ro", uri=True)
    rows = rem.execute("""SELECT c.i, c.j, c.b FROM cell c JOIN edge e ON e.cell=c.i
                          WHERE e.endpoint=? AND c.i IN (SELECT i FROM active)
                          ORDER BY c.t""", (X,)).fetchall()
    rem.close(); return rows

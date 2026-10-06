#!/usr/bin/env python3
"""The two dialects must not drift. This is the test that stops them.

A laptop instance is copied into the Timescale hub column for column, so the
SQLite and Postgres genomes are not two schemas that happen to resemble each
other: they are one schema with two spellings. Hand-maintained, they drifted
twice in a single afternoon, which is why both are now generated from genome.py
and why this runs in CI.
"""
import os, sys, sqlite3, tempfile
import genome

HERE = os.path.dirname(os.path.abspath(__file__))
ok = True


def check(label, cond, detail=""):
    global ok
    print(("   [PASS] " if cond else "   [FAIL] ") + label + (("  " + detail) if detail and not cond else ""))
    if not cond:
        ok = False


print("1. every generated file is what genome.py emits")
ROOT = os.path.dirname(HERE)
for dialect, paths in genome.FILES.items():
    want = genome.ddl(dialect)
    for rel in paths:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        have = open(path, encoding="utf8").read() if os.path.exists(path) else None
        check("%s matches genome.ddl(%r)" % (rel, dialect), have == want,
              "run `python genome.py --write`")

print()
print("1b. no ungenerated schema survives the repo")
# The whole point of the cleanup: a hand-kept .sql beside a generated one is how
# the fourth divergent genome appeared in the first place.
generated = {os.path.normpath(r) for ps in genome.FILES.values() for r in ps}
generated.add(os.path.normpath("cell/migrate-add-rt.sql"))
strays = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "generator")]
    for fn in filenames:
        if fn.endswith(".sql"):
            rel = os.path.normpath(os.path.relpath(os.path.join(dirpath, fn), ROOT))
            if rel not in generated:
                strays.append(rel)
check("no unmanaged .sql files", not strays, "found: %s" % strays)

print()
print("2. both dialects declare the same columns, in the same order")
lite, pg = genome.ddl("sqlite"), genome.ddl("postgres")


def cols(sql, table):
    body = sql.split("CREATE TABLE IF NOT EXISTS %s(" % table, 1)[1].split("\n);", 1)[0]
    out = []
    for line in body.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("--") and not line.startswith("PRIMARY KEY"):
            out.append(line.split()[0])
    return out


cl, cp = cols(lite, "cell"), cols(pg, "cell.cell")
check("cell columns identical", cl == cp, "%s vs %s" % (cl, cp))
check("column order is the copy order", cl == [c[0] for c in genome.COLUMNS])
el, ep = cols(lite, "edge"), cols(pg, "cell.edge")
check("edge columns identical", el == ep, "%s vs %s" % (el, ep))

print()
print("3. every index in the spec reaches both dialects")
for name, _ in genome.INDEXES:
    check("%s present in both" % name, name in lite and name in pg)

print()
print("4. the SQLite genome actually executes, and the table it makes agrees with the spec")
db = sqlite3.connect(os.path.join(tempfile.gettempdir(), "genome_test.db"))
try:
    db.executescript("DROP VIEW IF EXISTS active; DROP TABLE IF EXISTS edge; DROP TABLE IF EXISTS cell;")
    db.executescript(lite)
    live = [r[1] for r in db.execute("PRAGMA table_info(cell)").fetchall()]
    check("executes and PRAGMA agrees with the spec", live == cl, "%s vs %s" % (live, cl))
    idx = {r[1] for r in db.execute("PRAGMA index_list(cell)").fetchall()}
    check("time indexes exist on the live table",
          all(n in idx for n, _ in genome.INDEXES), str(sorted(idx)))
    # A NULL t must stay queryable: content-addressed cells have no event time.
    db.execute("INSERT INTO cell(i,j,b,t,rt) VALUES('x','{\"kind\":\"n\"}',NULL,NULL,1.0)")
    check("a cell with NULL event time inserts",
          db.execute("SELECT count(*) FROM cell WHERE t IS NULL").fetchone()[0] == 1)
finally:
    db.close()

print()
print("ALL PASS" if ok else "FAILURES ABOVE")
sys.exit(0 if ok else 1)

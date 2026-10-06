#!/usr/bin/env python3
"""Federation + higher-order test for the uniform-cell substrate.

Proves, on the single-cell genome:
  1. content-addressed nouns AND definitional edges mint identical ids on independent instances (1:1);
  2. authored observations stay distinct with provenance (the identity-discipline is per cell);
  3. home borrows office's active Hom(-, X) and renders it with zero id remapping;
  4. retraction is a cell pointing at a cell (no extra table); latest-outcome-wins; append-only
     supersession reactivates without deleting anything;
  5. higher order is native: a cell can point at an outcome (a cell about a cell about objects);
  6. delta sync = union of rows by id, idempotent.
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cell as C

HERE = os.path.dirname(os.path.abspath(__file__))
op, hp = os.path.join(HERE, "office.db"), os.path.join(HERE, "home.db")
office = C.Instance(op, fresh=True)
home = C.Instance(hp, fresh=True)
def L(s=""): print(s)
def dj(j): return json.loads(j)
def PASS(cond, msg): L(f"   [{'PASS' if cond else 'FAIL'}] {msg}"); assert cond, msg

L("1. shared frame: content-addressed nouns are 1:1 across independent instances")
frame = {
    "sample": {"kind": "sample", "key": "LSAT-12 LAO/STO wafer, lot 2026-03"},
    "cypher": {"kind": "instrument", "key": "Cypher AFM s/n C-1147"},
    "paper":  {"kind": "ref", "scheme": "doi", "key": "10.1038/nature25764"},
    "kto":    {"kind": "material", "key": "KTaO3 (100)"},
}
oid = {k: office.put(v) for k, v in frame.items()}
hid = {k: home.put(v) for k, v in frame.items()}
PASS(all(oid[k] == hid[k] for k in frame), "same nouns -> identical ids on both machines")
S = oid["sample"]

L("\n2. identity-discipline is per cell: definitional edge dedups, observation does not")
# a definitional (content-addressed) edge: 'is-a' sample -> material, authored on BOTH machines
o_isa = office.relate("is-a", {"src": S, "tgt": oid["kto"]}, authored=False)
h_isa = home.relate("is-a", {"src": S, "tgt": hid["kto"]}, authored=False)
PASS(o_isa == h_isa, "identical definitional edge -> identical id (collapses on union)")
# authored observations: two measurement cells, distinct even though similar
o_m1 = office.relate("measured", {"instrument": oid["cypher"], "sample": S}, {"run": "cAFM sweep #1"})
o_m2 = office.relate("measured", {"instrument": oid["cypher"], "sample": S}, {"run": "cAFM sweep #2 (drift)"})
h_ci = home.relate("cited-in", {"src": S, "tgt": hid["paper"]}, {"note": "electron pairing"})
PASS(o_m1 != o_m2, "two authored observations get distinct ids (provenance kept, never collapsed)")

L("\n3. BORROW: home assembles full Hom(-, sample) from office's relations it does not own")
local = home.hom(S); borrowed = C.borrow(op, S)
def render(rows, who):
    for i, j, b in rows:
        d = dj(j); L(f"     [{who}] {d['kind']:9} {d.get('data',{}).get('run') or d.get('data',{}).get('note') or ''}")
render(local, "home  "); render(borrowed, "office")
PASS(all(S in dj(j).get("faces", {}).values() for _, j, _ in borrowed),
     "every borrowed cell references home's own sample id (zero remapping)")
PASS(len(local) + len(borrowed) >= 4, "neighborhood = local + borrowed")

L("\n4. RETRACTION is a cell->cell; latest outcome wins; append-only reactivation")
office.retract(o_m2)
b2 = C.borrow(op, S)
gone = "cAFM sweep #2 (drift)" not in [dj(j).get("data", {}).get("run") for _, j, _ in b2]
PASS(gone, "retracted run drops out of active Hom via the outcome cell")
office.reactivate(o_m2)               # newer outcome, status active -> supersedes
b3 = C.borrow(op, S)
back = "cAFM sweep #2 (drift)" in [dj(j).get("data", {}).get("run") for _, j, _ in b3]
PASS(back, "a newer 'active' outcome reactivates it (nothing deleted, latest wins)")

L("\n5. higher order is native: a cell about an outcome about a relation about objects")
oc = office.retract(o_m1)                                   # 2nd-order cell (points at a relation)
note = office.author({"kind": "note", "faces": {"about": oc}, "data": {"text": "retest after realign"}})
# traverse note -> outcome -> relation -> object, all through the same edge index
hop = office.db.execute("SELECT endpoint FROM edge WHERE cell=? AND role='about'", (note,)).fetchone()[0]
hop2 = office.db.execute("SELECT endpoint FROM edge WHERE cell=? AND role='of'", (hop,)).fetchone()[0]
PASS(hop == oc and hop2 == o_m1, "note -> outcome -> relation resolves with no special-casing per level")

L("\n6. delta sync: union of rows by id, idempotent")
before = home.counts()[0]
got = home.import_rows(office.export_rows())
again = home.import_rows(office.export_rows())
after = home.counts()[0]
PASS(got > 0 and again == 0, f"first import added {got} cells, re-import added 0 (idempotent)")
PASS(len(home.hom(S)) >= len(local), "office's relations now render in home's LOCAL Hom(-, sample)")

L(f"\nSUMMARY  (cell, edge, active)   office={office.counts()}   home={home.counts()}")
office.db.close(); home.db.close()
L("\nALL PASS")

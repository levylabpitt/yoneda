#!/usr/bin/env python3
"""Delta-file sync + live borrow endpoint, end to end."""
import os, sys, json, threading, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cell as C, sync as S, serve as SV

HERE = os.path.dirname(os.path.abspath(__file__))
def L(s=""): print(s)
def PASS(cond, msg): L(f"   [{'PASS' if cond else 'FAIL'}] {msg}"); assert cond, msg
def ids(inst): return {r[0] for r in inst.db.execute("SELECT i FROM cell").fetchall()}

op, hp = os.path.join(HERE, "s_office.db"), os.path.join(HERE, "s_home.db")
for p in (op, hp):
    for x in (p, p + "-wal", p + "-shm"):
        if os.path.exists(x): os.remove(x)
syncdir = tempfile.mkdtemp(prefix="yoneda-sync-")

office = C.Instance(op, fresh=True)
home = C.Instance(hp, fresh=True)

L("1. delta-file sync converges two instances through a shared folder (no direct connection)")
frame = {"sample": {"kind": "sample", "key": "wafer-42"}, "kto": {"kind": "material", "key": "KTaO3"}}
oid = {k: office.put(v) for k, v in frame.items()}
hid = {k: home.put(v) for k, v in frame.items()}
S_id = oid["sample"]
office.relate("measured", {"instrument": office.put({"kind": "instrument", "key": "Cypher"}), "sample": S_id}, {"run": "#1"})
home.relate("cited-in", {"src": S_id, "tgt": home.put({"kind": "ref", "scheme": "doi", "key": "10.x/y"})}, {"note": "n"})

S.tick(office, syncdir)     # office publishes
S.tick(home, syncdir)       # home imports office, publishes its own
S.tick(office, syncdir)     # office imports home
PASS(ids(office) == ids(home), "both instances hold the identical set of cells after sync")
PASS(len(office.hom(S_id)) == len(home.hom(S_id)) >= 2, "full Hom(-, sample) present on both")

L("\n2. sync is idempotent: another round moves nothing")
r1 = S.tick(office, syncdir); r2 = S.tick(home, syncdir)
PASS(r1["imported"] == 0 and r2["imported"] == 0, f"steady state: no re-import (office {r1}, home {r2})")

L("\n3. new authored cell propagates on the next tick")
before = len(home.hom(S_id))
office.relate("measured", {"instrument": office.put({"kind": "instrument", "key": "Cypher"}), "sample": S_id}, {"run": "#2"})
S.tick(office, syncdir); S.tick(home, syncdir)
PASS(len(home.hom(S_id)) == before + 1, "office's new measurement reached home automatically")

L("\n4. live borrow over HTTP returns active Hom(-, X)")
srv = SV.make_server(op, 0, office.id)
port = srv.server_address[1]
th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
try:
    time.sleep(0.1)
    hom = SV.borrow_http(f"http://127.0.0.1:{port}", S_id)
    PASS(len(hom) >= 1 and all(S_id in v["j"].get("faces", {}).values() for v in hom),
         f"borrowed {len(hom)} cells over HTTP, all referencing the sample id")
finally:
    srv.shutdown(); srv.server_close()

office.db.close(); home.db.close()
for p in (op, hp):
    for x in (p, p + "-wal", p + "-shm"):
        if os.path.exists(x):
            try: os.remove(x)
            except OSError: pass
L("\nALL PASS")

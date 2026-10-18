"""The Yoneda instance this demonstration writes to, and the few queries it needs.

The genome is not reimplemented here. It is the public one, `cell/cell.py` and
`cell/cell.sql` from levylabpitt/yoneda, imported from the local checkout, and
its commit is recorded in the instance as a cell so a reader knows which genome
wrote the rows.

Two identity rules, both from the proposal (Section 2, "What a cell is"):

  file cells     i = sha256 of the bytes themselves, j = {kind:file, sha256, bytes}
  everything     cell.py's own rules: put() for content-addressed definitions,
  else           author() for assertions, which get a uuidv7, an instance, and
                 two times (t = when it happened, rt = when it was written down)
"""
import hashlib
import json
import os
import subprocess
import sys

def _genome_repo():
    """The yoneda checkout whose cell/ this uses: $YONEDA_GENOME, else the repository this
    folder sits inside (as examples/<name>/ of levylabpitt/yoneda), else the usual local clone."""
    if os.environ.get("YONEDA_GENOME"):
        return os.environ["YONEDA_GENOME"]
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        d = os.path.dirname(d)
        if os.path.exists(os.path.join(d, "cell", "cell.py")):
            return d
    return os.path.join(os.path.expanduser("~"), "repos", "yoneda-public")


GENOME_REPO = _genome_repo()
sys.path.insert(0, os.path.join(GENOME_REPO, "cell"))
import cell  # noqa: E402  the public genome, unmodified


def genome_commit():
    try:
        return subprocess.check_output(["git", "-C", GENOME_REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def open_instance(path, fresh=False):
    inst = cell.Instance(path, fresh=fresh)
    return inst


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def put_file(inst, raw: bytes) -> str:
    """A file enters under the hash of its bytes. Same bytes, same cell, on any machine."""
    h = sha256(raw)
    inst._raw(h, {"kind": "file", "sha256": h, "bytes": len(raw)}, None, None, cell.now())
    return h


def j(row_j):
    return json.loads(row_j)


def active_of_kind(inst, kind, **faces):
    """Active cells of one kind whose faces include every role=endpoint given."""
    sql = "SELECT c.i, c.j, c.b, c.t, c.rt FROM active c WHERE json_extract(c.j,'$.kind')=?"
    args = [kind]
    for role, endpoint in faces.items():
        sql += " AND EXISTS (SELECT 1 FROM edge e WHERE e.cell=c.i AND e.role=? AND e.endpoint=?)"
        args += [role, endpoint]
    sql += " ORDER BY c.t, c.i"
    return [(i, json.loads(jj), b, t, rt) for i, jj, b, t, rt in inst.db.execute(sql, args)]


def get(inst, i):
    row = inst.db.execute("SELECT j FROM cell WHERE i=?", (i,)).fetchone()
    return json.loads(row[0]) if row else None


def bytes_of(inst, file_sha, roots):
    """Fetch a file's bytes from wherever a `located` cell says they are, and refuse
    them unless they still hash to the cell's identity.

    roots maps a store's name to where that store is mounted on this machine. The
    instance records which store and which path; only the mount point is local."""
    for _, jj, _, _, _ in active_of_kind(inst, "located", file=file_sha):
        store = get(inst, jj["faces"]["store"])["data"]["name"]
        if store not in roots:
            continue
        p = os.path.join(roots[store], jj["data"]["path"])
        if os.path.exists(p):
            raw = open(p, "rb").read()
            if sha256(raw) == file_sha:
                return raw
            raise ValueError(f"bytes at {p} no longer match {file_sha[:12]}")
    raise FileNotFoundError(file_sha)


def store_blob(inst, raw, store_cell, root, by, ext=".npz"):
    """Write a derived artifact into a content-addressed folder and record it."""
    h = put_file(inst, raw)
    name = h + ext
    p = os.path.join(root, name)
    if not os.path.exists(p):
        with open(p, "wb") as fh:
            fh.write(raw)
    if not active_of_kind(inst, "located", file=h, store=store_cell):
        inst.relate("located", {"file": h, "store": store_cell, "by": by}, {"path": name})
    return h


def experiment(inst, number, cooldown_tag):
    for i, jj, *_ in active_of_kind(inst, "experiment"):
        if jj["data"]["number"] == number and jj["data"]["tag"] == cooldown_tag:
            return i, jj
    raise KeyError(number)


def runs(inst, exp_i):
    """Active runs of an experiment, in acquisition order (event time)."""
    return active_of_kind(inst, "run", experiment=exp_i)


def wiring(inst, exp_i):
    """The active wiring claims for an experiment. Exactly one is expected."""
    return active_of_kind(inst, "wiring", experiment=exp_i)


def is_active(inst, i):
    return inst.db.execute("SELECT 1 FROM active WHERE i=?", (i,)).fetchone() is not None

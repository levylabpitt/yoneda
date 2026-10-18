#!/usr/bin/env python3
"""Rebuild the whole demonstration from nothing but the lab store.

    py rebuild.py --out <folder> --store <lab Data root> [--all] [--deposit <dir>]

(or set LEVYLAB_DATA instead of --store)

Creates <folder>/fig2.yoneda.db and <folder>/derived/, then runs, in order:
ingest (hash and connect), claims (what a person asserts), derive (the
arithmetic, recorded), figure (the projection), verify (the audit). With --all
the whole cooldown folder is ingested, every file, not only the five runs the
figure needs; the figure does not change, because it asks the instance which
runs to use.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.environ.get("LEVYLAB_DATA")      # the root of the lab Data tree on this machine


def run(*args):
    print(">", " ".join(a if " " not in a else f'"{a}"' for a in args[1:]), flush=True)
    subprocess.run([sys.executable, *args], check=True, cwd=HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--store", default=STORE, required=STORE is None)
    ap.add_argument("--figure-image", default=os.path.join(HERE, "reference", "sciadv.adx4761-f2.jpg"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--deposit")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    db, blobs = os.path.join(a.out, "fig2.yoneda.db"), os.path.join(a.out, "derived")
    lab, bl = f"levylab-drive:Data={a.store}", f"fig2-yoneda:blobs={blobs}"
    only = [] if a.all else ["--only", "15", "16", "16A", "17B", "18A", "processed"]
    run(os.path.join(HERE, "ingest.py"), "--db", db, "--store", a.store, "--cooldown", "MNK/SA03018F.20171127",
        *only, "--fresh")
    run(os.path.join(HERE, "claims.py"), "--db", db, "--figure-image", a.figure_image)
    if os.path.exists(os.path.join(HERE, "questions.py")):     # private to the lab instance
        run(os.path.join(HERE, "questions.py"), "--db", db)
    run(os.path.join(HERE, "derive.py"), "--db", db, "--roots", lab, "--blobs", blobs)
    run(os.path.join(HERE, "figure.py"), "--db", db, "--roots", bl, "--out", os.path.join(a.out, "fig2_regenerated.png"),
        "--blobs", blobs)
    run(os.path.join(HERE, "verify.py"), "--db", db, "--roots", lab, bl, "--report", os.path.join(a.out, "verify.json"),
        *(["--deposit", a.deposit] if a.deposit else []))


if __name__ == "__main__":
    main()

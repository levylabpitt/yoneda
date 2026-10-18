#!/usr/bin/env python3
"""Ingest a cooldown folder from the lab store into a Yoneda instance.

    py ingest.py --db fig2.yoneda.db --store <root> --cooldown MNK/SA03018F.20171127 [--only 16 16A 17B 15 18A]

Save first, name by fingerprint, connect later. Every file under the folder
enters as a file cell named by the SHA-256 of its bytes, whatever it is: raw
sweeps, a person's processed .dat files, Igor experiments, binary blobs. A
`located` cell records where those bytes were found. Nothing is copied: the
bytes stay where the lab put them.

Then, for the files this code can read (the acquisition software's .itx), it
connects: one `run` cell per acquisition with the event time read from the
file's own clock, one `experiment` per folder, and the wiring.

The wiring is the instructive part. Each file carries the channel assignment
twice, once typed by the person in the header ("1: 3, current ...") and once
written by LabVIEW in an INDEX block. Both enter as `wiring` claims with their
source. Each claim is then checked against the conductance the instrument
itself computed during the measurement (the R4t wave), and a claim that fails
is retracted by an `outcome` cell that points at the check as its reason. The
claim is not deleted; the `active` view stops returning it.
"""
import argparse
import concurrent.futures as cf
import os
import re

import numpy as np

import itx
import yo

E2H = 7.748091729e-5 / 2          # e^2/h in siemens
HERE = os.path.dirname(os.path.abspath(__file__))
TAG = re.compile(r"^(SA\d{5})([A-Z])\.(\d{8})$")
RUNFILE = re.compile(r"\.(\d{6})\.itx$")


def wave_for(n, waves):
    """Lock-in n is stored as Xn in lock-in mode and as Lockin<n> in IV mode."""
    for name in ("X%d" % n, "Lockin%d" % n):
        if name in waves:
            return name
    return None


def table_claim(header, waves):
    roles = {}
    for n, text in itx.lockin_table(header).items():
        t = text.lower()
        w = wave_for(n, waves)
        if "current" in t and "drain" not in t:
            roles["I"] = w
        elif "v+" in t:
            roles["Vp"] = w
        elif "v-" in t:
            roles["Vm"] = w
    return roles if len(roles) == 3 else None


def index_claim(index, order):
    if not all(k in index for k in ("Current", "Voltage_1", "Voltage_2")):
        return None
    try:
        return {"I": order[index["Current"]], "Vp": order[index["Voltage_1"]], "Vm": order[index["Voltage_2"]]}
    except IndexError:
        return None


def g4t(waves, roles):
    """Four-terminal conductance in e^2/h, G = I / (V- - V+), the convention the instrument's R4t uses."""
    return waves[roles["I"]] / (waves[roles["Vm"]] - waves[roles["Vp"]]) / E2H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--store", required=True, help="root of the lab store (the single place)")
    ap.add_argument("--store-name", default="levylab-drive:Data")
    ap.add_argument("--cooldown", required=True, help="path under the store, e.g. MNK/SA03018F.20171127")
    ap.add_argument("--only", nargs="*", help="experiment numbers to ingest (default: every folder)")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()

    inst = yo.open_instance(a.db, fresh=a.fresh)
    tag = os.path.basename(a.cooldown)
    m = TAG.match(tag)
    sample_id, canvas_letter, date = m.groups()
    instrument_name = a.cooldown.replace("\\", "/").split("/")[0]

    # the code that does this is itself a cell, so every claim below can name it
    code = yo.put_file(inst, open(os.path.join(HERE, "ingest.py"), "rb").read())
    codes = {name: yo.put_file(inst, open(os.path.join(HERE, name), "rb").read()) for name in ("itx.py", "yo.py")}
    store = inst.put({"kind": "store", "data": {"name": a.store_name}})
    genome = inst.put({"kind": "genome", "data": {"repo": "levylabpitt/yoneda", "path": "cell/cell.sql",
                                                  "commit": yo.genome_commit()}})
    activity = inst.relate("ingest", {"code": code, "store": store, "genome": genome,
                                      **{"lib:" + k: v for k, v in codes.items()}},
                           {"cooldown": a.cooldown, "agent": "Claude (Opus 5.5) for J. Levy"})

    sample = inst.put({"kind": "sample", "data": {"id": sample_id}})
    canvas = inst.put({"kind": "canvas", "faces": {"sample": sample}, "data": {"tag": sample_id + canvas_letter}})
    instrument = inst.put({"kind": "instrument", "data": {"name": instrument_name}})
    cooldown = inst.put({"kind": "cooldown", "faces": {"canvas": canvas, "instrument": instrument},
                         "data": {"tag": tag}})

    root = os.path.normpath(os.path.join(a.store, a.cooldown))
    folders = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if a.only:
        num = lambda d: (re.match(r"^\s*([0-9]+[A-Z]?)\s*-", d) or re.match(r"(.*)", d)).group(1)
        folders = [d for d in folders if num(d) in a.only or d in a.only]
    paths = []
    for dp, _, fs in os.walk(root):
        rel = os.path.relpath(dp, root)
        top = rel.split(os.sep)[0]
        if a.only and top not in folders:
            continue
        paths += [os.path.join(dp, f) for f in sorted(fs) if f != "desktop.ini"]
    print(f"{len(paths)} files under {a.cooldown}" + (f" in {folders}" if a.only else ""))

    def load(p):
        with open(p, "rb") as fh:
            return p, fh.read(), os.path.getmtime(p)

    experiments = {}
    first_run = {}
    n_runs = 0
    with cf.ThreadPoolExecutor(16) as pool:
        for k, (p, raw, mtime) in enumerate(pool.map(load, paths)):
            rel = os.path.relpath(p, a.store).replace("\\", "/")
            f = yo.put_file(inst, raw)
            seen = [x for x in yo.active_of_kind(inst, "located", file=f, store=store) if x[1]["data"]["path"] == rel]
            if seen:
                continue                     # these bytes at this path are already in; ingest is idempotent
            inst.relate("located", {"file": f, "store": store, "by": activity}, {"path": rel}, t=mtime)
            folder = os.path.relpath(p, root).split(os.sep)[0]
            rm = RUNFILE.search(p)
            if not rm or os.path.dirname(p) != os.path.join(root, folder):
                continue
            header, waves, index = itx.parse(raw)
            if "time" not in waves:
                continue
            if folder not in experiments:
                num = re.match(r"^\s*([0-9]+\s*[A-Z]?)", folder)
                experiments[folder] = inst.put({"kind": "experiment", "faces": {"cooldown": cooldown},
                                                "data": {"tag": tag, "folder": folder,
                                                         "number": num.group(1).replace(" ", "") if num else folder}})
            t0 = float(waves["time"][0]) - itx.IGOR_EPOCH_TO_UNIX
            data = {"tag": tag, "index": int(rm.group(1)), "header": header,
                    "waves": sorted(waves), "n": int(len(waves["time"]))}
            if "B" in waves:
                data["B_T"] = float(waves["B"][0])
            if "Vsg" in waves:
                data["Vsg_V"] = [float(waves["Vsg"][0]), float(waves["Vsg"][-1])]
            run = inst.relate("run", {"file": f, "experiment": experiments[folder], "by": activity}, data, t=t0)
            n_runs += 1
            if folder not in first_run or data["index"] < first_run[folder][0]:
                first_run[folder] = (data["index"], run, raw, t0)
            if k % 50 == 0:
                print(f"  {k}/{len(paths)} {rel}")

    # wiring: two sources per experiment, each checked against the instrument's own R4t
    for folder, (_, run, raw, t0) in sorted(first_run.items()):
        header, waves, index = itx.parse(raw)
        exp = experiments[folder]
        claims = []
        tc = table_claim(header, waves)
        if tc:
            claims.append(("hand-typed lock-in table in the file header", tc))
        ic = index_claim(index, itx.wave_order(raw))
        if ic:
            claims.append(("LabVIEW INDEX block in the file header", ic))
        for source, roles in claims:
            w = inst.relate("wiring", {"experiment": exp, "evidence": run, "by": activity},
                            {**roles, "source": source, "formula": "G = I/(V- - V+) / (e^2/h)"}, t=t0)
            if "R4t(e2/h)" not in waves:
                continue
            g, r = g4t(waves, roles), waves["R4t(e2/h)"]
            ok = np.abs(r) > 0.3
            ratio = float(np.median(g[ok] / r[ok])) if ok.any() else float("nan")
            chk = inst.relate("check", {"of": w, "against": run, "by": activity},
                              {"test": "median of G(claimed wiring) / R4t(instrument)", "value": ratio,
                               "pass": bool(abs(ratio - 1) < 0.02)})
            print(f"  wiring {folder[:40]:40s} {source[:28]:28s} {roles} ratio={ratio:.4g}")
            if abs(ratio - 1) >= 0.02:
                inst.author({"kind": "outcome", "faces": {"of": w, "because": chk},
                             "data": {"status": "retracted",
                                      "reason": "this wiring does not reproduce the conductance the instrument "
                                                "computed during the measurement"}})
    print("runs", n_runs, "experiments", len(experiments), "cells/edges/active", inst.counts())


if __name__ == "__main__":
    main()

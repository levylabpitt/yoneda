#!/usr/bin/env python3
"""Audit the instance: can the figure be trusted, and does it agree with what was published?

    py verify.py --db fig2.yoneda.db --roots levylab-drive:Data=<path> fig2-yoneda:blobs=<dir> [--deposit <dir>]

Part 1 asks only the instance and the bytes. Every file a derivation used is
re-hashed where its `located` cell says it lives. Every derivation is rerun
from the inputs its faces name, with the parameters its data hold, and the
output is compared by hash with the blob it claims to have produced.

Part 2 is the only place the published deposit (Harvard Dataverse,
doi:10.7910/DVN/J37IY0) is read, and only to compare. Nothing it contains
flows into Part 1 or into the figure.
"""
import argparse
import json
import os
import re

import numpy as np

import pipeline as pl
import yo


def derivations(inst, step):
    return [d for d in yo.active_of_kind(inst, "derivation") if d[1]["data"]["step"] == step]


def part1(inst, roots):
    ok = True
    checked = 0
    by_input = {}
    for i, jj, *_ in derivations(inst, "conductance"):
        f = jj["faces"]
        runs = [f[k] for k in sorted(f) if k.startswith("run:")]
        raw = []
        for r in runs:
            rj = yo.get(inst, r)
            raw.append((yo.bytes_of(inst, rj["faces"]["file"], roots), rj["data"]["B_T"]))   # re-hashes
            checked += 1
        wiring = yo.get(inst, f["wiring:0"])["data"]
        vsg, B, G, _ = pl.g_map(raw, wiring)
        same = yo.sha256(pl.pack(vsg=vsg, B=B, G=G)) == f["output"]
        ok &= same
        by_input[i] = (vsg, B, G)
        print(f"  conductance  {len(runs):3d} runs re-hashed, recomputed output {'matches' if same else 'DIFFERS'} {f['output'][:12]}")
    for i, jj, *_ in derivations(inst, "unjump"):
        vsg, B, G = by_input[jj["faces"]["input"]]
        p = jj["data"]["params"]
        on, jumps = pl.find_jumps(vsg, G, p["onset_level_e2h"], p["jump_threshold_V"], p["jump_noise_factor"])
        Gc, shift = pl.unjump(vsg, G, jumps)
        same = yo.sha256(pl.pack(vsg=vsg, B=B, G=Gc, shift=shift, onset=on)) == jj["faces"]["output"]
        ok &= same
        by_input[i] = (vsg, B, Gc)
        print(f"  unjump       {len(jumps)} jumps, recomputed output {'matches' if same else 'DIFFERS'}")
    for i, jj, *_ in derivations(inst, "transconductance"):
        vsg, B, Gc = by_input[jj["faces"]["input"]]
        T = pl.transconductance(vsg, Gc, jj["data"]["smoothing_sigma_V"])
        Bs, Ts = pl.symmetrize(B, T)
        same = yo.sha256(pl.pack(vsg=vsg, B=Bs, dGdV=Ts)) == jj["faces"]["output"]
        ok &= same
        print(f"  transcond.   recomputed output {'matches' if same else 'DIFFERS'}")
    print(f"  {checked} raw files re-hashed against their cells")
    return ok, by_input


def read_igor_text(p):
    txt = open(p, encoding="latin-1").read().replace("\r\n", "\n").replace("\r", "\n")
    out = {}
    for m in re.finditer(r"WAVES/?[A-Z/=0-9,()]*\s+([^\n]+)\nBEGIN\n(.*?)\nEND", txt, re.S):
        names = [n.strip().strip("'") for n in m.group(1).split("\t") if n.strip()]
        A = np.array([[float(x) for x in l.split()] for l in m.group(2).split("\n") if l.strip()])
        if len(names) == 1 and A.shape[1] > 1:
            out[names[0]] = A
        else:
            for k, n in enumerate(names):
                out[n] = A[:, k]
    return out


def part2(inst, deposit, by_input):
    """Each published curve against the raw sweep it came from; each published map against ours."""
    files = {"17B": ("Helical-Device-A-Conductance_SA03018F.20171127.17B.itx",
                     "Helical-Device-A-Transconductance_SA03018F.20171127.17B.itx"),
             "16A": ("Waveguide-Device-Conductance_SA03018F.20171127.16.itx",
                     "Waveguide-Device-Transconductance_SA03018F.20171127.16.itx")}
    report = {}
    exps = {yo.get(inst, jj["faces"]["experiment"])["data"]["number"]: i
            for i, jj, *_ in derivations(inst, "conductance")}
    for num, (fc, ft) in files.items():
        vsg, B, G = by_input[exps[num]]
        w = read_igor_text(os.path.join(deposit, fc))
        key = lambda s: -1 if "Plot0" in s else int(s.split("_")[1].split(".")[0])
        ys = [w[k] for k in sorted([k for k in w if k.startswith("y_")], key=key)]
        res = []
        for y in ys:                                   # best raw sweep and best uniform V_sg shift
            best = None
            for r in range(len(G)):
                for s in range(-12, 13):
                    lo, hi = max(0, s), len(y) + min(0, s)
                    d = y[lo:hi] - np.roll(G[r], s)[lo:hi]
                    rms = float(np.sqrt(np.mean(d ** 2)))
                    if best is None or rms < best[1]:
                        best = (r, rms, s * float(vsg[1] - vsg[0]))
            res.append(best)
        hi_field = [b for b in res if abs(B[b[0]]) > 4]
        report[num] = {
            "published_curves": len(ys), "raw_sweeps": len(G),
            "published_curve_k_is_raw_sweep": "k+1 (17B), reversed (16A); see README",
            "uniform_vsg_shift_mV_median": round(1e3 * float(np.median([b[2] for b in res])), 3),
            "rms_e2h_median_absB_gt_4T": round(float(np.median([b[1] for b in hi_field])), 4),
            "rms_e2h_median_all": round(float(np.median([b[1] for b in res])), 4)}
        # maps: correlation of our dG/dV_sg with theirs on the measured half, after the same uniform shift
        tj = [d for d in derivations(inst, "transconductance")
              if yo.get(inst, yo.get(inst, d[1]["faces"]["input"])["faces"]["input"]) and
              yo.get(inst, d[1]["faces"]["input"])["faces"]["input"] == exps[num]][0]
        ours = pl.unpack(yo.bytes_of(inst, tj[1]["faces"]["output"], ROOTS))
        D = list(read_igor_text(os.path.join(deposit, ft)).values())[0]
        n = min(D.shape[0], ours["dGdV"].shape[0])
        O = ours["dGdV"][:n]
        shift = int(round(report[num]["uniform_vsg_shift_mV_median"] * 1e-3 / float(vsg[1] - vsg[0])))
        O = np.roll(O, shift, axis=1)[:, :D.shape[1]]
        Dm = D[:n, :O.shape[1]]
        okm = np.isfinite(O) & np.isfinite(Dm)
        okm[:, :20] = okm[:, -20:] = False
        hb = np.abs(ours["B"][:n]) > 3
        c_all = float(np.corrcoef(O[okm], Dm[okm])[0, 1])
        m2 = okm & hb[:, None]
        c_hi = float(np.corrcoef(O[m2], Dm[m2])[0, 1])
        amp = float(np.sum(O[m2] * Dm[m2]) / np.sum(O[m2] ** 2))
        report[num].update({"map_correlation_all_fields": round(c_all, 3), "map_correlation_absB_gt_3T": round(c_hi, 3),
                            "map_amplitude_ratio_published_over_ours_absB_gt_3T": round(amp, 3)})
    return report


ROOTS = {}


def main():
    global ROOTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--deposit", help="folder holding the Dataverse .itx files, for Part 2 only")
    ap.add_argument("--report", help="write the summary as JSON here")
    a = ap.parse_args()
    ROOTS = dict(x.split("=", 1) for x in a.roots)
    inst = yo.open_instance(a.db)

    print("Part 1: the instance against the bytes")
    ok, by_input = part1(inst, ROOTS)
    retracted = inst.db.execute("SELECT count(*) FROM cell WHERE i NOT IN (SELECT i FROM active)").fetchone()[0]
    summary = {"part1_all_recomputations_match": bool(ok), "cells": inst.counts()[0], "edges": inst.counts()[1],
               "retracted_cells": retracted,
               "questions": [jj["data"]["text"] for _, jj, *_ in yo.active_of_kind(inst, "question")],
               "checks": [{"value": jj["data"].get("value", jj["data"].get("value_meV")), "test": jj["data"]["test"]}
                          for _, jj, *_ in yo.active_of_kind(inst, "check")]}
    print("  retracted cells (still present, no longer active):", retracted)
    # the figure, redrawn from the instance alone, must be the bytes the figure cell names
    import subprocess, sys, tempfile
    fig = [d for d in derivations(inst, "figure")][-1]
    tmp = os.path.join(tempfile.gettempdir(), "fig2_verify.png")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "figure.py"),
                    "--db", a.db, "--roots", *a.roots, "--out", tmp], check=True, capture_output=True)
    same = yo.sha256(open(tmp, "rb").read()) == fig[1]["faces"]["output"]
    ok &= same
    summary["figure_rerendered_hash_matches"] = bool(same)
    summary["figure_witnesses"] = sorted(k for k in fig[1]["faces"] if k not in ("output", "code", "by"))
    print(f"  figure redrawn from the instance: {'identical bytes' if same else 'DIFFERS'} ({fig[1]['faces']['output'][:12]})")
    summary["part1_all_recomputations_match"] = bool(ok)
    if a.deposit:
        print("Part 2: against the published deposit")
        summary["part2"] = part2(inst, a.deposit, by_input)
        print(json.dumps(summary["part2"], indent=2))
    if a.report:
        json.dump(summary, open(a.report, "w"), indent=2)
    print("OK" if ok else "FAILED")


if __name__ == "__main__":
    main()

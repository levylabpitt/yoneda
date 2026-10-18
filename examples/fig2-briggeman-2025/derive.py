#!/usr/bin/env python3
"""Compute everything Fig. 2 needs, from raw bytes, recording each step as a cell.

    py derive.py --db fig2.yoneda.db --roots levylab-drive:Data=<path> --blobs <dir>

Nothing here is told which runs to use. It asks the instance: for the paper,
which experiments do active `depicts` claims name; for each experiment, which
runs are active and which wiring claim is active. A retracted wiring or a
retracted panel claim changes the answer without any change to this file.

Each step writes its output as a content-addressed blob and one `derivation`
cell whose faces are its inputs (runs, claims, earlier derivations, the code
by hash) and whose data are its parameters. That is the recipe; anyone holding
the bytes can rerun it and compare hashes.
"""
import argparse
import os

import numpy as np

import pipeline as pl
import yo

HERE = os.path.dirname(os.path.abspath(__file__))
DOI = "10.1126/sciadv.adx4761"
PARAMS = {
    "onset_level_e2h": 1.0,          # the lowest-subband onset is where G first reaches 1 e^2/h
    "jump_threshold_V": 3e-3,        # a gate jump is a step in that onset of more than 3 mV ...
    "jump_noise_factor": 6.0,        # ... and more than 6x the local scatter of the steps around it
    "smoothing_sigma_V": 1.5e-3,     # Gaussian smoothing before d/dV_sg
}


def roots_arg(items):
    return dict(x.split("=", 1) for x in items)


def paper_cell(inst):
    for i, jj, *_ in yo.active_of_kind(inst, "paper"):
        if jj["data"]["doi"] == DOI:
            return i
    raise KeyError(DOI)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--roots", nargs="+", required=True, help="store=path, one per store")
    ap.add_argument("--blobs", required=True, help="folder for derived blobs (content-addressed)")
    a = ap.parse_args()
    roots = roots_arg(a.roots)
    os.makedirs(a.blobs, exist_ok=True)

    inst = yo.open_instance(a.db)
    code = {n: yo.put_file(inst, open(os.path.join(HERE, n), "rb").read()) for n in ("derive.py", "pipeline.py", "itx.py")}
    blobs = inst.put({"kind": "store", "data": {"name": "fig2-yoneda:blobs"}})
    me = inst.relate("derive", {"code": code["derive.py"], "lib:pipeline": code["pipeline.py"],
                                "lib:itx": code["itx.py"]}, {"params": PARAMS})
    paper = paper_cell(inst)

    def record(step, inputs, output_raw, data):
        out = yo.store_blob(inst, output_raw, blobs, a.blobs, me)
        faces = {"output": out, "code": code["pipeline.py"], "by": me, **inputs}
        cell = inst.relate("derivation", faces, {"step": step, **data})
        return cell, out

    experiments = sorted({jj["faces"]["experiment"] for _, jj, *_ in yo.active_of_kind(inst, "depicts", paper=paper)})
    for exp in experiments:
        ej = yo.get(inst, exp)
        num = ej["data"]["number"]
        # independent claims stay distinct cells; when every active one agrees, use it and cite all
        wires = yo.wiring(inst, exp)
        roles = {tuple(w[1]["data"][k] for k in ("I", "Vp", "Vm")) for w in wires}
        if len(roles) != 1:
            raise SystemExit(f"{num}: active wiring claims disagree or are missing: {roles}")
        wire_j = wires[0][1]
        wire_faces = {f"wiring:{k}": w[0] for k, w in enumerate(wires)}
        runs = yo.runs(inst, exp)                     # acquisition order
        raw = [(yo.bytes_of(inst, jj["faces"]["file"], roots), jj["data"]["B_T"]) for _, jj, *_ in runs]

        # 1. conductance, every sweep, as recorded
        vsg, B, G, dropped = pl.g_map(raw, wire_j["data"])
        kept = [r for k, r in enumerate(runs) if k not in dropped]
        inputs = {"experiment": exp, **wire_faces, **{f"run:{k:03d}": r[0] for k, r in enumerate(kept)}}
        g_cell, g_out = record("conductance", inputs, pl.pack(vsg=vsg, B=B, G=G),
                               {"formula": wire_j["data"]["formula"], "wiring": {k: wire_j["data"][k] for k in ("I", "Vp", "Vm")},
                                "sweeps": len(B), "dropped": dropped, "order": "acquisition"})

        # 2. gate jumps, found and removed in the open
        on, jumps = pl.find_jumps(vsg, G, PARAMS["onset_level_e2h"], PARAMS["jump_threshold_V"], PARAMS["jump_noise_factor"])
        Gc, shift = pl.unjump(vsg, G, jumps)
        j_cell, j_out = record("unjump", {"input": g_cell}, pl.pack(vsg=vsg, B=B, G=Gc, shift=shift, onset=on),
                               {"jumps": [{"sweep": k, "B_T": float(B[k]), "jump_mV": round(d * 1e3, 3)} for k, d in jumps],
                                "anchor": "the first sweep acquired; every later sweep is moved by the sum of the jumps before it",
                                "params": {k: PARAMS[k] for k in ("onset_level_e2h", "jump_threshold_V", "jump_noise_factor")}})

        # 3. transconductance, then the mirror the paper applies
        T = pl.transconductance(vsg, Gc, PARAMS["smoothing_sigma_V"])
        Bs, Ts = pl.symmetrize(B, T)
        t_cell, t_out = record("transconductance", {"input": j_cell}, pl.pack(vsg=vsg, B=Bs, dGdV=Ts),
                               {"units": "(e^2/h)/V", "smoothing_sigma_V": PARAMS["smoothing_sigma_V"],
                                "symmetrized": "one-sided field sweep mirrored to the other sign, M(-B) = M(B)"})

        # 4. the paper's own definition of mu0, tested against the claimed calibration
        levers = yo.active_of_kind(inst, "lever-arm", experiment=exp)
        if len(levers) != 1:
            raise SystemExit(f"{num}: {len(levers)} active lever-arm claims; one is needed")
        lv = levers[0][1]["data"]
        i0 = int(np.argmin(np.abs(B)))
        mu_onset = lv["mu0_meV"] + lv["alpha_meV_per_V"] * pl.onset(vsg, Gc[i0], 0.5)
        inst.relate("check", {"of": levers[0][0], "against": j_cell, "by": me},
                    {"test": "mu of the lowest-subband onset (G = 0.5 e^2/h) at the sweep nearest B = 0, "
                             "after jump removal; the paper defines this as mu = 0",
                     "value_meV": round(float(mu_onset), 4), "B_T": float(B[i0])})
        print(f"{num}: {len(B)} sweeps, jumps {[(round(float(B[k]),2), round(d*1e3,2)) for k, d in jumps]}, "
              f"onset at B~0 sits at mu = {mu_onset:+.3f} meV under the claimed calibration")
    print("cells/edges/active", inst.counts())


if __name__ == "__main__":
    main()

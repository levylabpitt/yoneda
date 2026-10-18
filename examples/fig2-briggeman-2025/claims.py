#!/usr/bin/env python3
"""The assertions a person makes about the ingested runs, each with its evidence.

    py claims.py --db fig2.yoneda.db --figure-image f2.jpg

Ingest records what the files are. This records what someone says they mean:
which run is behind which panel of the paper, which lever arm turns gate
voltage into chemical potential. Every one
is an authored cell (uuidv7, an instance, two times), and every one names the
cells it rests on. None of them is a property of a file, so any of them can be
retracted later without touching the data.
"""
import argparse
import os

import yo

TAG = "SA03018F.20171127"
DOI = "10.1126/sciadv.adx4761"
HERE = os.path.dirname(os.path.abspath(__file__))


def processed_blob(inst, needle):
    """A file in the lab's own processed/ folder, found by its recorded path."""
    for i, jj, *_ in yo.active_of_kind(inst, "located"):
        if "/processed/" in jj["data"]["path"] and needle in jj["data"]["path"]:
            return jj["faces"]["file"], jj["data"]["path"]
    raise KeyError(needle)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--figure-image", required=True, help="the published Fig. 2 image, as distributed by PMC")
    a = ap.parse_args()
    inst = yo.open_instance(a.db)

    code = yo.put_file(inst, open(os.path.join(HERE, "claims.py"), "rb").read())
    pmc = inst.put({"kind": "store", "data": {"name": "pmc"}})
    me = inst.relate("assert", {"code": code},
                     {"agent": "Claude (Opus 5.5) for J. Levy",
                      "note": "claims read off the paper, its supplement, and the lab's own folders"})

    paper = inst.put({"kind": "paper", "data": {"doi": DOI, "title": "Engineered chirality of one-dimensional nanowires",
                                                "journal": "Science Advances", "year": 2025, "article": "eadx4761"}})
    fig = yo.put_file(inst, open(a.figure_image, "rb").read())
    inst.relate("located", {"file": fig, "store": pmc, "by": me},
                {"path": "https://pmc.ncbi.nlm.nih.gov/articles/instance/12164949/bin/sciadv.adx4761-f2.jpg"})
    inst.relate("figure-of", {"file": fig, "paper": paper, "by": me}, {"figure": "2"})

    ex = {n: yo.experiment(inst, n, TAG)[0] for n in ("17B", "16A")}
    blob17, path17 = processed_blob(inst, "17B - sweep B, Vsg lockin, superlattice_original_6,8-4")
    blob16, path16 = processed_blob(inst, "16A - sweep B, Vsg lockin, control_original16A_mu_8,14-10")

    # which run is behind which panel
    for panel, n, blob, path, section in (
            ("2A", "17B", blob17, path17, "chiral superlattice"), ("2B", "17B", blob17, path17, "chiral superlattice"),
            ("2C", "16A", blob16, path16, "control waveguide"), ("2D", "16A", blob16, path16, "control waveguide")):
        inst.relate("depicts", {"paper": paper, "experiment": ex[n], "evidence": blob, "by": me},
                    {"panel": panel, "section": section,
                     "product": "waterfall G(mu)" if panel in ("2A", "2C") else "map dG/dmu(B, mu)",
                     "why": f"the experimenter's own processed file for this panel's section is {path.split('/')[-1]!r}, "
                            "whose channel numbers (current wave, voltage pair) match this run's typed lock-in table; "
                            "the caption's section, temperature and field range agree with the run's header"})

    # lever arms, read off the published axes against the raw gate range
    for n, panel, alpha, mu_lo, mu_hi, v_lo, v_hi in (
            ("17B", "2B", None, -0.249, 0.808, -0.030125, 0.099875),
            ("16A", "2D", None, -0.079, 0.393, -0.020125, 0.100125)):
        alpha = (mu_hi - mu_lo) / (v_hi - v_lo)                 # meV per V
        inst.relate("lever-arm", {"experiment": ex[n], "evidence": fig, "paper": paper, "by": me},
                               {"alpha_meV_per_V": round(alpha, 4),
                                "mu0_meV": round(mu_lo - alpha * v_lo, 4),
                                "map": "mu = mu0 + alpha * V_sg",
                                "basis": f"published Fig. {panel}: the mu axis spans {mu_lo} to {mu_hi} meV "
                                         f"(frame edges, measured against the tick marks in the PMC image) over the "
                                         f"raw sweep's V_sg range {v_lo*1e3:.3f} to {v_hi*1e3:.3f} mV",
                                "uncertainty": "about 1% in alpha and 0.005 meV in mu0: one pixel of the published image"})

    print("claims written;", "cells/edges/active", inst.counts())


if __name__ == "__main__":
    main()

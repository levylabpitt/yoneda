#!/usr/bin/env python3
"""Draw Fig. 2 of Briggeman et al., Sci. Adv. 11, eadx4761 (2025), from the instance alone.

    py figure.py --db fig2.yoneda.db --roots fig2-yoneda:blobs=<dir> --out fig2.png

The only inputs are the database and the mount point of the blob store. The
figure is a query: the paper's active `depicts` claims say which experiment is
behind each panel, that experiment's active derivations hold the arrays, and
its active lever-arm claim turns gate voltage into chemical potential. The
finished PNG enters the instance as a file cell with one `derivation` cell
whose faces are every cell it rests on, so a claim about the figure can name
its witnesses.
"""
import argparse
import io
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

import pipeline as pl                                  # noqa: E402
import yo                                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DOI = "10.1126/sciadv.adx4761"
E2H = pl.E2H
STYLE = {   # presentation only: what the published panels show, not anything about the data
    "2A": {"xlim": (-2.45, 0.85), "ylim": (0, 9.2), "offset_mV": -2.0, "anchor": "high field", "stride": 2,
           "label": "Chiral\nsuperlattice"},
    "2C": {"xlim": (-0.1, 0.72), "ylim": (0, 10.2), "offset_mV": 0.56, "anchor": "zero field", "stride": 2,
           "label": "Control\nwaveguide"},
    "2B": {"vmin": -0.45, "vmax": 2.5, "ticks": [0.0, 2.5], "label": "Chiral superlattice"},
    "2D": {"vmin": -1.0, "vmax": 4.6, "ticks": [0, 2, 4], "label": "Control waveguide"},
}
# purple for negative, blue at zero, through green and yellow to red, as in the paper
CMAP = LinearSegmentedColormap.from_list("igorish", [(0.0, "#7b00d4"), (0.13, "#1f5fff"), (0.2, "#2a7fff"),
                                                     (0.36, "#4fe0c0"), (0.47, "#5ee84a"), (0.6, "#f0f020"),
                                                     (0.72, "#ff8a00"), (0.84, "#ff0000"), (1.0, "#ff0000")])


def derivation(inst, step, **faces):
    found = yo.active_of_kind(inst, "derivation", **faces)
    found = [f for f in found if f[1]["data"]["step"] == step]
    if not found:
        raise KeyError(step)
    return found[-1]                                  # the latest active one


def chain(inst, exp):
    """conductance -> unjump -> transconductance, for one experiment."""
    g = [d for d in yo.active_of_kind(inst, "derivation", experiment=exp) if d[1]["data"]["step"] == "conductance"][-1]
    j = derivation(inst, "unjump", input=g[0])
    t = derivation(inst, "transconductance", input=j[0])
    return g, j, t


def draw(inst, roots):
    """The whole figure as a function of the instance. Returns the matplotlib figure,
    the cells it rests on (role -> id), and the panel claims it found."""
    paper = [i for i, jj, *_ in yo.active_of_kind(inst, "paper") if jj["data"]["doi"] == DOI][0]
    panels = {jj["data"]["panel"]: (i, jj) for i, jj, *_ in yo.active_of_kind(inst, "depicts", paper=paper)}
    witnesses = {"paper": paper}

    fig = plt.figure(figsize=(7.33, 6.66), dpi=150)
    pos = {"2A": [0.085, 0.585, 0.37, 0.385], "2B": [0.6, 0.585, 0.36, 0.33],
           "2C": [0.085, 0.085, 0.37, 0.385], "2D": [0.6, 0.085, 0.36, 0.33]}
    for panel in ("2A", "2B", "2C", "2D"):
        claim_i, claim = panels[panel]
        exp = claim["faces"]["experiment"]
        g, jmp, t = chain(inst, exp)
        lv_i, lv, *_ = yo.active_of_kind(inst, "lever-arm", experiment=exp)[0]
        alpha, mu0 = lv["data"]["alpha_meV_per_V"], lv["data"]["mu0_meV"]
        witnesses.update({f"{panel}:claim": claim_i, f"{panel}:lever-arm": lv_i})
        ax = fig.add_axes(pos[panel])
        s = STYLE[panel]
        if panel in ("2A", "2C"):
            witnesses[f"{panel}:data"] = g[0]
            d = pl.unpack(yo.bytes_of(inst, g[1]["faces"]["output"], roots))
            vsg, B, G = d["vsg"], d["B"], d["G"]
            order = np.argsort(-np.abs(B))           # |B| largest at the right, B = 0 at the left
            n = len(order)
            near = {int(np.argmin(np.abs(np.abs(B) - k))) for k in range(0, 19)}
            for rank, r in enumerate(order):
                if rank % s["stride"] and r not in near:
                    continue                          # the paper draws every other sweep, and every whole tesla
                # waterfall offset, a presentation choice: one curve is left where it is (the anchor)
                # and each step away from it moves by offset_mV of V_sg
                steps = rank if s["anchor"] == "high field" else n - 1 - rank
                x = mu0 + alpha * (vsg + steps * s["offset_mV"] * 1e-3)
                black = r in near
                ax.plot(x, G[r], lw=1.0 if black else 0.6, color="k" if black else "#2f6fe0", zorder=3 if black else 2)
            ax.set_xlim(*s["xlim"]); ax.set_ylim(*s["ylim"])
            ax.set_xlabel("μ (meV)"); ax.set_ylabel("G ($e^2/h$)")
            for yv in (2, 4, 6, 8, 10):
                ax.axhline(yv, color="#9bb3d6", lw=0.5, ls=":", zorder=1)
            bend = B[order[0]]
            ax.text(0.03, 0.96, "B = 0 T", transform=ax.transAxes, va="top", fontsize=8,
                    bbox=dict(fc="w", ec="k", lw=0.6, pad=1.5))
            ax.text(0.97, 0.96, f"B = {bend:.0f} T".replace("-", "−"), transform=ax.transAxes, va="top",
                    ha="right", fontsize=8, bbox=dict(fc="w", ec="k", lw=0.6, pad=1.5), zorder=5)
            ax.text(0.97, 0.86, s["label"], transform=ax.transAxes, va="top", ha="right", fontsize=8,
                    bbox=dict(fc="w", ec="none", alpha=0.8, pad=1), zorder=5)
        else:
            witnesses[f"{panel}:data"] = t[0]
            d = pl.unpack(yo.bytes_of(inst, t[1]["faces"]["output"], roots))
            vsg, B, T = d["vsg"], d["B"], d["dGdV"]
            mu = mu0 + alpha * vsg
            dGdmu = T * E2H / (alpha * 1e-3)            # (e^2/h)/V -> S/eV
            dB = np.median(np.diff(B)); dmu = alpha * np.median(np.diff(vsg))
            im = ax.imshow(dGdmu.T, origin="lower", aspect="auto", cmap=CMAP, vmin=s["vmin"], vmax=s["vmax"],
                           extent=[B[0] - dB / 2, B[-1] + dB / 2, mu[0] - dmu / 2, mu[-1] + dmu / 2],
                           interpolation="bilinear")
            ax.set_facecolor("#1f5fff")
            ax.set_xticks([-18, -12, -6, 0, 6, 12, 18]); ax.set_xlim(-18.3, 18.3)
            ax.set_xlabel("B (T)"); ax.set_ylabel("μ (meV)")
            ax.text(0.97, 0.03, s["label"], transform=ax.transAxes, ha="right", va="bottom", color="w", fontsize=8)
            cax = fig.add_axes([pos[panel][0] + 0.17, pos[panel][1] + pos[panel][3] + 0.012, 0.19, 0.018])
            cb = fig.colorbar(im, cax=cax, orientation="horizontal", ticks=s["ticks"])
            cb.ax.xaxis.set_ticks_position("top"); cb.ax.tick_params(labelsize=7)
            fig.text(pos[panel][0] + 0.165, pos[panel][1] + pos[panel][3] + 0.021, "dG/dμ (S/eV)", ha="right", fontsize=8)
        ax.text(-0.17, 1.02, panel[1], transform=ax.transAxes, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=7, direction="in", top=True, right=True)
    fig.text(0.5, 0.005, f"Regenerated from raw acquisitions by query over a Yoneda instance; doi:{DOI}, Fig. 2",
             ha="center", fontsize=6, color="#555")
    return fig, witnesses, panels


def png_bytes(fig):
    """PNG bytes with no timestamp or software tag, so equal figures hash equal."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None}, dpi=150)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blobs", help="if given, the PNG is also stored and recorded as a cell")
    a = ap.parse_args()
    roots = dict(x.split("=", 1) for x in a.roots)
    inst = yo.open_instance(a.db)
    fig, witnesses, panels = draw(inst, roots)
    raw = png_bytes(fig)
    with open(a.out, "wb") as fh:
        fh.write(raw)
    print("wrote", a.out, yo.sha256(raw)[:16])

    if a.blobs:
        code = yo.put_file(inst, open(os.path.join(HERE, "figure.py"), "rb").read())
        blobs = inst.put({"kind": "store", "data": {"name": "fig2-yoneda:blobs"}})
        me = inst.relate("render", {"code": code}, {"style": STYLE})
        out = yo.store_blob(inst, raw, blobs, a.blobs, me, ext=".png")
        cell = inst.relate("derivation", {"output": out, "code": code, "by": me, **witnesses},
                           {"step": "figure", "figure": "2", "panels": sorted(panels)})
        print("figure cell", cell, "with", len(witnesses), "witnesses")


if __name__ == "__main__":
    main()

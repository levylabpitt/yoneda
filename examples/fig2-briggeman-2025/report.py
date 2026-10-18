# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo>=0.24", "numpy", "scipy", "matplotlib", "pillow"]
# ///
import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Fig. 2 from Raw Files")


@app.cell(hide_code=True)
def _():
    # Everything below is read from the instance through the same modules the
    # pipeline used, so the report and the pipeline cannot disagree about the data.
    import io
    import json
    import os
    import sys

    import marimo as mo
    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HERE = str(mo.notebook_dir())
    sys.path.insert(0, HERE)
    import figure as figmod
    import pipeline as pl
    import yo

    return HERE, figmod, io, json, mo, np, os, pl, plt, yo


@app.cell(hide_code=True)
def _(HERE, mo, os, yo):
    # Which instance and where its stores are mounted: `-- --db ... --blobs ... --store ...`
    # on the marimo command line, else the copies shipped beside this notebook. The lab
    # store is optional; without it the report reads only the instance and its blobs.
    _args = mo.cli_args()
    db_path = _args.get("db") or os.path.join(HERE, "instance", "fig2.yoneda.db")
    if not os.path.exists(db_path):
        db_path = os.path.join(HERE, "out", "fig2.yoneda.db")
    blobs_dir = _args.get("blobs") or os.path.join(os.path.dirname(db_path), "derived")
    if not os.path.isdir(blobs_dir):
        blobs_dir = os.path.join(os.path.dirname(db_path), "blobs")
    store_dir = _args.get("store") or os.environ.get("LEVYLAB_DATA")
    mo.stop(not os.path.exists(db_path), mo.callout(mo.md(f"No instance at `{db_path}`."), kind="danger"))
    inst = yo.open_instance(db_path)
    roots = {"fig2-yoneda:blobs": blobs_dir}
    if store_dir and os.path.isdir(store_dir):
        roots["levylab-drive:Data"] = store_dir
    return blobs_dir, db_path, inst, roots, store_dir


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Fig. 2 of the engineered-chirality paper, regenerated from raw files

    Briggeman *et al.*, *Science Advances* **11**, eadx4761 (2025), Fig. 2 shows the conductance and transconductance of a chiral superlattice written at the LaAlO$_3$/SrTiO$_3$ interface and of its straight control waveguide, at 25 mK and 0 to 18 T. This notebook redraws that figure from the 2017 acquisition files, by query over a Yoneda instance. The instance holds every file as a cell named by the SHA-256 of its bytes, every acquisition as a run with two times, and every interpretation (which wiring, which run is in which panel, which lever arm) as a claim with its evidence. The figure is a function of the active claims and nothing else. The data deposit that accompanies the paper (Harvard Dataverse, doi:10.7910/DVN/J37IY0) is not read by any step that makes the figure; it is read only by the audit, to compare.
    """)
    return


@app.cell(hide_code=True)
def _(db_path, inst, json, mo, roots, yo):
    _rows = inst.db.execute(
        "SELECT json_extract(j,'$.kind') k, count(*) n, sum(i IN (SELECT i FROM active)) a "
        "FROM cell GROUP BY k ORDER BY n DESC").fetchall()
    _bang = inst.id
    _genome = [jj["data"] for _, jj, *_ in yo.active_of_kind(inst, "genome")]
    _c, _e, _a = inst.counts()
    mo.vstack([
        mo.md(f"""
    ## The instance

    `{db_path}` holds **{_c:,}** cells and **{_e:,}** edges; **{_c - _a}** cells are retracted (still present, no longer active). Instance `{_bang}`, written on the public genome `{_genome[0]['repo']}` `{_genome[0]['path']}` at commit `{_genome[0]['commit'][:7]}`. Stores mounted here: {", ".join(f"`{k}`" for k in roots)}.
    """),
        mo.ui.table([{"kind": k, "cells": n, "active": a} for k, n, a in _rows], selection=None, page_size=30),
    ])
    return


@app.cell(hide_code=True)
def _(HERE, figmod, inst, mo, os, roots, yo):
    fig2, fig2_witnesses, fig2_panels = figmod.draw(inst, roots)
    fig2_png = figmod.png_bytes(fig2)
    _recorded = [jj for _, jj, *_ in yo.active_of_kind(inst, "derivation") if jj["data"]["step"] == "figure"][-1]
    _same = yo.sha256(fig2_png) == _recorded["faces"]["output"]
    _pub = open(os.path.join(HERE, "reference", "sciadv.adx4761-f2.jpg"), "rb").read()
    mo.vstack([
        mo.md("## Published and regenerated"),
        mo.hstack([
            mo.vstack([mo.image(_pub, width=520), mo.md("Published (PMC12164949).")]),
            mo.vstack([mo.image(fig2_png, width=520),
                       mo.md(f"Redrawn just now from the instance. sha256 `{yo.sha256(fig2_png)[:16]}…`")]),
        ], widths="equal", align="start"),
        mo.callout(mo.md(
            f"The redrawn PNG is {'**byte-identical**' if _same else '**not identical**'} to the one the instance "
            f"recorded as its figure cell, whose {len(fig2_witnesses)} faces are the cells it rests on: "
            + ", ".join(f"`{k}`" for k in sorted(fig2_witnesses))), kind="success" if _same else "warn"),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## One acquisition, as stored

    Run 17B swept the field from −18 T toward zero, one gate sweep per file. Pick a sweep. The cell shown is the row in the instance; the curve is drawn from that run's bytes through the active wiring claim and the active lever arm, so it is the same arithmetic as panel A, without the waterfall offset.
    """)
    return


@app.cell(hide_code=True)
def _(inst, yo):
    exp17 = [i for i, jj, *_ in yo.active_of_kind(inst, "experiment") if jj["data"]["number"] == "17B"][0]
    runs17 = yo.runs(inst, exp17)
    return exp17, runs17


@app.cell(hide_code=True)
def _(mo, runs17):
    sweep = mo.ui.slider(0, len(runs17) - 1, value=50, step=1, label="sweep", show_value=True, full_width=True)
    sweep
    return (sweep,)


@app.cell(hide_code=True)
def _(exp17, inst, json, mo, np, pl, plt, roots, runs17, sweep, yo):
    from datetime import datetime, timezone

    _i, _j, _b, _t, _rt = runs17[sweep.value]
    _shown = {**_j, "data": {**_j["data"], "header": _j["data"]["header"][:4] + ["…"],
                             "waves": _j["data"]["waves"][:6] + ["…"]}}
    _fmt = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _wire = yo.wiring(inst, exp17)[0][1]["data"]
    _lv = yo.active_of_kind(inst, "lever-arm", experiment=exp17)[0][1]["data"]
    _fileid = _j["faces"]["file"]
    _fig, _ax = plt.subplots(figsize=(5.2, 3.2), dpi=110)
    try:
        _raw = yo.bytes_of(inst, _fileid, roots)
        _vsg, _B, _G, _ = pl.g_map([(_raw, _j["data"]["B_T"])], _wire)
        _ax.plot(_lv["mu0_meV"] + _lv["alpha_meV_per_V"] * _vsg, _G[0], color="#1d4fd8", lw=1)
        _src = "the raw file on the lab store, re-hashed against the cell's identity"
    except FileNotFoundError:
        _blob = [d for d in yo.active_of_kind(inst, "derivation", experiment=exp17)
                 if d[1]["data"]["step"] == "conductance"][-1][1]["faces"]["output"]
        _d = pl.unpack(yo.bytes_of(inst, _blob, roots))
        _ax.plot(_lv["mu0_meV"] + _lv["alpha_meV_per_V"] * _d["vsg"], _d["G"][sweep.value], color="#1d4fd8", lw=1)
        _src = "the recorded conductance blob (the lab store is not mounted here)"
    _ax.set_xlabel("μ (meV)"); _ax.set_ylabel("G (e²/h)"); _ax.set_ylim(0, 9)
    _ax.set_title(f"B = {_j['data']['B_T']:.3f} T", fontsize=10)
    _fig.tight_layout()
    mo.hstack([
        mo.vstack([
            mo.md(f"`i` = `{_i}` (authored, uuidv7)  \n`t` = {_fmt(_t)}, from the file's own clock  \n"
                  f"`rt` = {_fmt(_rt)}, when this instance wrote it  \n`file` face = sha256 `{_fileid[:16]}…`"),
            mo.md("```json\n" + json.dumps(_shown, indent=1, ensure_ascii=False) + "\n```"),
        ]),
        mo.vstack([_fig, mo.md(f"Drawn from {_src}.")]),
    ], widths=[1.1, 1], align="start")
    return


@app.cell(hide_code=True)
def _(inst, json, mo, yo):
    _rows = []
    for _i, _j, *_ in yo.active_of_kind(inst, "experiment"):
        _ws = inst.db.execute(
            "SELECT c.i, c.j FROM cell c JOIN edge e ON e.cell=c.i AND e.role='experiment' AND e.endpoint=? "
            "WHERE json_extract(c.j,'$.kind')='wiring' ORDER BY c.t", (_i,)).fetchall()
        for _wi, _wj in _ws:
            _w = json.loads(_wj)["data"]
            _chk = yo.active_of_kind(inst, "check", of=_wi)
            _rows.append({"run": _j["data"]["number"], "source": _w["source"],
                          "current, V+, V-": f"{_w['I']}, {_w['Vp']}, {_w['Vm']}",
                          "G(claim) / G(instrument)": f"{_chk[0][1]['data']['value']:.4g}" if _chk else "no R4t in file",
                          "status": "active" if yo.is_active(inst, _wi) else "retracted"})
    _out = [jj for _, jj, *_ in yo.active_of_kind(inst, "outcome")]
    mo.vstack([
        mo.md(r"""
    ## A correction, as stored

    Each file names its wiring twice, once in the experimenter's typed lock-in table and once in a LabVIEW INDEX block. Both entered as `wiring` claims, and each was checked against the conductance the instrument computed during the measurement (the `R4t` wave in the same file). Where the INDEX block fails it is retracted by an `outcome` cell that names the failed check as its reason. The retracted claim stays in the instance; the `active` view no longer returns it, so no derivation sees it.
    """),
        mo.ui.table(_rows, selection=None),
        mo.md("```json\n" + json.dumps(_out[0], indent=1) + "\n```"),
    ])
    return


@app.cell(hide_code=True)
def _(inst, mo, np, pl, plt, roots, yo):
    _fig, _axs = plt.subplots(1, 2, figsize=(10, 3.4), dpi=110)
    _rows = []
    for _ax, _num in zip(_axs, ("17B", "16A")):
        _exp = [i for i, jj, *_ in yo.active_of_kind(inst, "experiment") if jj["data"]["number"] == _num][0]
        _g = [d for d in yo.active_of_kind(inst, "derivation", experiment=_exp) if d[1]["data"]["step"] == "conductance"][-1]
        _u = [d for d in yo.active_of_kind(inst, "derivation", input=_g[0]) if d[1]["data"]["step"] == "unjump"][-1]
        _d = pl.unpack(yo.bytes_of(inst, _u[1]["faces"]["output"], roots))
        _ax.plot(_d["B"], _d["onset"] * 1e3, ".", ms=3, color="#9aa6b8", label="as recorded")
        _ax.plot(_d["B"], (_d["onset"] - _d["shift"]) * 1e3, ".", ms=3, color="#1d4fd8", label="after jump removal")
        for _jmp in _u[1]["data"]["jumps"]:
            _ax.axvline(_jmp["B_T"], color="#b4381f", lw=0.6, ls=":")
            _rows.append({"run": _num, "B (T)": _jmp["B_T"], "jump (mV)": _jmp["jump_mV"], "sweep": _jmp["sweep"]})
        _ax.set_title(f"run {_num}", fontsize=10); _ax.set_xlabel("B (T)"); _ax.set_ylabel("V_sg at G = 1 e²/h (mV)")
        _ax.legend(fontsize=8, frameon=False)
    _fig.tight_layout()
    _p = _u[1]["data"]["params"]
    mo.vstack([
        mo.md(f"""
    ## Gate jumps, found and removed in the open

    The published maps are free of the discrete gate jumps that the raw sweeps show near zero field, and the published waterfalls keep them. The rule used for the published maps is not recorded, so the step is done here by one stated rule and recorded with its result: a step in the lowest-subband onset between neighbouring sweeps is a jump if it departs from the local trend by more than {_p['jump_threshold_V']*1e3:.0f} mV and by more than {_p['jump_noise_factor']:.0f} times the local scatter. The earliest sweep is the anchor. The 26.6 mV jump in the control run pushes its low-field sweeps past the top of the gate range, which leaves the empty rectangle at the top of panel D; the published panel D has the same rectangle.
    """),
        _fig,
        mo.ui.table(_rows, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(inst, mo, yo):
    _rows = []
    for _i, _j, *_ in yo.active_of_kind(inst, "lever-arm"):
        _num = yo.get(inst, _j["faces"]["experiment"])["data"]["number"]
        _chk = yo.active_of_kind(inst, "check", of=_i)
        _rows.append({"run": _num, "alpha (µeV/mV)": _j["data"]["alpha_meV_per_V"], "mu0 (meV)": _j["data"]["mu0_meV"],
                      "onset at B≈0 under it (meV)": _chk[0][1]["data"]["value_meV"] if _chk else None,
                      "basis": _j["data"]["basis"]})
    mo.vstack([
        mo.md(r"""
    ## Calibration

    The paper writes $\mu = \mu_0 + \alpha V_{sg}$, with $\alpha$ from finite-bias spectroscopy and $\mu_0$ set so that $\mu = 0$ at the lowest-subband onset at $B = 0$. Neither number is stated. Both are read here off the published axes against the raw gate range and entered as a `lever-arm` claim whose evidence is the published image, itself a file cell. The paper's own definition of $\mu_0$ is then tested on the aligned data and stored as a `check`. For the superlattice the onset sits at −0.11 meV rather than 0, because this alignment rule and the one used for the published map differ below about −1.5 T.
    """),
        mo.ui.table(_rows, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(HERE, db_path, json, mo, os, roots):
    _rep = os.path.join(os.path.dirname(db_path), "verify.json")
    _v = json.load(open(_rep)) if os.path.exists(_rep) else {}
    _p2 = _v.get("part2", {})
    _keys = [("uniform_vsg_shift_mV_median", "published curves vs raw sweeps, uniform V_sg shift (mV)"),
             ("rms_e2h_median_absB_gt_4T", "residual after that shift, median, |B| > 4 T (e²/h)"),
             ("map_correlation_absB_gt_3T", "map correlation with published, |B| > 3 T"),
             ("map_amplitude_ratio_published_over_ours_absB_gt_3T", "map amplitude, published / ours, |B| > 3 T"),
             ("map_correlation_all_fields", "map correlation with published, all fields")]
    _rows = [{"test": lab, "superlattice (17B)": _p2.get("17B", {}).get(k), "control (16A)": _p2.get("16A", {}).get(k)}
             for k, lab in _keys]
    _live = "levylab-drive:Data" in roots
    mo.vstack([
        mo.md(f"""
    ## Audit

    `verify.py` has two parts. Part 1 needs only the instance and the bytes: every raw file is re-hashed where its `located` cell says it lives, every derivation is rerun from the inputs and parameters its cell names and compared by hash, and the figure is redrawn. The last run of Part 1 {'passed' if _v.get('part1_all_recomputations_match') else 'did not pass'}{', and the figure redraw matched' if _v.get('figure_rerendered_hash_matches') else ''}. {'The lab store is mounted, so it can be rerun below.' if _live else 'The lab store is not mounted here, so Part 1 is shown as recorded; the figure redraw above is live.'}

    Part 2 is the only code that opens the Dataverse deposit, and it only compares.
    """),
        mo.ui.table(_rows, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(mo, roots):
    rerun = mo.ui.run_button(label="Rerun Part 1 against the lab store", disabled="levylab-drive:Data" not in roots)
    rerun
    return (rerun,)


@app.cell(hide_code=True)
def _(HERE, inst, mo, rerun, roots):
    mo.stop(not rerun.value)
    import contextlib as _contextlib, io as _io, sys as _sys
    _sys.path.insert(0, HERE)
    import verify as _verify

    _buf = _io.StringIO()
    with _contextlib.redirect_stdout(_buf):
        _ok, _ = _verify.part1(inst, roots)
    mo.vstack([mo.callout(mo.md("Part 1 **passed**." if _ok else "Part 1 **failed**."), kind="success" if _ok else "danger"),
               mo.md("```\n" + _buf.getvalue() + "\n```")])
    return


@app.cell(hide_code=True)
def _(inst, mo, yo):
    _qs = []
    for _i, _j, *_ in yo.active_of_kind(inst, "question"):
        _about = yo.get(inst, _j["faces"]["about"])
        _tag = _about["kind"] + (" " + _about["data"]["number"] if _about["kind"] == "experiment" else "")
        _qs.append(f"- *about {_tag}:* {_j['data']['text']}")
    # questions live only in the lab's own instance; a public instance has none and shows nothing here
    mo.md("") if not _qs else mo.md("## Open questions, stored as cells\n\nA reconstruction that disagrees with the experimenter's result is treated as a defect in the reconstruction until shown otherwise, so each disagreement is entered as a question addressed to the person who did the work, with a face pointing at what it is about.\n\n" + "\n".join(_qs))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Rerun it

    ```
    py rebuild.py --out <folder> --store <lab Data root>        # from raw bytes, about 25 s
    py figure.py --db instance/fig2.yoneda.db --roots fig2-yoneda:blobs=instance/derived --out fig2.png
    marimo edit report.py -- --store <lab Data root>              # this notebook, with the live audit
    ```

    The second line needs only the instance and its derived blobs, and reproduces the figure byte for byte. The finite-bias run 18A is ingested and no lever arm is derived from it yet; Fig. 3 of the paper uses the same two runs and would add one derivation and one render.
    """)
    return


if __name__ == "__main__":
    app.run()

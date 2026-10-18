"""The arithmetic, with no database in it.

Every function here is a pure function of arrays and parameters, so that the
cells recording a derivation can name this file by hash and the parameters by
value, and anyone holding the bytes gets the same answer.
"""
import io
import zipfile

import numpy as np
from scipy.ndimage import gaussian_filter1d

import itx

E2H = 7.748091729e-5 / 2          # e^2/h in siemens


def g_map(raw_runs, roles):
    """Stack one gate sweep per field into G(B, V_sg), in units of e^2/h.

    raw_runs: list of (bytes, B_T) in acquisition order. Every sweep must share
    one V_sg grid; a sweep that does not (an aborted last file) is dropped and
    reported, never interpolated onto the grid."""
    vsg, rows, fields, dropped = None, [], [], []
    for k, (raw, b) in enumerate(raw_runs):
        _, w, _ = itx.parse(raw)
        g = w[roles["I"]] / (w[roles["Vm"]] - w[roles["Vp"]]) / E2H
        v = w["Vsg"]
        if vsg is None:
            vsg = v
        if len(v) != len(vsg) or not np.allclose(v, vsg, atol=1e-7):
            dropped.append(k)
            continue
        rows.append(g)
        fields.append(b)
    return np.asarray(vsg), np.asarray(fields), np.asarray(rows), dropped


def onset(vsg, G, level=1.0):
    """V_sg where G first rises through `level` (e^2/h), from the low-gate side."""
    above = np.where(G >= level)[0]
    if not len(above) or above[0] == 0:
        return float("nan")
    i = above[0]
    return float(np.interp(level, [G[i - 1], G[i]], [vsg[i - 1], vsg[i]]))


def find_jumps(vsg, G, level, threshold_V, noise=6.0, window=4):
    """Discrete gate jumps, found in the lowest-subband onset across successive sweeps.

    G is in acquisition order. The onset (V_sg where G first reaches `level`) moves
    smoothly with field; a charge rearrangement moves it all at once. A step between
    neighbouring sweeps that departs from the local trend (the median of the steps
    around it) by more than threshold_V, and by more than `noise` times the local
    scatter of those steps, is a jump; its size is that departure. The second test
    keeps a stretch where the onset is merely noisy (near the edge of the gate range)
    from being read as a run of jumps.
    Returns the onsets and a list of (sweep index, jump in volts)."""
    on = np.array([onset(vsg, g, level) for g in G])
    d = np.diff(on)
    jumps = []
    for k in range(len(d)):
        nb = np.r_[d[max(0, k - window):k], d[k + 1:k + 1 + window]]
        nb = nb[np.isfinite(nb)]
        trend = float(np.median(nb)) if len(nb) else 0.0
        scatter = float(np.median(np.abs(nb - trend))) if len(nb) else 0.0
        dep = d[k] - trend
        if np.isfinite(dep) and abs(dep) > max(threshold_V, noise * scatter):
            jumps.append((k + 1, float(dep)))
    return on, jumps


def unjump(vsg, G, jumps):
    """Shift every sweep after a jump back by the jump, cumulatively. The first sweep
    is the anchor and is never moved. Points shifted past the grid edge become NaN."""
    shift = np.zeros(len(G))
    for k, dv in jumps:
        shift[k:] += dv
    out = np.full_like(G, np.nan)
    for r in range(len(G)):
        out[r] = np.interp(vsg + shift[r], vsg, G[r], left=np.nan, right=np.nan)
    return out, shift


def transconductance(vsg, G, sigma_V):
    """dG/dV_sg along each sweep after Gaussian smoothing of width sigma_V, in (e^2/h)/V.
    NaN edges (from unjump) are filled by the nearest valid value before smoothing and
    restored to NaN after, so they cannot leak a false edge into the derivative."""
    dv = float(np.mean(np.diff(vsg)))
    out = np.full_like(G, np.nan)
    for r, g in enumerate(G):
        ok = np.isfinite(g)
        if ok.sum() < 10:
            continue
        gf = np.interp(np.arange(len(g)), np.where(ok)[0], g[ok])
        t = np.gradient(gaussian_filter1d(gf, sigma_V / dv), dv)
        t[~ok] = np.nan
        out[r] = t
    return out


def symmetrize(B, M):
    """Mirror a one-sided field sweep onto the other side: M(-B) = M(B).

    The paper states transport is symmetric in B (its Fig. S3) and shows its
    maps symmetrized; this is that operation, done in the open."""
    o = np.argsort(B)
    B, M = B[o], M[o]
    if B.mean() < 0:
        return np.concatenate([B, -B[::-1]]), np.concatenate([M, M[::-1]])
    return np.concatenate([-B[::-1], B]), np.concatenate([M[::-1], M])


def pack(**arrays) -> bytes:
    """npz bytes that depend only on the arrays (fixed zip timestamps), so a blob's
    hash is a function of its content and a recomputation can be checked by hash."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for name in sorted(arrays):
            a = io.BytesIO()
            np.lib.format.write_array(a, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            z.writestr(zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0)), a.getvalue())
    return buf.getvalue()


def unpack(raw: bytes):
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        return {k: z[k] for k in z.files}

"""Read the Igor text files the MNK acquisition software wrote in 2017.

One file is one gate sweep. It carries a free-text header (lines starting X//)
that the person running the experiment typed, a machine-written INDEX block
naming which waves hold current and voltage, and one WAVES block per channel.

Nothing here interprets anything. It returns the header lines and the arrays
under the names the file itself gives them.
"""
import re

import numpy as np

IGOR_EPOCH_TO_UNIX = 2082844800.0     # seconds from 1904-01-01 to 1970-01-01

_WAVE = re.compile(r"WAVES/D/N=\((\d+)\)\s+'([^']+)'\s*\nBEGIN\n(.*?)\nEND", re.S)
_INDEX = re.compile(r"<(Side_Gate|Current|Voltage_1|Voltage_2|B_Field)>(\d+)<")


def parse(raw: bytes):
    txt = raw.decode("latin-1").replace("\r\n", "\n").replace("\r", "\n")
    header = [l[3:].rstrip() for l in txt.split("\n") if l.startswith("X//")]
    waves = {}
    for m in _WAVE.finditer(txt):
        name = m.group(2).split(".")[0]          # 'X1.SA03018F.20171127.000050' -> 'X1'
        waves[name] = np.array(m.group(3).split(), dtype=float)
    index = {k: int(v) for k, v in _INDEX.findall(txt)}
    return header, waves, index


def wave_order(raw: bytes):
    """Wave names in file order. The INDEX block refers to waves by position."""
    txt = raw.decode("latin-1")
    return [m.group(2).split(".")[0] for m in _WAVE.finditer(txt.replace("\r", "\n"))]


def lockin_table(header):
    """The hand-typed lock-in table: '1: 3, current, 100uV AC ...' -> {1: 'current ...'}."""
    out, on = {}, False
    for line in header:
        s = line.strip()
        if s.lower().startswith("lockin:"):
            on = True
            continue
        if on:
            m = re.match(r"^(\d)\s*:\s*\d+\s*,\s*(.*)$", s)
            if m:
                out[int(m.group(1))] = m.group(2).strip()
            elif s.startswith("`INDEX`") or not s:
                if out:
                    break
    return out

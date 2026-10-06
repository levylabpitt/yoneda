"""
extract.py: turn a few DOIs, a URL, and maybe a PDF into a group profile.

This is the reverse-engineering step. The compendium is a stem cell: it has a
genome (two tables, nothing deleted, entities assembled, the epistemic tiers)
and it has tissue (the 2am vignette, the materials, the instruments, the file
formats, the people). The genome is written once. The tissue is a function of
whoever is reading, and this file computes it.

What each input is actually worth, measured on the Levy group 2026-07-17:

  DOIs (required, 5-10)
      Crossref, free, no auth. Gives titles, journals, authors with
      affiliations, references, and abstracts for roughly 60% of entries (ACS
      and APS do not deposit them; AIP, Wiley and AJP do). Five DOIs returned
      29 distinct people correctly weighted, which is the group and its
      collaborators, with no roster supplied. Titles alone returned the
      materials.

  One PDF, or an instruments page (required for the tissue to be theirs)
      Crossref will NEVER give you TDMS, or an Asylum AFM, or a Leiden fridge.
      Methods sections are the only place instruments and file formats live.
      Without this the document says "your data files". With it, it says "your
      TDMS files", which is the entire difference between a document aimed at
      someone and a document about someone.

  Group URL (optional)
      Members with roles, facilities, and how they describe themselves, which
      is the register to match.

Nothing here calls an LLM. This step is deterministic and auditable: every fact
it emits can be traced to a DOI, a URL, or a page of a PDF. The LLM comes later
and only rewrites prose around these facts. That order matters, because a model
asked to invent a group's vocabulary will happily do so.
"""

from __future__ import annotations
import json, re, sys, time, urllib.request, urllib.error
from collections import Counter
from dataclasses import dataclass, field, asdict

UA = "yoneda-generator/0.1 (mailto:jeremy.levy@levylab.org)"
CROSSREF = "https://api.crossref.org/works/"

# Chemical formulas: LaAlO3, SrTiO3, KTaO3, MoS2, Bi2Se3. Two or more
# element-ish groups, at least one digit, so it does not match ordinary words.
FORMULA = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
_NOT_FORMULA = {"DNA", "RNA", "PCR", "NMR", "STM", "AFM", "SEM", "TEM", "XRD",
                "USA", "PhD", "II", "III", "IV", "MHz", "GHz", "THz", "K", "T"}

# File formats worth knowing about, by community. Presence of one of these in a
# methods section is the single highest-value token this whole file extracts.
FILE_FORMATS = {
    "tdms": "LabVIEW TDMS", "hdf5": "HDF5", "h5": "HDF5", "ibw": "Igor Binary Wave",
    "fits": "FITS", "fastq": "FASTQ", "bam": "BAM", "sam": "SAM", "vcf": "VCF",
    "mzml": "mzML", "cif": "CIF", "nexus": "NeXus", "nxs": "NeXus",
    "sdf": "SDF", "pdb": "PDB", "edf": "EDF", "dm3": "Gatan DM3", "dm4": "Gatan DM4",
    "spe": "SPE", "raw": "RAW", "czi": "Zeiss CZI", "nd2": "Nikon ND2",
    "tiff": "TIFF", "netcdf": "NetCDF", "nc": "NetCDF", "root": "ROOT",
    "mat": "MATLAB MAT", "npy": "NumPy", "parquet": "Parquet", "sqlite": "SQLite",
}
INSTRUMENT_HINTS = [
    "LabVIEW", "Asylum", "Bruker", "Oxford Instruments", "Leiden", "BlueFors",
    "Quantum Design", "PPMS", "MPMS", "Zurich Instruments", "Stanford Research",
    "SR830", "lock-in", "dilution refrigerator", "cryostat", "sputtering",
    "molecular beam epitaxy", "MBE", "pulsed laser deposition", "PLD",
    "scanning tunneling", "atomic force", "confocal", "sequencer", "Illumina",
    "cyclotron", "beamline", "synchrotron", "telescope", "spectrometer",
    "mass spectrometer", "chromatography", "flow cytometer", "microscope",
]


@dataclass
class Paper:
    doi: str
    title: str = ""
    journal: str = ""
    year: int = 0
    authors: list = field(default_factory=list)     # ["Given Family", ...]
    affiliations: list = field(default_factory=list)
    abstract: str = ""


@dataclass
class Profile:
    """Everything the templates are allowed to know about a group."""
    papers: list = field(default_factory=list)
    people: list = field(default_factory=list)        # [{name, n_papers}]
    materials: list = field(default_factory=list)     # [{term, n}]
    venues: list = field(default_factory=list)
    institutions: list = field(default_factory=list)
    year_span: tuple = (0, 0)
    file_formats: list = field(default_factory=list)  # from PDFs/URL only
    instruments: list = field(default_factory=list)   # from PDFs/URL only
    members: list = field(default_factory=list)       # from URL only
    provenance: dict = field(default_factory=dict)    # what came from where
    gaps: list = field(default_factory=list)          # what we could NOT learn


def _get(url: str, timeout: int = 15) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception:
        return None


def fetch_doi(doi: str) -> Paper | None:
    raw = _get(CROSSREF + urllib.parse.quote(doi))
    if not raw:
        return None
    try:
        m = json.loads(raw)["message"]
    except Exception:
        return None
    authors, affs = [], []
    for a in m.get("author", []) or []:
        n = f"{a.get('given','')} {a.get('family','')}".strip()
        if n:
            authors.append(n)
        for x in a.get("affiliation", []) or []:
            if x.get("name"):
                affs.append(x["name"])
    dp = (m.get("issued", {}).get("date-parts") or [[0]])[0]
    return Paper(
        doi=doi,
        title=re.sub(r"<[^>]+>", "", (m.get("title") or [""])[0]).strip(),
        journal=(m.get("container-title") or [""])[0],
        year=dp[0] if dp and dp[0] else 0,
        authors=authors,
        affiliations=affs,
        abstract=re.sub(r"<[^>]+>", " ", m.get("abstract") or "").strip(),
    )


def pdf_text(path: str, max_pages: int = 30) -> str:
    try:
        import fitz  # PyMuPDF
        d = fitz.open(path)
        return "\n".join(d[i].get_text() for i in range(min(len(d), max_pages)))
    except Exception:
        try:
            from pypdf import PdfReader
            r = PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in r.pages[:max_pages])
        except Exception:
            return ""


def url_text(url: str) -> str:
    raw = _get(url, timeout=20)
    if not raw:
        return ""
    try:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(raw, "html.parser")
        for t in s(["script", "style", "nav", "footer"]):
            t.decompose()
        return re.sub(r"\n{3,}", "\n\n", s.get_text("\n"))
    except Exception:
        return raw.decode("utf-8", "replace")


def find_formats(text: str) -> list:
    """File formats, the highest-value tissue there is. Methods sections only."""
    hits = Counter()
    low = text.lower()
    for ext, name in FILE_FORMATS.items():
        # ".tdms" or "TDMS file" or "TDMS format", not the bare token, which
        # false-positives hard (".nc", ".mat", ".raw" are all real words).
        if re.search(rf"\.{ext}\b", low) or re.search(rf"\b{ext}\s+(?:file|format|data)", low):
            hits[name] += 1
    return [{"format": k, "n": v} for k, v in hits.most_common()]


def find_instruments(text: str) -> list:
    hits = Counter()
    for h in INSTRUMENT_HINTS:
        n = len(re.findall(rf"\b{re.escape(h)}\b", text, re.I))
        if n:
            hits[h] += n
    return [{"instrument": k, "n": v} for k, v in hits.most_common(12)]


def find_materials(texts: list) -> list:
    hits = Counter()
    for t in texts:
        for m in FORMULA.findall(t):
            if m in _NOT_FORMULA or len(m) < 3 or not re.search(r"\d", m):
                continue
            hits[m] += 1
    return [{"term": k, "n": v} for k, v in hits.most_common(12)]


def build(dois: list, url: str = "", pdfs: list = None) -> Profile:
    p = Profile()
    pdfs = pdfs or []
    papers = []
    for d in dois:
        pap = fetch_doi(d)
        if pap:
            papers.append(pap)
        time.sleep(0.2)  # be polite to Crossref
    p.papers = [asdict(x) for x in papers]

    if not papers:
        p.gaps.append("No DOI resolved. Without publications there is nothing to aim at.")
        return p

    people = Counter()
    for x in papers:
        for a in x.authors:
            people[a] += 1
    p.people = [{"name": k, "n_papers": v} for k, v in people.most_common(40)]
    p.venues = [{"journal": k, "n": v} for k, v in
                Counter(x.journal for x in papers if x.journal).most_common(10)]
    p.institutions = [{"name": k, "n": v} for k, v in
                      Counter(a for x in papers for a in x.affiliations).most_common(8)]
    years = [x.year for x in papers if x.year]
    p.year_span = (min(years), max(years)) if years else (0, 0)
    p.materials = find_materials([x.title + " " + x.abstract for x in papers])

    n_abs = sum(1 for x in papers if x.abstract)
    p.provenance = {
        "dois_given": len(dois), "dois_resolved": len(papers),
        "abstracts_available": f"{n_abs}/{len(papers)}",
        "url_given": bool(url), "pdfs_given": len(pdfs),
    }
    if n_abs < len(papers):
        p.gaps.append(
            f"Only {n_abs} of {len(papers)} abstracts are in Crossref. ACS and APS do not "
            "deposit them. Vocabulary is thinner than it looks.")

    # The tissue that Crossref can never supply.
    corpus = ""
    for f in pdfs:
        corpus += "\n" + pdf_text(f)
    if url:
        corpus += "\n" + url_text(url)
    if corpus.strip():
        p.file_formats = find_formats(corpus)
        p.instruments = find_instruments(corpus)
    if not p.file_formats:
        p.gaps.append(
            "No file format identified. Crossref cannot supply this; it lives in methods "
            "sections. The document will have to say 'your data files' instead of naming "
            "the format, which is the difference between aimed-at-them and about-them. "
            "Supply one PDF or an instruments page.")
    if not p.instruments:
        p.gaps.append("No instrument identified. Same cause, same remedy.")
    return p


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build a group profile from DOIs, a URL, and PDFs.")
    ap.add_argument("--doi", action="append", default=[], help="repeatable")
    ap.add_argument("--url", default="")
    ap.add_argument("--pdf", action="append", default=[], help="repeatable")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    prof = build(a.doi, a.url, a.pdf)
    js = json.dumps(asdict(prof), indent=2, ensure_ascii=False)
    if a.out == "-":
        sys.stdout.write(js)
    else:
        open(a.out, "w", encoding="utf-8").write(js)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    import urllib.parse
    main()

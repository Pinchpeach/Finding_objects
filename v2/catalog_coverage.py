"""Which archives a search could not reach, and what the classification loses (2.36.0).

Each collector fails independently (network, archive outage, budget), and
the pipeline then classifies with whatever arrived.  On the 18 independent
fields (2.35.0) unreachable archives were the most common cause of a worse
result: without Legacy Surveys the UNKNOWN fraction rose to 39-68 %, and
without Gaia stars lose their decisive parallax/proper-motion evidence.
A result produced without them must say so, field by field.

``summarize(raw_dir)`` reads Get_data/controller.py's collection summary and
returns the failed collectors with the evidence each one supplies
(``IMPACT``); ``write`` stores it as ``catalog_coverage.json`` next to the
results, which the app shows as a warning banner.

2.57.0: the same information is also written *into* the result tables
(``annotate``: columns ``run_archives_status`` / ``run_archives_missing``).
The JSON file and the console / app warning are lost when only the CSV is
passed on, and on 2026-11-23 the same 2' COSMOS search gave 270 rows (24 high
confidence) when Legacy Surveys timed out and 3,582 rows (786) on the next
run: whoever holds only the first file must be able to see that it is
incomplete.  Columns rather than a comment header, because ``pd.read_csv``
(and the app) read a ``#`` line as data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

FILE = "catalog_coverage.json"
FAILED = ("error", "timeout")
COL_STATUS = "run_archives_status"
COL_MISSING = "run_archives_missing"
# values of COL_STATUS
COMPLETE = "complete"  # every attempted archive answered (ok / empty / outside its footprint)
KEY_MISSING = "key_archives_missing"  # a key archive failed: labels may be much less certain
OTHER_MISSING = "archives_missing"  # only non-key archives failed (radio, X-ray, spectra, labels)
DEGRADED = "degraded"  # nothing failed, but an archive answered from a reduced alternative source
UNKNOWN = "unknown"  # no collection summary: files collected elsewhere

# collector -> (catalogue, what the classification loses without it, key)
# "key" archives carry evidence most objects depend on (Stage 4 rules / the
# fitted fusion); the others affect a subset (radio, X-ray, spectra, labels).
IMPACT = {
    "gaia_dr3": ("Gaia DR3", "parallax / proper motion (decisive STAR evidence), DSC class probabilities", True),
    "gaia_dr3_variability_sos_vizier": ("Gaia DR3 variability", "variable-star sub-classes", False),
    "sdss_dr18": ("SDSS DR18 imaging", "SDSS morphology and u-band colours", False),
    "panstarrs1": (
        "Pan-STARRS1 DR2",
        "PS1 morphology and colours (the main optical data outside Legacy Surveys)",
        True,
    ),
    "desi_legacy": ("DESI Legacy Surveys DR10", "deep morphology and the faint-object (LS-GBM) classifier", True),
    "galex": ("GALEX", "UV colours", False),
    "twomass": ("2MASS", "near-IR colours of bright stars", False),
    "allwise": ("AllWISE", "mid-IR AGN colours (QSO evidence)", True),
    "lotss": ("LoTSS DR2", "radio detections", False),
    "first": ("FIRST", "radio detections", False),
    "nvss": ("NVSS", "radio detections", False),
    "tgss": ("TGSS ADR1", "radio detections", False),
    "vlass": ("VLASS", "radio detections", False),
    "xmm": ("4XMM", "X-ray detections (AGN evidence)", False),
    "chandra": ("Chandra CSC", "X-ray detections (AGN evidence)", False),
    "erosita": ("eROSITA eRASS1", "X-ray detections (AGN, clusters)", False),
    "mystix_mpcm": ("MYStIX MPCM", "young-star members of massive star-forming regions", False),
    "sdss_spectroscopy": ("SDSS spectroscopy", "spectroscopic classes and redshifts", False),
    "desi_spectroscopy": ("DESI DR1 spectroscopy", "spectroscopic classes and redshifts", False),
    "desi_fastspec": ("DESI FastSpecFit", "emission-line sub-classes", False),
    "lamost_spectroscopy": ("LAMOST DR5", "spectroscopic classes and stellar parameters", False),
    "ztf_periodic": ("ZTF periodic variables", "variable-star sub-classes", False),
    "atnf_pulsar": ("ATNF pulsars", "pulsar labels", False),
    "bzcat": ("Roma-BZCAT", "blazar labels", False),
    "agb_suh2021": ("AGB catalogue (Suh 2021)", "AGB labels", False),
    "sga2020": ("Siena Galaxy Atlas", "large-galaxy grouping", False),
    "galaxy_zoo_desi": ("Galaxy Zoo DESI", "galaxy morphology sub-class", False),
    "galaxy_clusters": ("galaxy cluster catalogues", "cluster membership", False),
    "simbad": ("SIMBAD", "literature labels", False),
    "ned": ("NED", "literature labels", False),
}


# Archives that answered from an alternative source which lacks products of the primary one
# (2.57.0).  Such a collector is "ok" in the collection summary, so nothing told the user that
# e.g. Gaia came from the VizieR copy.  collector -> (raw file prefix, status column, status value,
# source, what the classification lacks).  The Gaia list is what _vizier_fallback leaves empty
# (WORK_REPORT_2026-11-23b.md measures what that changes); the PS1 copy: practical-use probe,
# 2026-11-15 (panstarrs1.py).  The Legacy Surveys viewer catalogue serves the same rows and columns
# as the Data Lab TAP, so it is not listed.
ALTERNATIVE = {
    "gaia_dr3": (
        "gaia_dr3_ra",
        "gaia_base_query_status",
        "vizier_fallback",
        "the VizieR I/355 copy",
        # ESP-UCD and FLAME come from I/355/paramp since the 2.57.0 review; the 9 variability summary
        # flags (gaia_source in_vari_*) have no VizieR copy (I/358 holds the classifications, not the flags).
        (
            "variability summary flags (in_vari_*: Gaia AGN / compact-companion candidates)",
            "G / BP / RP fluxes, bp_g, g_rp, rv_nb_transits",
        ),
    ),
    "panstarrs1": (
        "panstarrs1_ra",
        "ps1_query_status",
        "vizier_fallback",
        "the VizieR II/389 copy",
        ("aperture magnitudes", "objects with only two detections"),
    ),
}


# Collectors whose primary source never writes the status column: an empty answer that still has the column
# in its header came from the alternative source (PR #73 review: PS1 from the VizieR copy with no rows was
# read as "complete" -- and the copy omits sources with two detections that MAST would return).
EMPTY_HEADER_MARKS = frozenset({"panstarrs1"})


def _alternative(raw_dir: Path, failed: set) -> list[dict]:
    """Collectors that answered from an alternative source (see ``ALTERNATIVE``)."""
    out = []
    for collector, (prefix, column, value, source, lacks) in ALTERNATIVE.items():
        if collector in failed:
            continue
        for path in sorted(Path(raw_dir).glob(f"{prefix}*.csv")):
            try:
                st = pd.read_csv(path, usecols=[column], dtype=str, keep_default_na=False)[column]
            except (ValueError, OSError):  # a file without the column: the primary source's output
                continue
            if (st == value).any() or (st.empty and collector in EMPTY_HEADER_MARKS):
                out.append(
                    {
                        "collector": collector,
                        "catalog": IMPACT.get(collector, (collector,))[0],
                        "source": source,
                        "lacks": list(lacks),
                    }
                )
            break
    return out


def summarize(raw_dir: Path) -> dict:
    """Failed collectors of the run whose raw files are in ``raw_dir``.

    No collection summary (classification of files collected elsewhere)
    gives ``known: False`` rather than a false all-clear."""
    files = sorted(Path(raw_dir).glob("collection_summary_*.csv")) if raw_dir else []
    if not files:
        return {"known": False, "failed": [], "key_failed": False}
    s = pd.read_csv(files[-1], keep_default_na=False)
    failed = []
    for r in s[s.status.isin(FAILED)].itertuples():
        name, role, key = IMPACT.get(r.collector, (r.collector, "", False))
        failed.append(
            {
                "collector": r.collector,
                "catalog": name,
                "status": r.status,
                "impact": role,
                "key": bool(key),
                "error": str(r.error)[:200],
            }
        )
    return {
        "known": True,
        "attempted": int(len(s)),
        "failed": failed,
        "key_failed": any(f["key"] for f in failed),
        "alternative": _alternative(raw_dir, {f["collector"] for f in failed}),
        # the folder these results were classified from: --retry-failed asks this search again,
        # not another search that happens to share the work folder (2.57.0)
        "raw_dir": str(raw_dir),
    }


def write(work: Path, raw_dir: Path) -> dict:
    cov = summarize(raw_dir)
    (Path(work) / FILE).write_text(json.dumps(cov, indent=1), encoding="utf-8")
    return cov


def status(cov: dict | None) -> str:
    """``COL_STATUS`` value of a coverage summary (``summarize`` / ``read``)."""
    if not cov or not cov.get("known"):
        return UNKNOWN
    if not cov.get("failed"):
        return DEGRADED if cov.get("alternative") else COMPLETE
    return KEY_MISSING if any(f.get("key") for f in cov["failed"]) else OTHER_MISSING


def missing(cov: dict | None) -> str:
    """``COL_MISSING`` value: ``collector:status`` of every failed archive,
    key archives first, ``|``-separated like the ``catalogs`` column."""
    failed = sorted((cov or {}).get("failed", []), key=lambda f: (not f.get("key"), f["collector"]))
    alt = sorted((cov or {}).get("alternative", []), key=lambda a: a["collector"])
    return "|".join(
        [f"{f['collector']}:{f['status']}" for f in failed] + [f"{a['collector']}:alternative_source" for a in alt]
    )


def annotate(df: pd.DataFrame, cov: dict | None) -> pd.DataFrame:
    """Add the run-level completeness columns (the same value in every row)."""
    df = df.copy()
    df[COL_STATUS] = status(cov)
    df[COL_MISSING] = missing(cov)
    return df


def read(work: Path) -> dict | None:
    try:
        return json.loads((Path(work) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def message(cov: dict | None) -> str:
    """One warning line for the app / log, or "" when nothing is missing."""
    if not cov:
        return ""
    lines = []
    if cov.get("failed"):
        key = [f for f in cov["failed"] if f.get("key")]
        other = [f for f in cov["failed"] if not f.get("key")]
        parts = [f"{f['catalog']} ({f['impact']})" for f in key] + [f["catalog"] for f in other]
        head = "Unavailable archives — classes may be less certain" if key else "Unavailable archives"
        lines.append(f"{head}: " + "; ".join(parts))
    if cov.get("alternative"):
        parts = [f"{a['catalog']} from {a['source']} (without {', '.join(a['lacks'])})" for a in cov["alternative"]]
        lines.append("Reduced alternative source — " + "; ".join(parts))
    return " | ".join(lines)

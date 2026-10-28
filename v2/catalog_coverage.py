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
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

FILE = "catalog_coverage.json"
FAILED = ("error", "timeout")

# collector -> (catalogue, what the classification loses without it, key)
# "key" archives carry evidence most objects depend on (Stage 4 rules / the
# fitted fusion); the others affect a subset (radio, X-ray, spectra, labels).
IMPACT = {
    "gaia_dr3": ("Gaia DR3", "parallax / proper motion (decisive STAR evidence), DSC class probabilities", True),
    "gaia_dr3_variability_sos_vizier": ("Gaia DR3 variability", "variable-star sub-classes", False),
    "sdss_dr18": ("SDSS DR18 imaging", "SDSS morphology and u-band colours", False),
    "panstarrs1": ("Pan-STARRS1 DR2", "PS1 morphology and colours (the main optical data outside Legacy Surveys)", True),
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
    "galaxy_clusters": ("galaxy cluster catalogues", "cluster membership", False),
    "simbad": ("SIMBAD", "literature labels", False),
    "ned": ("NED", "literature labels", False),
}


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
            {"collector": r.collector, "catalog": name, "status": r.status, "impact": role, "key": bool(key), "error": str(r.error)[:200]}
        )
    return {
        "known": True,
        "attempted": int(len(s)),
        "failed": failed,
        "key_failed": any(f["key"] for f in failed),
    }


def write(work: Path, raw_dir: Path) -> dict:
    cov = summarize(raw_dir)
    (Path(work) / FILE).write_text(json.dumps(cov, indent=1), encoding="utf-8")
    return cov


def read(work: Path) -> dict | None:
    try:
        return json.loads((Path(work) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def message(cov: dict | None) -> str:
    """One warning line for the app / log, or "" when nothing is missing."""
    if not cov or not cov.get("failed"):
        return ""
    key = [f for f in cov["failed"] if f.get("key")]
    other = [f for f in cov["failed"] if not f.get("key")]
    parts = [f"{f['catalog']} ({f['impact']})" for f in key] + [f["catalog"] for f in other]
    head = "Unavailable archives — classes may be less certain" if key else "Unavailable archives"
    return f"{head}: " + "; ".join(parts)

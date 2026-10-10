"""Physical/evolutionary-state axis with conservative independent evidence."""

from __future__ import annotations
import math, sys
from pathlib import Path

AXIS = "physical"
CLASSES = ("WD", "RGB", "AGB", "UNKNOWN")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
from common import load_module, row_num as _num, text as _text  # noqa: E402


def _load_branch(name):
    return load_module(ROOT / "branches" / f"{name}.py", f"classifier_branch_{name}")


STAR = _load_branch("star")
EVOLVED = _load_branch("evolved_star")


def classify(row):
    catalogs = _text(row, "catalogs") or ""
    if "Suh 2021 AGB Catalog" in catalogs:
        assoc = _num(row, "association_confidence__suh_2021_agb_catalog")
        sub = _text(row, "agb_subclass")
        return {
            "axis": AXIS,
            "label": "AGB",
            "confidence": assoc,
            "status": "SUH2021_AGB_CATALOG_MATCH",
            "evidence": [
                {
                    "kind": "suh2021_agb_catalog_counterpart",
                    "agb_subclass": sub,
                    "position_basis": _text(row, "position_basis"),
                    "association_confidence": assoc,
                    "score_semantics": "raw association score; not calibrated posterior",
                }
            ],
        }
    simbad = _text(row, "otype")
    if simbad == "AGB*":
        return {
            "axis": AXIS,
            "label": "AGB",
            "confidence": None,
            "status": "SIMBAD_CURATED_AGB",
            "evidence": [{"kind": "simbad_physical_type", "otype": "AGB*"}],
        }
    coarse = str(row.get("primary_class", "")).strip().upper()
    if coarse in {"GALAXY", "QSO"}:
        return {
            "axis": AXIS,
            "label": "UNKNOWN",
            "confidence": None,
            "status": "NOT_STELLAR_ROUTE",
            "evidence": [{"kind": "coarse_route", "primary_class": coarse}],
        }
    star = STAR.classify(row)
    family = star.get("stellar_family")
    evidence = [
        {
            "kind": "star_branch",
            "stellar_family": family,
            "stellar_family_score": star.get("stellar_family_score"),
            "basis": star.get("basis"),
            "wd_hr_locus_signal": star.get("wd_hr_locus_signal"),
            "spectral_type": star.get("spectral_type"),
            "spectral_type_confidence": star.get("spectral_type_confidence"),
        }
    ]
    if family == "WHITE_DWARF_CANDIDATE":
        return {
            "axis": AXIS,
            "label": "WD",
            "confidence": star.get("stellar_family_score"),
            "status": "CLASSIFIED_WD",
            "evidence": evidence,
        }
    evolved = EVOLVED.classify(row)
    evidence.extend(evolved.get("evidence", []))
    if evolved.get("label") in {"RGB", "AGB"}:
        return {
            "axis": AXIS,
            "label": evolved["label"],
            "confidence": evolved.get("confidence"),
            "status": evolved.get("status", "CLASSIFIED"),
            "evidence": evidence,
        }
    # A stellar-family route establishes only that the object is stellar.  It is
    # not evidence for a physical/evolutionary state, and must not become a
    # catch-all physical class.  In particular, doing so turns missing RGB/AGB
    # evidence into a confident but wrong label in independent truth tests.
    if family in {"STAR_LIKE", "BINARY_CANDIDATE"}:
        return {
            "axis": AXIS,
            "label": "UNKNOWN",
            "confidence": None,
            "status": "STAR_LIKE_NO_VALIDATED_PHYSICAL_STATE",
            "evidence": evidence,
        }
    return {
        "axis": AXIS,
        "label": "UNKNOWN",
        "confidence": None,
        "status": "INSUFFICIENT_PHYSICAL_EVIDENCE",
        "evidence": evidence,
    }

"""Compact-object axis with conservative catalog evidence."""

from __future__ import annotations
import math
import sys as _sys
from pathlib import Path as _Path

_V2 = _Path(__file__).resolve().parents[2]
if str(_V2) not in _sys.path:
    _sys.path.insert(0, str(_V2))
from common import row_num as _num, text as _text  # noqa: E402

AXIS = "compact"
CLASSES = ("NS", "PULSAR", "XRB", "COMPACT_COMPANION_CANDIDATE", "OTHER_COMPACT", "UNKNOWN")


def _bool(row, key):
    v = row.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "1.0", "true", "t", "yes"}


def classify(row):
    catalogs = _text(row, "catalogs") or ""
    if "ATNF Pulsar Catalog" in catalogs:
        assoc = _num(row, "association_confidence__atnf_pulsar_catalog")
        return {
            "axis": AXIS,
            "label": "PULSAR",
            "confidence": assoc,
            "status": "ATNF_CATALOG_MATCH",
            "evidence": [
                {
                    "kind": "atnf_pulsar_catalog_counterpart",
                    "association_confidence": assoc,
                    "score_semantics": "raw association score; not calibrated posterior",
                }
            ],
        }
    simbad = _text(row, "otype")
    if simbad == "N*":
        return {
            "axis": AXIS,
            "label": "NS",
            "confidence": None,
            "status": "SIMBAD_CURATED_NS",
            "evidence": [{"kind": "simbad_physical_type", "otype": "N*"}],
        }
    if simbad == "Psr":
        return {
            "axis": AXIS,
            "label": "PULSAR",
            "confidence": None,
            "status": "SIMBAD_CURATED_PULSAR",
            "evidence": [{"kind": "simbad_physical_type", "otype": "Psr"}],
        }
    if simbad in {"XB*", "LXB", "HXB"}:
        return {
            "axis": AXIS,
            "label": "XRB",
            "confidence": None,
            "status": "SIMBAD_CURATED_XRB",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    if _bool(row, "in_vari_compact_companion"):
        return {
            "axis": AXIS,
            "label": "COMPACT_COMPANION_CANDIDATE",
            "confidence": None,
            "status": "GAIA_DR3_COMPACT_COMPANION_CANDIDATE",
            "evidence": [{"kind": "gaia_dr3_vari_summary", "in_vari_compact_companion": True}],
        }
    return {
        "axis": AXIS,
        "label": "UNKNOWN",
        "confidence": None,
        "status": "NO_VALIDATED_COMPACT_EVIDENCE",
        "evidence": [],
    }

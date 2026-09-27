"""RGB/AGB refinement branch.

This module defines the evidence boundary for evolved stars without inventing
unvalidated RGB/AGB probabilities. It exposes available stellar parameters and
returns UNRESOLVED until a literature-backed, externally validated decision model
is installed.
"""
from __future__ import annotations
import math

REQUIRED_FEATURE_GROUPS={
    "atmosphere":("teff_gspphot","logg_gspphot","mh_gspphot"),
    "astrometry":("parallax","parallax_error"),
    "photometry":("phot_g_mean_mag","phot_bp_mean_mag","phot_rp_mean_mag","bp_rp"),
}

def _num(row,key):
    try:
        value=float(row.get(key))
        return value if math.isfinite(value) else None
    except Exception:
        return None

def classify(row):
    available={}
    for group,keys in REQUIRED_FEATURE_GROUPS.items():
        available[group]={key:_num(row,key) for key in keys}
    present=[key for values in available.values() for key,value in values.items() if value is not None]
    return {
        "label":"UNRESOLVED",
        "confidence":None,
        "status":"AWAITING_VALIDATED_MODEL",
        "evidence":[{
            "kind":"feature_availability",
            "present_features":present,
            "feature_groups":available,
            "note":"RGB/AGB inference intentionally disabled until literature-backed calibration and external validation are installed.",
        }],
    }

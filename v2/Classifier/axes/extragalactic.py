"""Extragalactic refinement axis using coarse routing and Gaia AGN evidence."""

from __future__ import annotations
import functools
import importlib.util as _ilu
from pathlib import Path as _P

_s = _ilu.spec_from_file_location("v2_classifier_rowutil", _P(__file__).resolve().parents[1] / "_rowutil.py")
ROW = _ilu.module_from_spec(_s)
_s.loader.exec_module(ROW)
OTYPES = ROW.OTYPES
_num, _bool = ROW.num, ROW.flag
AXIS = "extragalactic"
_result = functools.partial(ROW.axis_result, AXIS)
CLASSES = ("GALAXY", "AGN", "QSO", "BLAZAR", "OTHER_EXTRAGALACTIC", "UNKNOWN")
# BLAZAR (2.22.0): Roma-BZCAT 5th edition membership (Massaro et al. 2015,
# Ap&SS 357, 75; every source radio-detected with an optical spectrum), type
# from the name prefix (BL Lac / FSRQ / host-dominated BL Lac / uncertain) as
# the subtype; SIMBAD BLL (BL Lac) and Bla (blazar) are the curated route.
SIMBAD_BLAZAR = {"BLL": "BL_LAC", "Bla": None}


def _text(row, key):
    # Upper-cased, unlike the other axes (Roma-BZCAT types, Gaia class names).
    v = ROW.text(row, key)
    return v and v.upper()


def classify(row):
    catalogs = row.get("catalogs") or ""
    if "Roma-BZCAT" in str(catalogs):
        typ = _text(row, "roma_bzcat__blazar_type")
        assoc = _num(row, "association_confidence__roma_bzcat")
        return _result(
            "BLAZAR",
            assoc,
            "ROMA_BZCAT_MATCH",
            [
                {
                    "kind": "roma_bzcat_counterpart",
                    "name": row.get("roma_bzcat__catalog_object_id"),
                    "blazar_type": typ,
                    "redshift": _num(row, "roma_bzcat__z"),
                    "association_confidence": assoc,
                    "score_semantics": "raw association score; not calibrated posterior",
                }
            ],
            subtype=typ,
        )
    ot = row.get("otype") or row.get("simbad__otype")
    ot = str(ot).strip() if ot is not None else ""
    if OTYPES.is_a(ot, "Bla"):
        return _result(
            "BLAZAR",
            None,
            "SIMBAD_CURATED_BLAZAR",
            [{"kind": "simbad_physical_type", "otype": ot}],
            subtype=SIMBAD_BLAZAR.get(ot),
        )
    raw = _text(row, "best_class_name")
    coarse = _text(row, "primary_class")
    if raw == "AGN" or _bool(row, "in_vari_agn"):
        return _result(
            "AGN",
            None,
            "GAIA_DR3_AGN_CANDIDATE",
            [{"kind": "gaia_dr3_variability", "best_class_name": raw, "in_vari_agn": _bool(row, "in_vari_agn")}],
        )
    if coarse in ("QSO", "GALAXY"):  # COARSE_QSO_ROUTE / COARSE_GALAXY_ROUTE
        return _result(coarse, None, f"COARSE_{coarse}_ROUTE", [{"kind": "preprocess_route", "primary_class": coarse}])
    return _result("UNKNOWN", None, "NO_EXTRAGALACTIC_EVIDENCE", [])

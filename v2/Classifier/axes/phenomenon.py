"""Transient/nebular phenomenon axis.

Uses exact curated SIMBAD physical types for PN/nova and Gaia DR3 variability
candidate classes for SN/microlensing. Gaia candidate scores are retained as
catalog evidence, not treated as calibrated probabilities.
"""
from __future__ import annotations
import math
AXIS="phenomenon"
CLASSES=("SN","PN","NOVA","MICROLENSING","OTHER_TRANSIENT","OTHER_PHENOMENON","NONE","UNKNOWN")

def _text(row,key):
    value=row.get(key)
    if value is None:return None
    value=str(value).strip()
    return None if not value or value.lower()=="nan" else value

def _num(row,key):
    try:
        value=float(row.get(key))
        return value if math.isfinite(value) else None
    except Exception:return None

def classify(row):
    catalogs=_text(row,"catalogs") or ""
    if "HASH PN Catalog" in catalogs:
        assoc=_num(row,"association_confidence__hash_pn_catalog")
        return {
            "axis":AXIS,"label":"PN","confidence":None,"status":"HASH_PN_CATALOG_MATCH",
            "evidence":[{"kind":"hash_pn_catalog_counterpart","association_confidence":assoc,
                         "note":"Independent counterpart in the HASH planetary-nebula catalogue."}],
        }
    if "ASAS-SN Supernova Catalog" in catalogs:
        assoc=_num(row,"association_confidence__asas_sn_supernova_catalog")
        subtype=_text(row,"sn_subtype")
        return {
            "axis":AXIS,"label":"SN","confidence":None,"status":"ASASSN_SUPERNOVA_CATALOG_MATCH",
            "evidence":[{"kind":"asas_sn_supernova_catalog_counterpart","association_confidence":assoc,
                         "sn_subtype":subtype,
                         "note":"Independent counterpart in the ASAS-SN bright-supernova catalogue."}],
        }

    simbad=_text(row,"otype")
    if simbad=="SN*":
        return {
            "axis":AXIS,"label":"SN","confidence":None,"status":"SIMBAD_CURATED_SN",
            "evidence":[{"kind":"simbad_physical_type","otype":"SN*","note":"Exact SIMBAD SuperNova physical type."}],
        }
    if simbad=="PN":
        return {
            "axis":AXIS,"label":"PN","confidence":None,"status":"SIMBAD_CURATED_PN",
            "evidence":[{"kind":"simbad_physical_type","otype":"PN","note":"Exact SIMBAD Planetary Nebula physical type."}],
        }
    if simbad=="No*":
        return {
            "axis":AXIS,"label":"NOVA","confidence":None,"status":"SIMBAD_CURATED_NOVA",
            "evidence":[{"kind":"simbad_physical_type","otype":"No*","note":"Exact SIMBAD Classical Nova physical type."}],
        }

    raw=_text(row,"best_class_name")
    score=_num(row,"best_class_score")
    evidence=[] if raw is None else [{
        "kind":"gaia_dr3_vari_classifier_result","best_class_name":raw,
        "best_class_score":score,
        "score_semantics":"Gaia candidate classification score, not a calibrated probability",
    }]
    if raw=="SN":
        return {"axis":AXIS,"label":"SN","confidence":None,"status":"GAIA_DR3_SN_CANDIDATE","evidence":evidence}
    if raw=="MICROLENSING":
        return {"axis":AXIS,"label":"MICROLENSING","confidence":None,"status":"GAIA_DR3_MICROLENSING_CANDIDATE","evidence":evidence}
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VALIDATED_PHENOMENON_EVIDENCE","evidence":evidence}

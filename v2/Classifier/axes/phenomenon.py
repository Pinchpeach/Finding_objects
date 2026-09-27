"""Transient/phenomenon axis from validated catalog evidence currently available.

Gaia DR3 publishes SN and MICROLENSING candidate classes. PN and nova are not
in Gaia vari_classifier_result, so they remain unresolved until dedicated
spectroscopic/catalog-independent evidence modules are implemented.
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

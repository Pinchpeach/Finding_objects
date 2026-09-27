"""Variability axis using published Gaia DR3 variability candidate classes.

best_class_score is retained only as a Gaia catalog score. Gaia documents it as
a median normalized-rank confidence quantity, not a calibrated class probability.
"""
from __future__ import annotations
import math
AXIS="variability"
CLASSES=("RR_LYRAE","CEPHEID","LPV","ECLIPSING","ROTATIONAL","ERUPTIVE","PULSATING","OTHER_VARIABLE","UNKNOWN")

MAP={
    "RR":"RR_LYRAE",
    "CEP":"CEPHEID",
    "LPV":"LPV",
    "ECL":"ECLIPSING",
    "ELL":"ECLIPSING",
    "SOLAR_LIKE":"ROTATIONAL",
    "ACV|CP|MCP|ROAM|ROAP|SXARI":"ROTATIONAL",
    "CV":"ERUPTIVE",
    "RCB":"ERUPTIVE",
    "BCEP":"PULSATING",
    "DSCT|GDOR|SXPHE":"PULSATING",
    "SPB":"PULSATING",
    "ACYG":"PULSATING",
    "SDB":"PULSATING",
    "RS":"OTHER_VARIABLE",
    "S":"OTHER_VARIABLE",
    "SYST":"OTHER_VARIABLE",
    "YSO":"OTHER_VARIABLE",
    "BE|GCAS|SDOR|WR":"OTHER_VARIABLE",
}
EVENT_CLASSES={"SN","MICROLENSING"}
NON_STELLAR={"AGN","GALAXY"}
OTHER_SPECIAL={"EP","WD"}

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
        "kind":"gaia_dr3_vari_classifier_result",
        "best_class_name":raw,
        "best_class_score":score,
        "score_semantics":"Gaia catalog normalized-rank classification score; not used as calibrated probability",
    }]
    if raw in MAP:
        return {"axis":AXIS,"label":MAP[raw],"confidence":None,"status":"GAIA_DR3_VARIABLE_CANDIDATE","evidence":evidence}
    if raw in EVENT_CLASSES:
        return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"ROUTED_TO_PHENOMENON","evidence":evidence}
    if raw in NON_STELLAR:
        return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NON_STELLAR_VARIABILITY_LABEL","evidence":evidence}
    if raw in OTHER_SPECIAL:
        return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"UNMAPPED_GAIA_VARIABILITY_CLASS","evidence":evidence}
    if raw is None:
        return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VARIABILITY_EVIDENCE","evidence":[]}
    return {"axis":AXIS,"label":"OTHER_VARIABLE","confidence":None,"status":"GAIA_DR3_VARIABLE_CANDIDATE","evidence":evidence}

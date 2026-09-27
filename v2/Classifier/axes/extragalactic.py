"""Extragalactic refinement axis using coarse routing and Gaia AGN evidence."""
from __future__ import annotations
AXIS="extragalactic"
CLASSES=("GALAXY","AGN","QSO","OTHER_EXTRAGALACTIC","UNKNOWN")

def _text(row,key):
    value=row.get(key)
    if value is None:return None
    value=str(value).strip()
    return None if not value or value.lower()=="nan" else value.upper()

def _bool(row,key):
    value=row.get(key)
    if value is None:return False
    if isinstance(value,bool):return value
    return str(value).strip().lower() in {"1","1.0","true","t","yes"}

def classify(row):
    raw=_text(row,"best_class_name")
    coarse=_text(row,"primary_class")
    if raw=="AGN" or _bool(row,"in_vari_agn"):
        return {
            "axis":AXIS,"label":"AGN","confidence":None,"status":"GAIA_DR3_AGN_CANDIDATE",
            "evidence":[{"kind":"gaia_dr3_variability","best_class_name":raw,"in_vari_agn":_bool(row,"in_vari_agn")}],
        }
    if coarse=="QSO":
        return {
            "axis":AXIS,"label":"QSO","confidence":None,"status":"COARSE_QSO_ROUTE",
            "evidence":[{"kind":"preprocess_route","primary_class":"QSO"}],
        }
    if coarse=="GALAXY":
        return {
            "axis":AXIS,"label":"GALAXY","confidence":None,"status":"COARSE_GALAXY_ROUTE",
            "evidence":[{"kind":"preprocess_route","primary_class":"GALAXY"}],
        }
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_EXTRAGALACTIC_EVIDENCE","evidence":[]}

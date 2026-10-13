"""Extragalactic refinement axis using coarse routing and Gaia AGN evidence."""
from __future__ import annotations
AXIS="extragalactic"
CLASSES=("GALAXY","AGN","QSO","BLAZAR","OTHER_EXTRAGALACTIC","UNKNOWN")
# BLAZAR (2.22.0): Roma-BZCAT 5th edition membership (Massaro et al. 2015,
# Ap&SS 357, 75; every source radio-detected with an optical spectrum), type
# from the name prefix (BL Lac / FSRQ / host-dominated BL Lac / uncertain) as
# the subtype; SIMBAD BLL (BL Lac) and Bla (blazar) are the curated route.
SIMBAD_BLAZAR={"BLL":"BL_LAC","Bla":None}

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

def _num(row,key):
    try:
        import math
        v=float(row.get(key));return v if math.isfinite(v) else None
    except Exception:return None

def classify(row):
    catalogs=row.get("catalogs") or ""
    if "Roma-BZCAT" in str(catalogs):
        typ=_text(row,"roma_bzcat__blazar_type")
        assoc=_num(row,"association_confidence__roma_bzcat")
        return {"axis":AXIS,"label":"BLAZAR","subtype":typ,"confidence":assoc,"status":"ROMA_BZCAT_MATCH",
                "evidence":[{"kind":"roma_bzcat_counterpart","name":row.get("roma_bzcat__catalog_object_id"),"blazar_type":typ,
                             "redshift":_num(row,"roma_bzcat__z"),"association_confidence":assoc,
                             "score_semantics":"raw association score; not calibrated posterior"}]}
    ot=row.get("otype") or row.get("simbad__otype")
    ot=str(ot).strip() if ot is not None else ""
    if ot in SIMBAD_BLAZAR:
        return {"axis":AXIS,"label":"BLAZAR","subtype":SIMBAD_BLAZAR[ot],"confidence":None,"status":"SIMBAD_CURATED_BLAZAR",
                "evidence":[{"kind":"simbad_physical_type","otype":ot}]}
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

"""Transient/nebular phenomenon axis with independent event and spectroscopy channels.

Raw catalog/association scores are retained as evidence scores. They are not
reported as calibrated posterior probabilities; calibration is a separate stage.
"""
from __future__ import annotations
import math
AXIS="phenomenon"
CLASSES=("SN","PN","NOVA","MICROLENSING","OTHER_TRANSIENT","OTHER_PHENOMENON","NONE","UNKNOWN")

def _text(row,key):
    value=row.get(key)
    if value is None:return None
    value=str(value).strip();return None if not value or value.lower()=="nan" else value

def _num(row,key):
    try:
        value=float(row.get(key));return value if math.isfinite(value) else None
    except Exception:return None

def _event_evidence(row,catalog,kind):
    assoc=_num(row,"association_confidence__"+catalog.lower().replace("-","_").replace(" ","_").replace("/","_").strip("_"))
    event_mjd=_num(row,"event_mjd");obs_mjd=_num(row,"observation_mjd") or _num(row,"obs_mjd")
    dt=None if event_mjd is None or obs_mjd is None else obs_mjd-event_mjd
    return assoc,{"kind":kind,"association_confidence":assoc,"event_mjd":event_mjd,"observation_mjd":obs_mjd,"delta_days":dt,"sn_subtype":_text(row,"sn_subtype"),"note":"Transient event is kept separate from persistent host-galaxy detections; event time is retained when available."}

def _pn_lines(row):
    vals={k:_num(row,k) for k in ("pn_heii_4686","pn_oiii_4363","pn_oiii_5007","pn_halpha","pn_nii_6584","pn_sii_6717","pn_sii_6731")}
    detected={k:v for k,v in vals.items() if v is not None and v>0}
    ratio=None
    if vals["pn_oiii_5007"] and vals["pn_halpha"]:
        ratio=vals["pn_oiii_5007"]/vals["pn_halpha"]
    return detected,ratio

def classify(row):
    catalogs=_text(row,"catalogs") or ""
    if "Acker PN Spectroscopy" in catalogs:
        detected,ratio=_pn_lines(row)
        assoc=_num(row,"association_confidence__acker_pn_spectroscopy")
        if len(detected)>=2:
            return {"axis":AXIS,"label":"PN","confidence":assoc,"status":"PN_SPECTROSCOPY_EVIDENCE","evidence":[{"kind":"pn_emission_line_spectrum","association_confidence":assoc,"detected_lines":detected,"oiii5007_to_halpha":ratio,"note":"Independent Acker V/84 PN spectrum provides multiple nebular emission-line measurements; score remains uncalibrated."}]}
    if "HASH PN Catalog" in catalogs:
        assoc=_num(row,"association_confidence__hash_pn_catalog")
        return {"axis":AXIS,"label":"PN","confidence":assoc,"status":"HASH_PN_CATALOG_MATCH","evidence":[{"kind":"hash_pn_catalog_counterpart","association_confidence":assoc,"pn_catalog_status":_text(row,"pn_catalog_status"),"note":"Independent counterpart in HASH; identity evidence, not a generic spectroscopic classifier."}]}
    if "ASAS-SN Supernova Catalog" in catalogs:
        assoc,ev=_event_evidence(row,"ASAS-SN Supernova Catalog","asas_sn_supernova_event")
        return {"axis":AXIS,"label":"SN","confidence":assoc,"status":"ASASSN_SUPERNOVA_EVENT_MATCH","evidence":[ev]}
    if "Asiago Supernova Catalog" in catalogs:
        assoc,ev=_event_evidence(row,"Asiago Supernova Catalog","asiago_supernova_event")
        return {"axis":AXIS,"label":"SN","confidence":assoc,"status":"ASIAGO_SUPERNOVA_EVENT_MATCH","evidence":[ev]}

    # Generic time-domain branch: only promote an explicit SN light-curve class
    # if an event epoch is present. This avoids treating a host detection as SN.
    lc=_text(row,"transient_lightcurve_class")
    event_mjd=_num(row,"event_mjd")
    if lc and lc.upper().startswith("SN") and event_mjd is not None:
        score=_num(row,"transient_lightcurve_score")
        return {"axis":AXIS,"label":"SN","confidence":score,"status":"TIME_DOMAIN_SN_CANDIDATE","evidence":[{"kind":"event_time_aware_lightcurve","class":lc,"score":score,"event_mjd":event_mjd,"score_semantics":"raw time-domain classifier score; requires per-axis calibration"}]}

    simbad=_text(row,"otype")
    if simbad=="SN*":return {"axis":AXIS,"label":"SN","confidence":None,"status":"SIMBAD_CURATED_SN","evidence":[{"kind":"simbad_physical_type","otype":"SN*"}]}
    if simbad=="PN":return {"axis":AXIS,"label":"PN","confidence":None,"status":"SIMBAD_CURATED_PN","evidence":[{"kind":"simbad_physical_type","otype":"PN"}]}
    if simbad=="No*":return {"axis":AXIS,"label":"NOVA","confidence":None,"status":"SIMBAD_CURATED_NOVA","evidence":[{"kind":"simbad_physical_type","otype":"No*"}]}

    raw=_text(row,"best_class_name");score=_num(row,"best_class_score")
    evidence=[] if raw is None else [{"kind":"gaia_dr3_vari_classifier_result","best_class_name":raw,"best_class_score":score,"score_semantics":"Gaia candidate score; raw evidence, not calibrated probability"}]
    if raw=="SN":return {"axis":AXIS,"label":"SN","confidence":score,"status":"GAIA_DR3_SN_CANDIDATE","evidence":evidence}
    if raw=="MICROLENSING":return {"axis":AXIS,"label":"MICROLENSING","confidence":score,"status":"GAIA_DR3_MICROLENSING_CANDIDATE","evidence":evidence}
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VALIDATED_PHENOMENON_EVIDENCE","evidence":evidence}

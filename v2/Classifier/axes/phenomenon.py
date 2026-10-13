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

# HASH grades its entries True / Likely / Possible PN and also lists mimics,
# post-AGB stars and pre-PNe (Parker, Bojicic & Frew 2016).  True / Likely
# are PN, Possible is a PN candidate, explicit non-PN entries are not PN
# (2.18.0).  An unrecognised or missing status keeps the PN label.
HASH_NON_PN=("NOT","MIMIC","POST","PRE","SYMB","HII","H II","EM*","STAR","GALAXY","SNR","CLUSTER","OTHER")


def _hash_grade(status):
    s=(status or "").strip().upper()
    if not s:return None
    if s in ("T","TRUE") or s.startswith("TRUE"):return "TRUE"
    if s in ("L","LIKELY") or s.startswith("LIKELY"):return "LIKELY"
    if s in ("P","POSSIBLE") or s.startswith("POSSIBLE"):return "POSSIBLE"
    if any(k in s for k in HASH_NON_PN):return "NOT_PN"
    return None


def _sn_epoch_status(ev):
    """Catalogue SN matched long after the event is the host, not the SN."""
    dt=ev.get("delta_days")
    return dt is not None and dt>SN_MAX_DELTA_DAYS


# A catalogued SN is the transient only near its event: an observation more
# than a year after discovery sees the host galaxy (same rule as the
# time-domain branch, which needs an event epoch; 2.18.0).
SN_MAX_DELTA_DAYS=365.0


def classify(row):
    catalogs=_text(row,"catalogs") or ""
    if "Acker PN Spectroscopy" in catalogs:
        # The Strasbourg-ESO catalogue is itself a PN catalogue (Acker et al.
        # 1992): a counterpart is identity evidence, like HASH.  The old
        # ">= 2 positive lines" test only checked that data existed; the
        # ratios used against PN mimics (Frew & Parker 2010) are reported.
        detected,ratio=_pn_lines(row)
        assoc=_num(row,"association_confidence__acker_pn_spectroscopy")
        sii=sum(v for k,v in detected.items() if k.startswith("pn_sii"))
        ha=detected.get("pn_halpha")
        return {"axis":AXIS,"label":"PN","confidence":assoc,"status":"PN_SPECTROSCOPY_EVIDENCE","evidence":[{"kind":"pn_emission_line_spectrum","association_confidence":assoc,"detected_lines":detected,"oiii5007_to_halpha":ratio,"sii_to_halpha":(sii/ha if sii and ha else None),"note":"Acker et al. (1992) Strasbourg-ESO PN catalogue counterpart (identity evidence); [S II]/Ha and [O III]/Ha reported for mimic checks (Frew & Parker 2010)."}]}
    if "HASH PN Catalog" in catalogs:
        assoc=_num(row,"association_confidence__hash_pn_catalog");status=_text(row,"pn_catalog_status");grade=_hash_grade(status)
        ev=[{"kind":"hash_pn_catalog_counterpart","association_confidence":assoc,"pn_catalog_status":status,"hash_grade":grade,"note":"Independent counterpart in HASH; identity evidence, not a generic spectroscopic classifier."}]
        if grade=="NOT_PN":
            return {"axis":AXIS,"label":"OTHER_PHENOMENON","confidence":assoc,"status":"HASH_NON_PN_ENTRY","evidence":ev}
        if grade=="POSSIBLE":
            return {"axis":AXIS,"label":"PN","confidence":assoc,"status":"HASH_POSSIBLE_PN","evidence":ev}
        return {"axis":AXIS,"label":"PN","confidence":assoc,"status":"HASH_PN_CATALOG_MATCH","evidence":ev}
    for cat,kind,status in (("ASAS-SN Supernova Catalog","asas_sn_supernova_event","ASASSN_SUPERNOVA_EVENT_MATCH"),
                            ("Asiago Supernova Catalog","asiago_supernova_event","ASIAGO_SUPERNOVA_EVENT_MATCH")):
        if cat in catalogs:
            assoc,ev=_event_evidence(row,cat,kind)
            if _sn_epoch_status(ev):
                return {"axis":AXIS,"label":"OTHER_PHENOMENON","confidence":assoc,"status":"SN_HOST_PAST_EVENT","evidence":[ev]}
            return {"axis":AXIS,"label":"SN","confidence":assoc,"status":status,"evidence":[ev]}

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

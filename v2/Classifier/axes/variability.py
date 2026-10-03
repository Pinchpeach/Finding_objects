"""Variability axis; catalog scores are raw evidence pending independent calibration."""
from __future__ import annotations
import math
AXIS="variability";CLASSES=("RR_LYRAE","CEPHEID","MIRA","LPV","ECLIPSING","ROTATIONAL","ERUPTIVE","PULSATING","OTHER_VARIABLE","UNKNOWN")
SIMBAD_MAP={"RR*":"RR_LYRAE","Ce*":"CEPHEID","Mi*":"MIRA","LP*":"LPV","EB*":"ECLIPSING","Ro*":"ROTATIONAL","Er*":"ERUPTIVE","Pu*":"PULSATING"}
GAIA_MAP={"RR":"RR_LYRAE","CEP":"CEPHEID","LPV":"LPV","ECL":"ECLIPSING","ELL":"ECLIPSING","SOLAR_LIKE":"ROTATIONAL","ACV|CP|MCP|ROAM|ROAP|SXARI":"ROTATIONAL","CV":"ERUPTIVE","RCB":"ERUPTIVE","BCEP":"PULSATING","DSCT|GDOR|SXPHE":"PULSATING","SPB":"PULSATING","ACYG":"PULSATING","SDB":"PULSATING","RS":"OTHER_VARIABLE","S":"OTHER_VARIABLE","SYST":"OTHER_VARIABLE","YSO":"OTHER_VARIABLE","BE|GCAS|SDOR|WR":"OTHER_VARIABLE"}
EVENT_CLASSES={"SN","MICROLENSING"};NON_STELLAR={"AGN","GALAXY"};OTHER_SPECIAL={"EP","WD"}
def _text(row,key):
 v=row.get(key)
 if v is None:return None
 v=str(v).strip();return None if not v or v.lower()=="nan" else v
def _num(row,key):
 try:
  v=float(row.get(key));return v if math.isfinite(v) else None
 except Exception:return None
def classify(row):
 simbad=_text(row,"otype")
 if simbad in SIMBAD_MAP:return {"axis":AXIS,"label":SIMBAD_MAP[simbad],"confidence":None,"status":"SIMBAD_CURATED_VARIABLE_TYPE","evidence":[{"kind":"simbad_physical_type","otype":simbad}]}
 raw=_text(row,"best_class_name");score=_num(row,"best_class_score")
 evidence=[] if raw is None else [{"kind":"gaia_dr3_vari_classifier_result","best_class_name":raw,"best_class_score":score,"score_semantics":"raw Gaia normalized-rank score; not calibrated probability"}]
 if raw=="LPV":
  freq=_num(row,"lpv_frequency");amp=_num(row,"lpv_amplitude")
  period=None if freq is None or freq<=0 else 1.0/freq
  # Gaia publishes a Fourier semi-amplitude; Sanders (2023) defines a
  # conservative Mira boundary at full Delta-G > 0.865 mag and requires a
  # reported period. Keep this as candidate evidence, not a posterior.
  if amp is not None and period is not None and 35.0<=period<=1000.0 and 2.0*amp>0.865:
   evidence.append({"kind":"gaia_dr3_lpv_sos","period_days":period,"fourier_semi_amplitude_g":amp,"full_model_amplitude_g":2.0*amp,"mira_boundary_g":0.865,"score_semantics":"literature selection gate; not calibrated probability"})
   return {"axis":AXIS,"label":"MIRA","confidence":score,"status":"GAIA_DR3_HIGH_AMPLITUDE_MIRA_CANDIDATE","evidence":evidence}
 if raw in GAIA_MAP:return {"axis":AXIS,"label":GAIA_MAP[raw],"confidence":score,"status":"GAIA_DR3_VARIABLE_CANDIDATE","evidence":evidence}
 if raw in EVENT_CLASSES:return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"ROUTED_TO_PHENOMENON","evidence":evidence}
 if raw in NON_STELLAR:return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NON_STELLAR_VARIABILITY_LABEL","evidence":evidence}
 if raw in OTHER_SPECIAL:return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"UNMAPPED_GAIA_VARIABILITY_CLASS","evidence":evidence}
 if raw is None:return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VARIABILITY_EVIDENCE","evidence":[]}
 return {"axis":AXIS,"label":"OTHER_VARIABLE","confidence":score,"status":"GAIA_DR3_VARIABLE_CANDIDATE","evidence":evidence}

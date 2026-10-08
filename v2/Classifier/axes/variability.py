"""Variability axis; catalog scores are raw evidence pending independent calibration.

Gaia DR3 SOS classes take priority over the broad variability classifier when
available.  The leaf is emitted as a separate ``subtype`` field so existing
family-level labels and their independent calibration remain stable.
"""
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
def _flag(row,key):
 v=_num(row,key)
 return v is not None and int(v)==1
def _clean(value):
 return "".join(ch for ch in str(value or "").upper() if ch.isalnum())
def _result(label,confidence,status,evidence,subtype=None):
 return {"axis":AXIS,"label":label,"subtype":subtype,"confidence":confidence,"status":status,"evidence":evidence}
def classify(row):
 simbad=_text(row,"otype")
 if simbad in SIMBAD_MAP:return _result(SIMBAD_MAP[simbad],None,"SIMBAD_CURATED_VARIABLE_TYPE",[{"kind":"simbad_physical_type","otype":simbad}])
 # Gaia SOS RR Lyrae classifications are based on fitted multi-band time
 # series.  Do not derive subtype from a period threshold when this published
 # subtype is unavailable.
 rr=_clean(_text(row,"gaia_rrlyrae_best_classification"))
 if rr in {"RRAB","RRC","RRD"}:
  return _result("RR_LYRAE",None,"GAIA_DR3_SOS_RRLYRAE",[{"kind":"gaia_dr3_vari_rrlyrae","best_classification":rr,"period_fundamental_days":_num(row,"gaia_rrlyrae_pf"),"period_first_overtone_days":_num(row,"gaia_rrlyrae_p1_o"),"peak_to_peak_g_mag":_num(row,"gaia_rrlyrae_peak_to_peak_g")}],rr)
 # Gaia SOS Cepheid type/mode is retained verbatim after a small documented
 # vocabulary guard.  It is evidence, not a newly calibrated probability.
 cep=_clean(_text(row,"gaia_cepheid_best_classification"))
 csub=_clean(_text(row,"gaia_cepheid_subclassification"))
 cmode=_clean(_text(row,"gaia_cepheid_mode_classification"))
 if cep in {"DCEP","ACEP","T2CEP"}:
  subtype="_".join(x for x in (cep,csub or cmode) if x) or None
  return _result("CEPHEID",None,"GAIA_DR3_SOS_CEPHEID",[{"kind":"gaia_dr3_vari_cepheid","best_classification":cep,"subclassification":csub or None,"mode_classification":cmode or None,"period_fundamental_days":_num(row,"gaia_cepheid_pf"),"period_first_overtone_days":_num(row,"gaia_cepheid_p1_o"),"peak_to_peak_g_mag":_num(row,"gaia_cepheid_peak_to_peak_g")}],subtype)
 # LPV SOS has a published C-star-candidate flag.  It does not publish a
 # validated Mira leaf, so no period/amplitude threshold is used to make one.
 if _flag(row,"gaia_lpv_is_cstar"):
  return _result("LPV",None,"GAIA_DR3_SOS_LPV_CSTAR_CANDIDATE",[{"kind":"gaia_dr3_vari_long_period_variable","is_cstar":True,"frequency_per_day":_num(row,"gaia_lpv_frequency"),"amplitude_mag":_num(row,"gaia_lpv_amplitude")}],"C_STAR_CANDIDATE")
 raw=_text(row,"best_class_name");score=_num(row,"best_class_score")
 evidence=[] if raw is None else [{"kind":"gaia_dr3_vari_classifier_result","best_class_name":raw,"best_class_score":score,"score_semantics":"raw Gaia normalized-rank score; not calibrated probability"}]
 if raw in GAIA_MAP:return _result(GAIA_MAP[raw],score,"GAIA_DR3_VARIABLE_CANDIDATE",evidence)
 if raw in EVENT_CLASSES:return _result("UNKNOWN",None,"ROUTED_TO_PHENOMENON",evidence)
 if raw in NON_STELLAR:return _result("UNKNOWN",None,"NON_STELLAR_VARIABILITY_LABEL",evidence)
 if raw in OTHER_SPECIAL:return _result("UNKNOWN",None,"UNMAPPED_GAIA_VARIABILITY_CLASS",evidence)
 if raw is None:return _result("UNKNOWN",None,"NO_VARIABILITY_EVIDENCE",[])
 return _result("OTHER_VARIABLE",score,"GAIA_DR3_VARIABLE_CANDIDATE",evidence)

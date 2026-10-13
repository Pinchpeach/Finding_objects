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
# ZTF periodic variables (Chen et al. 2020, ApJS 249, 18): types from period,
# g/r amplitude and light-curve shape (Fourier R21 / phi21); Mira and SR are
# separated by amplitude among the long-period stars.  This is the only
# catalogue here with a Mira leaf (Gaia DR3 LPV SOS has none).
ZTF_MAP={"RR":("RR_LYRAE","RRAB"),"RRC":("RR_LYRAE","RRC"),"CEP":("CEPHEID","DCEP"),"CEPII":("CEPHEID","T2CEP"),
 "MIRA":("MIRA",None),"SR":("LPV","SR"),"EW":("ECLIPSING","EW"),"EA":("ECLIPSING","EA"),
 "BYDRA":("ROTATIONAL","BY_DRA"),"RSCVN":("ROTATIONAL","RS_CVN"),"DSCT":("PULSATING","DSCT")}
ZTF="ztf_periodic_variables__"
GAIA_VARI_MIN_SCORE=0.5
GAIA_MIRA_SEMI_AMP=0.6;MIRA_MIN_PERIOD_D=80.0;MIRA_MAX_PERIOD_D=1000.0
EVENT_CLASSES={"SN","MICROLENSING"};NON_STELLAR={"AGN","GALAXY"};OTHER_SPECIAL={"EP","WD"}
def _text(row,key):
 v=row.get(key)
 if v is None:return None
 v=str(v).strip();return None if not v or v.lower()=="nan" else v
def _num(row,key):
 try:
  v=float(row.get(key));return v if math.isfinite(v) else None
 except Exception:return None
def _cstar(row):
 """Gaia LPV C-star flag gated as Lebzelter et al. (2023) advise (G_BP < 19,
 7 < median_delta_wl_rp < 11); same rule as subclass.gaia_lpv_cstar (2.17.0)."""
 if not _flag(row,"gaia_lpv_is_cstar"):return False
 bp=_num(row,"gaia_dr3__phot_bp_mean_mag");wl=_num(row,"gaia_lpv_median_delta_wl_rp")
 if bp is None:bp=_num(row,"phot_bp_mean_mag")
 return bp is not None and bp<19.0 and (wl is None or 7.0<wl<11.0)
def _flag(row,key):
 v=_num(row,key)
 return v is not None and int(v)==1
def _ratio(a,b):
 """g/r amplitude ratio: ~1.4 for pulsators (temperature change; RR Lyrae ZTF
 A_g/A_r = 1.38/0.98, Kulkarni et al. 2025, arXiv:2509.03120), ~1.0-1.1 for
 contact binaries (benchmark/evaluate_rr_ew.py).  Reported, not used as a veto:
 detached binaries with unequal components also reach > 1.2."""
 return round(a/b,3) if a is not None and b is not None and b>0 else None
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
 # ZTF periodic-variable type (after the Gaia SOS RR Lyrae / Cepheid fits,
 # which use dedicated multi-band models; before the broad Gaia classifier).
 zt=_clean(_text(row,ZTF+"Type"))
 if zt in ZTF_MAP:
  label,sub=ZTF_MAP[zt]
  if label in ("MIRA","LPV") and _cstar(row):sub="C_STAR_CANDIDATE"   # keep the Gaia RP C-star flag
  ev=[{"kind":"ztf_periodic_variable","type":_text(row,ZTF+"Type"),"period_days":_num(row,ZTF+"Per"),"amplitude_r_mag":_num(row,ZTF+"rAmp"),"amplitude_g_mag":_num(row,ZTF+"gAmp"),"amplitude_ratio_g_r":_ratio(_num(row,ZTF+"gAmp"),_num(row,ZTF+"rAmp")),"ztf_id":_text(row,ZTF+"catalog_object_id")}]
  return _result(label,None,"ZTF_PERIODIC_VARIABLE",ev,sub)
 # Mira from the Gaia DR3 LPV SOS G amplitude (2.12.0).  ``amplitude`` is half
 # the peak-to-peak range of the fitted G model (Lebzelter et al. 2023); Miras
 # are the large-amplitude LPVs (GCVS: dV > 2.5 mag; Mira-like in Gaia DR2:
 # G range > ~1 mag, Mowlavi et al. 2018).  Semi-amplitude >= 0.6 mag (range
 # >= 1.2 mag), with the GCVS Mira period range (>= 80 d) when a period is
 # published.  ASAS-SN M vs SR (benchmark/build_mira_truth.py), threshold
 # chosen on one half, other half: precision 0.934, recall 0.968.
 amp=_num(row,"gaia_lpv_amplitude");freq=_num(row,"gaia_lpv_frequency")
 # 2.17.0: a published period in 80-1000 d is required, as in the Gaia DR3
 # Mira selection of Zhang & Sanders (2023: 80 < P < 1000 d, semi-amplitude
 # >= 0.5); every ASAS-SN M/SR star in the truth set has one.  Their alias
 # windows (170-200 d, 350-400 d) are not excluded: they flag unreliable
 # periods, and excluding them removed 30 Miras for 6 SRs here.
 if amp is not None and amp>=GAIA_MIRA_SEMI_AMP and freq is not None and freq>0 and MIRA_MIN_PERIOD_D<=1/freq<MIRA_MAX_PERIOD_D:
  sub="C_STAR_CANDIDATE" if _cstar(row) else None
  return _result("MIRA",None,"GAIA_DR3_SOS_LPV_LARGE_AMPLITUDE",[{"kind":"gaia_dr3_vari_long_period_variable","semi_amplitude_g_mag":amp,"period_days":round(1/freq,1) if freq else None,"is_cstar":_cstar(row)}],sub)
 # LPV SOS has a published C-star-candidate flag.  It does not publish a
 # validated Mira leaf, so no period/amplitude threshold is used to make one.
 if _cstar(row):
  return _result("LPV",None,"GAIA_DR3_SOS_LPV_CSTAR_CANDIDATE",[{"kind":"gaia_dr3_vari_long_period_variable","is_cstar":True,"frequency_per_day":_num(row,"gaia_lpv_frequency"),"amplitude_mag":_num(row,"gaia_lpv_amplitude")}],"C_STAR_CANDIDATE")
 raw=_text(row,"best_class_name");score=_num(row,"best_class_score")
 evidence=[] if raw is None else [{"kind":"gaia_dr3_vari_classifier_result","best_class_name":raw,"best_class_score":score,"score_semantics":"raw Gaia normalized-rank score; not calibrated probability"}]
 # Gaia vari_classifier scores are not calibrated across classes (Rimoldini
 # et al. 2023).  On the cross-validation set (192 objects) the type is
 # right for 35 % below score 0.5 and 91 % at >= 0.5, so below it only
 # "variable" is reported (2.18.0).
 if raw in GAIA_MAP and score is not None and score<GAIA_VARI_MIN_SCORE:
  return _result("OTHER_VARIABLE",score,"GAIA_DR3_VARIABLE_LOW_SCORE",evidence)
 if raw in GAIA_MAP:return _result(GAIA_MAP[raw],score,"GAIA_DR3_VARIABLE_CANDIDATE",evidence)
 if raw in EVENT_CLASSES:return _result("UNKNOWN",None,"ROUTED_TO_PHENOMENON",evidence)
 if raw in NON_STELLAR:return _result("UNKNOWN",None,"NON_STELLAR_VARIABILITY_LABEL",evidence)
 if raw in OTHER_SPECIAL:return _result("UNKNOWN",None,"UNMAPPED_GAIA_VARIABILITY_CLASS",evidence)
 if raw is None:return _result("UNKNOWN",None,"NO_VARIABILITY_EVIDENCE",[])
 return _result("OTHER_VARIABLE",score,"GAIA_DR3_VARIABLE_CANDIDATE",evidence)

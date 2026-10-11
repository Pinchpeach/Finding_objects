"""Compact-object axis with conservative catalog evidence."""
from __future__ import annotations
import math
AXIS="compact";CLASSES=("NS","PULSAR","PULSAR_CANDIDATE","XRB","COMPACT_COMPANION_CANDIDATE","OTHER_COMPACT","UNKNOWN")
# Radio pulsar candidate without the ATNF catalogue (2.6.3).  Pulsars have
# steep spectra (alpha ~ -1.6; Jankowski et al. 2018, Bates et al. 2013), are
# compact, and are strongly linearly polarised.  Selection: TGSS 150 MHz -
# NVSS 1.4 GHz alpha <= -1.5 with TGSS S_total / S_peak <= 1.5 (Frail et al.
# 2018) and NVSS fractional polarisation > 5 % (Han & Tian 1999).  Measured
# on NVSS-detected ATNF pulsars vs random NVSS sources (around the NVSS
# position; benchmark/build_pulsar_truth.py): 48/152 pulsars (32 %), 3/2532
# ordinary sources (0.12 %), and those three are steep, compact and polarised
# themselves.  Median alpha -1.67 vs -0.73, median polarisation 25 % vs 2.4 %.
PSR_ALPHA_MAX=-1.5;PSR_COMPACT_MAX=1.5;PSR_POL_MIN=0.05
def radio_pulsar_evidence(row):
 s14=_num(row,"nvss__S1.4");s150=_num(row,"tgss_adr1__Stotal");peak=_num(row,"tgss_adr1__Speak");pol=_num(row,"nvss__polFlux")
 if None in (s14,s150,peak,pol) or s14<=0 or s150<=0 or peak<=0:return None
 alpha=math.log10(s150/s14)/math.log10(150/1400);compact=s150/peak;fpol=pol/s14
 if alpha<=PSR_ALPHA_MAX and compact<=PSR_COMPACT_MAX and fpol>PSR_POL_MIN:
  return {"kind":"radio_steep_compact_polarised","alpha_150_1400":round(alpha,3),"compactness_150":round(compact,3),"nvss_fractional_pol":round(fpol,3)}
 return None
def _bool(row,key):
 v=row.get(key)
 if v is None:return False
 if isinstance(v,bool):return v
 return str(v).strip().lower() in {"1","1.0","true","t","yes"}
def _text(row,key):
 v=row.get(key)
 if v is None:return None
 v=str(v).strip();return None if not v or v.lower()=="nan" else v
def _num(row,key):
 try:
  v=float(row.get(key));return v if math.isfinite(v) else None
 except Exception:return None
def classify(row):
 catalogs=_text(row,"catalogs") or ""
 if "ATNF Pulsar Catalog" in catalogs:
  assoc=_num(row,"association_confidence__atnf_pulsar_catalog")
  return {"axis":AXIS,"label":"PULSAR","confidence":assoc,"status":"ATNF_CATALOG_MATCH","evidence":[{"kind":"atnf_pulsar_catalog_counterpart","association_confidence":assoc,"score_semantics":"raw association score; not calibrated posterior"}]}
 simbad=_text(row,"otype")
 if simbad=="N*":return {"axis":AXIS,"label":"NS","confidence":None,"status":"SIMBAD_CURATED_NS","evidence":[{"kind":"simbad_physical_type","otype":"N*"}]}
 if simbad=="Psr":return {"axis":AXIS,"label":"PULSAR","confidence":None,"status":"SIMBAD_CURATED_PULSAR","evidence":[{"kind":"simbad_physical_type","otype":"Psr"}]}
 if simbad in {"XB*","LXB","HXB"}:return {"axis":AXIS,"label":"XRB","confidence":None,"status":"SIMBAD_CURATED_XRB","evidence":[{"kind":"simbad_physical_type","otype":simbad}]}
 psr=radio_pulsar_evidence(row)
 if psr is not None:return {"axis":AXIS,"label":"PULSAR_CANDIDATE","confidence":None,"status":"RADIO_STEEP_COMPACT_POLARISED","evidence":[psr]}
 if _bool(row,"in_vari_compact_companion"):return {"axis":AXIS,"label":"COMPACT_COMPANION_CANDIDATE","confidence":None,"status":"GAIA_DR3_COMPACT_COMPANION_CANDIDATE","evidence":[{"kind":"gaia_dr3_vari_summary","in_vari_compact_companion":True}]}
 return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VALIDATED_COMPACT_EVIDENCE","evidence":[]}

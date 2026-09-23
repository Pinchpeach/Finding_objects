#!/usr/bin/env python3
"""Stage 4: rule-table-driven feature -> evidence conversion.

classification_rules.csv is the source of truth. A rule is evaluated only when
its required feature columns are present and usable. Missing values are neutral.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd

PRIMARY=("STAR","WD","GALAXY","QSO","BINARY")
DSC_MAP={
 "QSO":"classprob_dsc_combmod_quasar","GALAXY":"classprob_dsc_combmod_galaxy",
 "STAR":"classprob_dsc_combmod_star","WD":"classprob_dsc_combmod_whitedwarf",
 "BINARY":"classprob_dsc_combmod_binarystar",
}

def num(row,name):
    try:
        v=float(row.get(name))
        return v if math.isfinite(v) else None
    except (TypeError,ValueError): return None

def emit(out, rule, cls, score, value=None, note="", reliability=1.0):
    raw=float(max(0,min(1,score)))
    rel=float(max(0,min(1,reliability))) if reliability is not None else 0.0
    out.append({"class":cls,"rule_id":rule["rule_id"],"score":raw*rel,
      "raw_score":raw,"reliability":rel,"kind":rule["likelihood_method"],
      "origin":rule["threshold_origin"],"feature_group":rule["feature_group"],
      "value":value,"note":note})

def evaluate(rule,row):
    rid=rule["rule_id"]; out=[]
    relmap={
      "AST-EXT-001":"catalog_confidence_gaia_astrometry","AST-EXT-002":"catalog_confidence_gaia_astrometry",
      "AST-GAL-001":"catalog_confidence_gaia_astrometry","AST-GAL-002":"catalog_confidence_gaia_astrometry",
      "SPC-SDSS-001":"catalog_confidence_sdss_spectroscopy","SPC-SDSS-002":"catalog_confidence_sdss_spectroscopy",
      "SPC-SDSS-003":"catalog_confidence_sdss_spectroscopy","DSC-001":"catalog_confidence_gaia_dsc",
      "PS1-MORPH-001":"catalog_confidence_ps1_morphology","PS1-MORPH-002":"catalog_confidence_ps1_morphology",
      "WISE-AGN-001":"catalog_confidence_allwise","SDSS-PHOTO-001":"catalog_confidence_sdss_photometry",
      "SDSS-PHOTO-002":"catalog_confidence_sdss_photometry","NED-TYPE-001":"catalog_confidence_ned_type",
      "SIMBAD-TYPE-001":"catalog_confidence_simbad_type",
    }
    rcol=relmap.get(rid); reliability=num(row,rcol) if rcol else 1.0
    if rcol and reliability is None: reliability=0.0
    if rid=="AST-EXT-001":
        p,e=num(row,"parallax"),num(row,"parallax_error")
        if p is not None and e and e>0:
            x=abs((p+0.017)/e)
            if x<float(rule["threshold"]): emit(out,rule,"EXTRAGALACTIC",1-x/float(rule["threshold"]),x,reliability=reliability)
    elif rid=="AST-EXT-002":
        a,ae,d,de=(num(row,x) for x in ("pmra","pmra_error","pmdec","pmdec_error"))
        if None not in (a,ae,d,de) and ae>0 and de>0:
            x=math.sqrt((a/ae)**2+(d/de)**2)
            if x<float(rule["threshold"]): emit(out,rule,"EXTRAGALACTIC",1-x/float(rule["threshold"]),x,
              "diagonal-error approximation; covariance unavailable",reliability)
    elif rid=="AST-GAL-001":
        p,e=num(row,"parallax"),num(row,"parallax_error")
        if p is not None and e and e>0:
            x=abs(p/e); emit(out,rule,"STAR",x/(x+5),x,"uncalibrated physical support",reliability)
    elif rid=="AST-GAL-002":
        a,ae,d,de=(num(row,x) for x in ("pmra","pmra_error","pmdec","pmdec_error"))
        if None not in (a,ae,d,de) and ae>0 and de>0:
            x=math.sqrt((a/ae)**2+(d/de)**2); emit(out,rule,"STAR",x/(x+5),x,"uncalibrated physical support")
    elif rid.startswith("SPC-SDSS-"):
        c=str(row.get("class","")).strip().upper()
        target=rule["target_class"]
        hit=(target=="QSO" and c in {"QSO","QUASAR"}) or c==target
        if hit:
            zw=num(row,"zwarning"); score=1.0 if zw in (None,0) else 0.75
            emit(out,rule,target,score,c,"nonzero zwarning downweights spectral label" if zw not in (None,0) else "",reliability)
    elif rid.startswith("PS1-MORPH-"):
        delta=num(row,"ps1_i_psf_minus_kron"); imag=num(row,"iMeanPSFMag")
        valid=num(row,"ps1_i_photometry_valid")
        if None not in (delta,imag,valid) and valid==1 and 14<=imag<=21:
            if rid=="PS1-MORPH-001" and delta>0.05:
                # Extended morphology is direct GALAXY support within the documented regime.
                score=min(0.9,0.55+min(delta-0.05,0.35))
                emit(out,rule,"GALAXY",score,delta,"PS1 i-band PSF-Kron extended-source evidence",reliability)
            elif rid=="PS1-MORPH-002" and delta<=0.05:
                # Point-like morphology is deliberately weak STAR evidence: QSOs are unresolved too.
                score=min(0.65,0.50+min(max(0,0.05-delta),0.15))
                emit(out,rule,"STAR",score,delta,"weak point-source evidence; unresolved morphology is not STAR-specific",reliability)
    elif rid=="WISE-AGN-001":
        w1,w2,s1,s2=(num(row,x) for x in ("W1mag","W2mag","snr1","snr2"))
        if None not in (w1,w2,s1,s2) and w1-w2>=0.8 and w2<=15.05 and s1>=10 and s2>=10:
            emit(out,rule,"EXTRAGALACTIC",0.95,w1-w2,
                 "Stern+2012 AGN selection; 0.95 is reported sample reliability, not per-source posterior",reliability)
    elif rid.startswith("SDSS-PHOTO-"):
        typ=num(row,"type"); clean=num(row,"clean")
        if clean==1 and typ is not None:
            if rid=="SDSS-PHOTO-001" and int(typ)==3:
                emit(out,rule,"GALAXY",0.8,typ,"SDSS extended morphology",reliability)
            elif rid=="SDSS-PHOTO-002" and int(typ)==6:
                emit(out,rule,"STAR",0.55,typ,"weak point-source morphology; QSO contamination possible",reliability)
    elif rid=="NED-TYPE-001":
        typ=str(row.get("Type","")).strip()
        mp={"G":"GALAXY","QSO":"QSO","*":"STAR","WD*":"WD"}
        if typ in mp: emit(out,rule,mp[typ],0.85,typ,"curated NED preferred physical type",reliability)
    elif rid=="SIMBAD-TYPE-001":
        typ=str(row.get("otype","")).strip()
        mp={"G":"GALAXY","GiG":"GALAXY","QSO":"QSO","AGN":"EXTRAGALACTIC","Star":"STAR","*":"STAR","WD*":"WD"}
        if typ in mp: emit(out,rule,mp[typ],0.85,typ,"curated SIMBAD hierarchical physical type",reliability)
    elif rid=="DSC-001":
        for cls,col in DSC_MAP.items():
            v=num(row,col)
            if v is not None: emit(out,rule,cls,v,v,reliability=reliability)
    elif rid=="VAR-001":
        cls=str(row.get("best_class_name","")).strip()
        score=num(row,"best_class_score")
        if cls and score is not None: emit(out,rule,f"VAR:{cls}",score,score)
    return out

def run(features:Path,rules_path:Path,out:Path)->Path:
    df=pd.read_csv(features); rules=pd.read_csv(rules_path,keep_default_na=False)
    result=df.copy(); payload=[]; counts=[]; conflicts=[]
    for _,row in df.iterrows():
        ev=[]
        for _,rule in rules.iterrows(): ev.extend(evaluate(rule,row))
        payload.append(json.dumps(ev,separators=(",",":")))
        counts.append(len(ev))
        strong={e["class"] for e in ev if e["class"] in PRIMARY and e["score"]>=.8}
        conflicts.append(int(len(strong)>1))
    result["evidence_json"]=payload; result["evidence_count"]=counts; result["evidence_conflict"]=conflicts
    out.parent.mkdir(parents=True,exist_ok=True); result.to_csv(out,index=False)
    print(f"[OK] rules={len(rules)} objects={len(result)} -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--features",type=Path,default=root/"features.csv")
    p.add_argument("--rules",type=Path,default=root/"classification_rules.csv")
    p.add_argument("--out",type=Path,default=root/"evidence.csv")
    a=p.parse_args(); run(a.features,a.rules,a.out)
if __name__=="__main__": main()

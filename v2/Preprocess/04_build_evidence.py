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

def emit(out, rule, cls, score, value=None, note="", reliability=1.0, association_reliability=1.0):
    raw=float(max(0,min(1,score)))
    rel=float(max(0,min(1,reliability,association_reliability))) if reliability is not None else 0.0
    arel=float(max(0,min(1,association_reliability))) if association_reliability is not None else 0.0
    effective=raw*rel*arel
    if effective<=0: return
    out.append({"class":cls,"rule_id":rule["rule_id"],"score":effective,
      "raw_score":raw,"reliability":rel,"association_reliability":arel,"kind":rule["likelihood_method"],
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
      "WISE-AGN-R90-001":"catalog_confidence_allwise",
    }
    rcol=relmap.get(rid); reliability=num(row,rcol) if rcol else 1.0
    # Gate only by the association confidence of the catalog that produced
    # this evidence. A weak PS1/NED counterpart must not downweight Gaia/SDSS.
    assoc_prefix={
      "AST-EXT-001":"gaia_dr3","AST-EXT-002":"gaia_dr3","AST-GAL-001":"gaia_dr3","AST-GAL-002":"gaia_dr3",
      "DSC-001":"gaia_dr3","VAR-001":"gaia_dr3",
      "SPC-SDSS-001":"sdss_dr18_spectroscopy","SPC-SDSS-002":"sdss_dr18_spectroscopy","SPC-SDSS-003":"sdss_dr18_spectroscopy",
      "PS1-MORPH-001":"pan_starrs1_dr2_meanobject","PS1-MORPH-002":"pan_starrs1_dr2_meanobject","PS1-QSO-Z6-001":"pan_starrs1_dr2_meanobject",
      "WISE-AGN-001":"allwise","WISE-AGN-R90-001":"allwise",
      "SDSS-PHOTO-001":"sdss_dr18_photoobj","SDSS-PHOTO-002":"sdss_dr18_photoobj",
      "NED-TYPE-001":"ned","SIMBAD-TYPE-001":"simbad",
    }
    ap=assoc_prefix.get(rid)
    association_reliability=num(row,f"association_confidence__{ap}") if ap else 1.0
    if association_reliability is None: association_reliability=1.0
    if rcol and reliability is None: reliability=0.0
    if rid=="AST-EXT-001":
        p,e=num(row,"parallax"),num(row,"parallax_error")
        if p is not None and e and e>0:
            x=abs((p+0.017)/e)
            if x<float(rule["threshold"]): emit(out,rule,"EXTRAGALACTIC",1-x/float(rule["threshold"]),x,reliability=reliability,association_reliability=association_reliability)
    elif rid=="AST-EXT-002":
        a,ae,d,de=(num(row,x) for x in ("pmra","pmra_error","pmdec","pmdec_error"))
        if None not in (a,ae,d,de) and ae>0 and de>0:
            x=math.sqrt((a/ae)**2+(d/de)**2)
            if x<float(rule["threshold"]): emit(out,rule,"EXTRAGALACTIC",1-x/float(rule["threshold"]),x,
              "diagonal-error approximation; covariance unavailable",reliability,association_reliability)
    elif rid=="AST-GAL-001":
        p,e=num(row,"parallax"),num(row,"parallax_error")
        if p is not None and e and e>0:
            x=abs(p/e); emit(out,rule,"STAR",x/(x+5),x,"uncalibrated physical support",reliability,association_reliability)
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
            emit(out,rule,target,score,c,"nonzero zwarning downweights spectral label" if zw not in (None,0) else "",reliability,association_reliability)
    elif rid.startswith("PS1-MORPH-"):
        delta=num(row,"ps1_i_psf_minus_kron"); imag=num(row,"iMeanPSFMag")
        valid=num(row,"ps1_i_photometry_valid")
        if None not in (delta,imag,valid) and valid==1 and 14<=imag<=21:
            if rid=="PS1-MORPH-001" and delta>0.05:
                # Extended morphology is direct GALAXY support within the documented regime.
                score=min(0.9,0.55+min(delta-0.05,0.35))
                emit(out,rule,"GALAXY",score,delta,"PS1 i-band PSF-Kron extended-source evidence",reliability,association_reliability)
            elif rid=="PS1-MORPH-002" and delta<=0.05:
                # Point-like morphology is deliberately weak STAR evidence: QSOs are unresolved too.
                score=min(0.65,0.50+min(max(0,0.05-delta),0.15))
                emit(out,rule,"STAR",score,delta,"weak point-source evidence; unresolved morphology is not STAR-specific",reliability,association_reliability)
    elif rid=="WISE-AGN-R90-001":
        w1,w2,s1,s2=(num(row,x) for x in ("W1mag","W2mag","snr1","snr2"))
        if None not in (w1,w2,s1,s2) and s1>=3 and s2>=3:
            cut=0.650 if w2<=13.86 else 0.650*math.exp(0.153*(w2-13.86)**2)
            color=w1-w2
            if color>cut:
                emit(out,rule,"EXTRAGALACTIC",0.90,color,
                     f"Assef+2018 AllWISE R90 AGN color selection; boundary={cut:.3f}",reliability,association_reliability)
    elif rid=="PS1-QSO-Z6-001":
        iz=num(row,"ps1_i_z_color"); zy=num(row,"ps1_z_y_color")
        ei=num(row,"ps1_i_psf_mag_err"); eg=num(row,"ps1_g_psf_mag_err")
        er=num(row,"ps1_r_psf_mag_err"); ez=num(row,"ps1_z_psf_mag_err"); ey=num(row,"ps1_y_psf_mag_err")
        vz=num(row,"ps1_z_photometry_valid"); vy=num(row,"ps1_y_photometry_valid")
        # S/N from magnitude uncertainty: sigma_mag ~= 1.0857/SNR.
        sn=lambda e: (1.0857/e if e is not None and e>0 else None)
        sg,sr,sz,sy=sn(eg),sn(er),sn(ez),sn(ey)
        rz=None
        r=num(row,"rMeanPSFMag"); z=num(row,"zMeanPSFMag")
        if r is not None and z is not None and 0<r<40 and 0<z<40: rz=r-z
        if None not in (iz,zy,sz,sy,vz,vy) and vz==1 and vy==1 and iz>2.0:
            gdrop=(sg is None or sg<3)
            if zy<0.5:
                rcond=(sr is None or sr<3 or (rz is not None and rz>2.2))
                hit=gdrop and sz>10 and sy>5 and rcond
            else:
                hit=gdrop and sz>7 and sy>7 and (sr is None or sr<3)
            if hit:
                # Candidate-selection evidence only. Keep moderate because the
                # paper explicitly requires follow-up to reject cool dwarfs/artifacts.
                emit(out,rule,"QSO",0.70,{"i-z":iz,"z-y":zy},
                     "Bañados+2016 PS1 z~6 quasar color-selection candidate; follow-up required")
    elif rid=="WISE-AGN-001":
        w1,w2,s1,s2=(num(row,x) for x in ("W1mag","W2mag","snr1","snr2"))
        if None not in (w1,w2,s1,s2) and w1-w2>=0.8 and w2<=15.05 and s1>=10 and s2>=10:
            emit(out,rule,"EXTRAGALACTIC",0.95,w1-w2,
                 "Stern+2012 AGN selection; 0.95 is reported sample reliability, not per-source posterior",reliability,association_reliability)
    elif rid.startswith("SDSS-PHOTO-"):
        typ=num(row,"type"); clean=num(row,"clean")
        if clean==1 and typ is not None:
            if rid=="SDSS-PHOTO-001" and int(typ)==3:
                emit(out,rule,"GALAXY",0.8,typ,"SDSS extended morphology",reliability,association_reliability)
            elif rid=="SDSS-PHOTO-002" and int(typ)==6:
                emit(out,rule,"STAR",0.55,typ,"weak point-source morphology; QSO contamination possible",reliability,association_reliability)
    elif rid=="NED-TYPE-001":
        typ=str(row.get("Type","")).strip()
        mp={"G":"GALAXY","QSO":"QSO","*":"STAR","WD*":"WD"}
        if typ in mp: emit(out,rule,mp[typ],0.85,typ,"curated NED preferred physical type",reliability,association_reliability)
    elif rid=="SIMBAD-TYPE-001":
        typ=str(row.get("otype","")).strip()
        mp={"G":"GALAXY","GiG":"GALAXY","QSO":"QSO","AGN":"EXTRAGALACTIC","Star":"STAR","*":"STAR","WD*":"WD"}
        if typ in mp: emit(out,rule,mp[typ],0.85,typ,"curated SIMBAD hierarchical physical type",reliability,association_reliability)
    elif rid=="DSC-001":
        for cls,col in DSC_MAP.items():
            v=num(row,col)
            if v is not None: emit(out,rule,cls,v,v,reliability=reliability,association_reliability=association_reliability)
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

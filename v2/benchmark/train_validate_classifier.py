#!/usr/bin/env python3
"""Train and evaluate the next-generation STAR/GALAXY/QSO benchmark classifier.

The spectroscopic truth label is never used as an input feature.  The model
uses continuous multi-survey measurements plus explicit catalog-presence and
missing-value indicators.  HistGradientBoosting handles NaNs natively; a
held-out calibration split is used for sigmoid probability calibration.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
    classification_report, confusion_matrix, f1_score, log_loss)

CLASSES=["STAR","GALAXY","QSO"]
SAFE={
 "gaia_dr3":["parallax","parallax_error","pmra","pmra_error","pmdec","pmdec_error","ruwe",
   "phot_g_mean_mag","phot_bp_mean_mag","phot_rp_mean_mag","bp_rp","bp_g","g_rp",
   "classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star"],
 "panstarrs1":["gMeanPSFMag","gMeanPSFMagErr","rMeanPSFMag","rMeanPSFMagErr","iMeanPSFMag","iMeanPSFMagErr",
   "zMeanPSFMag","zMeanPSFMagErr","yMeanPSFMag","yMeanPSFMagErr","gMeanKronMag","rMeanKronMag",
   "iMeanKronMag","zMeanKronMag","yMeanKronMag","nDetections","ng","nr","ni","nz","ny"],
 "allwise":["W1mag","e_W1mag","W2mag","e_W2mag","W3mag","e_W3mag","W4mag","e_W4mag",
   "snr1","snr2","snr3","snr4","nb"],
 "twomass":["Jmag","e_Jmag","Jsnr","Hmag","e_Hmag","Hsnr","Kmag","e_Kmag","Ksnr"],
 "galex":["FUVmag","e_FUVmag","NUVmag","e_NUVmag","FUVexp","NUVexp"],
 "desi_legacy":["flux_g","flux_r","flux_i","flux_z","flux_ivar_g","flux_ivar_r","flux_ivar_i","flux_ivar_z",
   "mw_transmission_g","mw_transmission_r","mw_transmission_i","mw_transmission_z","nobs_g","nobs_r","nobs_i","nobs_z"],
}
PRESENCE=["gaia_dr3","panstarrs1","allwise","twomass","galex","desi_legacy",
          "first","nvss","lotss","vlass","chandra","xmm","erosita"]

def read_catalogs(root:Path):
    found={}
    for f in root.rglob("*_trd.csv"):
        cat=f.stem[:-4] if f.stem.endswith("_trd") else f.stem
        d=pd.read_csv(f)
        if cat not in found or len(d)>len(found[cat]):
            found[cat]=d
    return found

def add_derived(x:pd.DataFrame):
    def col(n): return pd.to_numeric(x[n],errors="coerce") if n in x else None
    def diff(out,a,b):
        if a in x and b in x: x[out]=col(a)-col(b)
    for a,b in [("ps1_g","ps1_r"),("ps1_r","ps1_i"),("ps1_i","ps1_z"),("ps1_z","ps1_y")]:
        diff(a+"_"+b+"_color",a+"MeanPSFMag",b+"MeanPSFMag")
    if "ps1_iMeanPSFMag" in x and "ps1_iMeanKronMag" in x:
        x["ps1_i_psf_minus_kron"]=col("ps1_iMeanPSFMag")-col("ps1_iMeanKronMag")
    diff("wise_w1_w2","wise_W1mag","wise_W2mag"); diff("wise_w2_w3","wise_W2mag","wise_W3mag")
    diff("tmass_j_h","tmass_Jmag","tmass_Hmag"); diff("tmass_h_k","tmass_Hmag","tmass_Kmag")
    diff("galex_fuv_nuv","galex_FUVmag","galex_NUVmag")
    if all(k in x for k in ("gaia_parallax","gaia_parallax_error")):
        x["gaia_parallax_snr"]=col("gaia_parallax").abs()/col("gaia_parallax_error").replace(0,np.nan)
    if all(k in x for k in ("gaia_pmra","gaia_pmra_error","gaia_pmdec","gaia_pmdec_error")):
        x["gaia_pm_significance"]=np.sqrt((col("gaia_pmra")/col("gaia_pmra_error").replace(0,np.nan))**2+
                                           (col("gaia_pmdec")/col("gaia_pmdec_error").replace(0,np.nan))**2)
    for b in "griz":
        f=f"desi_flux_{b}"
        t=f"desi_mw_transmission_{b}"
        if f in x:
            flux=col(f)
            if t in x: flux=flux/col(t).where(col(t)>0)
            x[f"desi_mag_{b}"]=22.5-2.5*np.log10(flux.where(flux>0))
    for a,b in [("g","r"),("r","i"),("i","z")]:
        diff(f"desi_{a}_{b}_color",f"desi_mag_{a}",f"desi_mag_{b}")
    return x

def build_matrix(truth:pd.DataFrame,cats:dict[str,pd.DataFrame]):
    x=pd.DataFrame({"benchmark_id":truth.benchmark_id.astype(str)})
    prefixes={"gaia_dr3":"gaia_","panstarrs1":"ps1_","allwise":"wise_","twomass":"tmass_",
              "galex":"galex_","desi_legacy":"desi_"}
    for cat in PRESENCE:
        d=cats.get(cat)
        present=set(d.benchmark_id.astype(str)) if d is not None and len(d) else set()
        x[f"has_{cat}"]=x.benchmark_id.isin(present).astype(float)
    for cat,cols in SAFE.items():
        d=cats.get(cat)
        if d is None or not len(d): continue
        keep=["benchmark_id"]+[c for c in cols if c in d.columns]
        q=d[keep].drop_duplicates("benchmark_id").copy()
        rename={c:prefixes[cat]+c for c in keep if c!="benchmark_id"}
        q=q.rename(columns=rename)
        x=x.merge(q,on="benchmark_id",how="left")
    x=add_derived(x)
    for c in x.columns:
        if c!="benchmark_id": x[c]=pd.to_numeric(x[c],errors="coerce")
    # Missingness is often survey-selection information; expose it explicitly,
    # while leaving NaNs for the tree model's native missing-value routing.
    base=[c for c in x.columns if c!="benchmark_id"]
    miss={f"missing__{c}":x[c].isna().astype(float) for c in base if x[c].isna().any()}
    if miss: x=pd.concat([x,pd.DataFrame(miss,index=x.index)],axis=1)
    return x

def multiclass_brier(y,proba,classes):
    one=np.zeros_like(proba,float)
    mp={c:i for i,c in enumerate(classes)}
    for r,v in enumerate(y): one[r,mp[v]]=1.0
    return float(np.mean(np.sum((proba-one)**2,axis=1)))

def ece(y,proba,classes,bins=10):
    pred=np.argmax(proba,axis=1); conf=np.max(proba,axis=1)
    truth=np.array([classes.index(v) for v in y]); ok=(pred==truth)
    edges=np.linspace(0,1,bins+1); val=0.0
    for lo,hi in zip(edges[:-1],edges[1:]):
        m=(conf>=lo)&(conf<(hi if hi<1 else hi+1e-12))
        if m.any(): val+=m.mean()*abs(float(ok[m].mean())-float(conf[m].mean()))
    return float(val)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--truth",type=Path,required=True); p.add_argument("--catalog-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    truth=pd.read_csv(a.truth); manifest=pd.read_csv(a.manifest)
    cats=read_catalogs(a.catalog_root); x=build_matrix(truth,cats)
    data=truth[["benchmark_id","truth_class"]+([c for c in ["truth_selection","truth_radio_catalog"] if c in truth.columns])].merge(
        manifest[["benchmark_id","split"]],on="benchmark_id").merge(x,on="benchmark_id")
    feats=[c for c in x.columns if c!="benchmark_id"]
    tr=data.split.eq("train"); ca=data.split.eq("calibration"); te=data.split.eq("test")
    base=HistGradientBoostingClassifier(loss="log_loss",learning_rate=0.05,max_iter=300,max_leaf_nodes=15,
        min_samples_leaf=15,l2_regularization=1.0,random_state=42)
    base.fit(data.loc[tr,feats],data.loc[tr,"truth_class"])
    if FrozenEstimator is not None:
        calibrated=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        calibrated=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    calibrated.fit(data.loc[ca,feats],data.loc[ca,"truth_class"])
    y=data.loc[te,"truth_class"].to_numpy(); ptest=calibrated.predict_proba(data.loc[te,feats])
    classes=list(calibrated.classes_); pred=np.array(classes)[np.argmax(ptest,axis=1)]
    metrics={"test_rows":int(te.sum()),"features":len(feats),"accuracy":float(accuracy_score(y,pred)),
      "balanced_accuracy":float(balanced_accuracy_score(y,pred)),"macro_f1":float(f1_score(y,pred,average="macro")),
      "log_loss":float(log_loss(y,ptest,labels=classes)),"multiclass_brier":multiclass_brier(y,ptest,classes),
      "confidence_ece_10bin":ece(y,ptest,classes)}
    if "truth_selection" in data:
        sel=data.loc[te,"truth_selection"].fillna("GENERAL").to_numpy()
        for grp in sorted(set(sel)):
            m=sel==grp
            if m.any():
                metrics[f"accuracy_{grp.lower()}"]=float(accuracy_score(y[m],pred[m]))
                metrics[f"n_{grp.lower()}"]=int(m.sum())
    report=classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0)
    cm=confusion_matrix(y,pred,labels=CLASSES)
    pd.DataFrame(cm,index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"confusion_matrix.csv")
    pd.DataFrame(report).T.to_csv(a.out/"classification_report.csv")
    predout=data.loc[te,["benchmark_id","truth_class"]+([c for c in ["truth_selection"] if c in data.columns])].copy()
    predout["predicted_class"]=pred
    for i,c in enumerate(classes): predout[f"p_{c.lower()}"]=ptest[:,i]
    predout.to_csv(a.out/"test_predictions.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    (a.out/"feature_columns.json").write_text(json.dumps(feats,indent=2)+"\n")
    joblib.dump({"model":calibrated,"features":feats,"classes":classes},a.out/"classifier.joblib")
    print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()

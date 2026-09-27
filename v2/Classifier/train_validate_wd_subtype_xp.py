#!/usr/bin/env python3
"""Validate DA vs DB classification with Gaia DR3 XP continuous coefficients.

The primary model follows García-Zamora et al. (2023): Random Forest on the
110 BP/RP Hermite coefficients. A Gaia-broadband HGB model is re-evaluated on
the exact same XP-available rows for a fair comparison.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_score, recall_score
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None

ROOT=Path(__file__).resolve().parent
CLASSES=["DA","DB"]

def load_core():
    p=ROOT/"train_validate_star_wd.py"
    s=importlib.util.spec_from_file_location("starwd_core",p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def split_for(bid):
    x=int(hashlib.sha256(("wd-subtype:"+str(bid)).encode()).hexdigest()[:8],16)%10
    return "train" if x<6 else ("calibration" if x<8 else "test")

def metrics(y,pred,p=None,classes=None):
    out={
      "accuracy":float(accuracy_score(y,pred)),
      "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
      "macro_f1":float(f1_score(y,pred,average="macro")),
      "db_precision":float(precision_score(y,pred,pos_label="DB",zero_division=0)),
      "db_recall":float(recall_score(y,pred,pos_label="DB",zero_division=0)),
      "db_f1":float(f1_score(y,pred,pos_label="DB",zero_division=0)),
    }
    if p is not None and classes is not None:
        out["log_loss"]=float(log_loss(y,p,labels=classes))
    return out

def calibrated(base,xtrain,ytrain,xcal,ycal):
    base.fit(xtrain,ytrain)
    if FrozenEstimator is not None:
        m=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        m=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    m.fit(xcal,ycal)
    return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    raw=pd.read_csv(a.features)
    if set(raw.star_truth_class)!={"DA","DB"}:
        raise ValueError(f"expected DA/DB truth, got {sorted(set(raw.star_truth_class))}")
    xp=[c for c in raw.columns if c.startswith("xp_bp_") or c.startswith("xp_rp_")]
    xp=[c for c in xp if c[-2:].isdigit()]
    if len(xp)!=110:
        raise ValueError(f"expected 110 XP coefficients, found {len(xp)}")

    data=raw.copy()
    data["split"]=data.benchmark_id.map(split_for)
    tr=data.split.eq("train"); ca=data.split.eq("calibration"); te=data.split.eq("test")
    ytr=data.loc[tr,"star_truth_class"]; yca=data.loc[ca,"star_truth_class"]; y=data.loc[te,"star_truth_class"].to_numpy()
    if min(ytr.value_counts().reindex(CLASSES,fill_value=0))<20 or min(yca.value_counts().reindex(CLASSES,fill_value=0))<8 or min(pd.Series(y).value_counts().reindex(CLASSES,fill_value=0))<8:
        raise RuntimeError("XP subset too small or imbalanced for train/calibration/test")

    # Literature-inspired model: all 110 raw Hermite coefficients.
    rf=RandomForestClassifier(
        n_estimators=1000,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf_model=calibrated(rf,data.loc[tr,xp],ytr,data.loc[ca,xp],yca)
    rp=rf_model.predict_proba(data.loc[te,xp]); rc=list(rf_model.classes_)
    rpred=np.array(rc)[np.argmax(rp,axis=1)]

    # Broadband comparison on identical XP-available objects and split.
    core=load_core()
    broad=core.prepare(raw)
    bdata=raw[["benchmark_id","star_truth_class"]].merge(broad,on="benchmark_id")
    bdata["split"]=bdata.benchmark_id.map(split_for)
    bf=[c for c in broad.columns if c!="benchmark_id"]
    btr=bdata.split.eq("train"); bca=bdata.split.eq("calibration"); bte=bdata.split.eq("test")
    hgb=HistGradientBoostingClassifier(loss="log_loss",learning_rate=0.05,max_iter=300,
        max_leaf_nodes=11,min_samples_leaf=10,l2_regularization=1.0,random_state=42)
    hgb_model=calibrated(hgb,bdata.loc[btr,bf],bdata.loc[btr,"star_truth_class"],
                         bdata.loc[bca,bf],bdata.loc[bca,"star_truth_class"])
    bp=hgb_model.predict_proba(bdata.loc[bte,bf]); bc=list(hgb_model.classes_)
    bpred=np.array(bc)[np.argmax(bp,axis=1)]
    by=bdata.loc[bte,"star_truth_class"].to_numpy()
    if list(data.loc[te,"benchmark_id"])!=list(bdata.loc[bte,"benchmark_id"]):
        raise RuntimeError("broadband and XP test rows misaligned")

    result={
      "xp_rows":int(len(data)),
      "class_counts":data.star_truth_class.value_counts().to_dict(),
      "split_counts":data.split.value_counts().to_dict(),
      "test_rows":int(te.sum()),
      "xp_feature_count":len(xp),
      "broadband_same_subset":metrics(by,bpred,bp,bc),
      "xp_random_forest":metrics(y,rpred,rp,rc),
      "decision_guard":"XP prototype is not production until external/subtype-diverse validation is complete"
    }
    pd.DataFrame(confusion_matrix(y,bpred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"broadband_confusion.csv")
    pd.DataFrame(confusion_matrix(y,rpred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"xp_rf_confusion.csv")
    q=data.loc[te,["benchmark_id","star_truth_class"]].copy()
    q["broadband_prediction"]=bpred
    q["xp_prediction"]=rpred
    q["p_db_xp"]=rp[:,rc.index("DB")]
    q.to_csv(a.out/"test_predictions.csv",index=False)
    imp=getattr(rf,"feature_importances_",None)
    if imp is not None:
        pd.DataFrame({"feature":xp,"importance":imp}).sort_values("importance",ascending=False).to_csv(a.out/"xp_feature_importance.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()

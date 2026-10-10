#!/usr/bin/env python3
"""Train DA/DB Gaia-XP model on LAMOST truth and evaluate on independent SDSS truth."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_score, recall_score
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None

ROOT=Path(__file__).resolve().parent
CLASSES=["DA","DB"]

def load_internal():
    p=ROOT/"train_validate_wd_subtype_xp.py"
    s=importlib.util.spec_from_file_location("wdxp_core",p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def calibrated(base,xtrain,ytrain,xcal,ycal):
    base.fit(xtrain,ytrain)
    if FrozenEstimator is not None:
        model=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        model=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    model.fit(xcal,ycal)
    return model

def metric_block(y,pred,p,classes):
    return {
      "accuracy":float(accuracy_score(y,pred)),
      "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
      "macro_f1":float(f1_score(y,pred,average="macro")),
      "db_precision":float(precision_score(y,pred,pos_label="DB",zero_division=0)),
      "db_recall":float(recall_score(y,pred,pos_label="DB",zero_division=0)),
      "db_f1":float(f1_score(y,pred,pos_label="DB",zero_division=0)),
      "log_loss":float(log_loss(y,p,labels=classes)),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--lamost-xp",type=Path,required=True)
    ap.add_argument("--sdss-xp",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    train=pd.read_csv(a.lamost_xp)
    ext=pd.read_csv(a.sdss_xp)
    if set(train.star_truth_class)!={"DA","DB"} or set(ext.star_truth_class)!={"DA","DB"}:
        raise ValueError("both datasets must contain exact DA/DB truth")
    xp=[c for c in train.columns if (c.startswith("xp_bp_") or c.startswith("xp_rp_")) and c[-2:].isdigit()]
    if len(xp)!=110 or any(c not in ext.columns for c in xp):
        raise ValueError(f"expected common 110 XP coefficient features; found train={len(xp)}")

    core=load_internal()
    train["split"]=train.benchmark_id.map(core.split_for)
    tr=train.split.eq("train"); ca=train.split.eq("calibration")
    ytr=train.loc[tr,"star_truth_class"]; yca=train.loc[ca,"star_truth_class"]
    if min(ytr.value_counts().reindex(CLASSES,fill_value=0))<20 or min(yca.value_counts().reindex(CLASSES,fill_value=0))<8:
        raise RuntimeError("LAMOST train/calibration split insufficient")

    rf=RandomForestClassifier(
        n_estimators=1000,max_features="sqrt",class_weight="balanced",
        random_state=42,n_jobs=-1,
    )
    model=calibrated(rf,train.loc[tr,xp],ytr,train.loc[ca,xp],yca)

    y=ext.star_truth_class.to_numpy()
    p=model.predict_proba(ext[xp]); classes=list(model.classes_)
    pred=np.array(classes)[np.argmax(p,axis=1)]
    conf=np.max(p,axis=1)

    # Conservative selective operating points are reported, not tuned on SDSS.
    selective={}
    for th in (0.80,0.90,0.95):
        keep=conf>=th
        selective[f"p_ge_{th:.2f}"]={
          "coverage":float(keep.mean()),
          "n":int(keep.sum()),
          "accuracy":float(accuracy_score(y[keep],pred[keep])) if keep.any() else None,
          "balanced_accuracy":float(balanced_accuracy_score(y[keep],pred[keep])) if keep.any() else None,
          "macro_f1":float(f1_score(y[keep],pred[keep],average="macro")) if keep.any() else None,
        }

    result={
      "train_domain":"LAMOST_DR5_GUO2022",
      "external_domain":"SDSS_DR14_KEPLER2019",
      "lamost_xp_rows":int(len(train)),
      "lamost_train_rows":int(tr.sum()),
      "lamost_calibration_rows":int(ca.sum()),
      "external_xp_rows":int(len(ext)),
      "external_class_counts":ext.star_truth_class.value_counts().to_dict(),
      "xp_feature_count":len(xp),
      "external":metric_block(y,pred,p,classes),
      "selective":selective,
      "decision_guard":"External SDSS performance must be considered before enabling DA/DB output in the STAR branch."
    }
    pd.DataFrame(confusion_matrix(y,pred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"external_confusion.csv")
    q=ext[["benchmark_id","star_truth_class"]].copy()
    q["prediction"]=pred
    q["confidence"]=conf
    q["p_db"]=p[:,classes.index("DB")]
    q.to_csv(a.out/"external_predictions.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()

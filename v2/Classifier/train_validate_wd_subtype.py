#!/usr/bin/env python3
"""Exploratory DA vs DB classifier using Gaia broadband astrometry/photometry.

This intentionally tests whether non-spectral Gaia features are sufficient for
white-dwarf subtype classification before introducing XP/spectrum models.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
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

def brier_db(y,p):
    yy=(np.asarray(y)=="DB").astype(float)
    return float(np.mean((p-yy)**2))

def score_block(y,pred,p=None,classes=None):
    out={
      "accuracy":float(accuracy_score(y,pred)),
      "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
      "macro_f1":float(f1_score(y,pred,average="macro")),
      "db_precision":float(precision_score(y,pred,pos_label="DB",zero_division=0)),
      "db_recall":float(recall_score(y,pred,pos_label="DB",zero_division=0)),
      "db_f1":float(f1_score(y,pred,pos_label="DB",zero_division=0)),
    }
    if p is not None:
        out["log_loss"]=float(log_loss(y,p,labels=classes))
        out["db_brier"]=brier_db(y,p[:,list(classes).index("DB")])
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    raw=pd.read_csv(a.features)
    if set(raw.star_truth_class)!={"DA","DB"}:
        raise ValueError(f"expected DA/DB truth, got {sorted(set(raw.star_truth_class))}")
    core=load_core()
    x=core.prepare(raw)
    data=raw[["benchmark_id","star_truth_class"]].merge(x,on="benchmark_id")
    data["split"]=data.benchmark_id.map(split_for)
    feats=[c for c in x.columns if c!="benchmark_id"]
    tr=data.split.eq("train"); ca=data.split.eq("calibration"); te=data.split.eq("test")
    ytr=data.loc[tr,"star_truth_class"]; yca=data.loc[ca,"star_truth_class"]; y=data.loc[te,"star_truth_class"].to_numpy()

    # Linear baseline: asks how much broad colour/astrometry separation exists.
    logistic=Pipeline([
      ("impute",SimpleImputer(strategy="median",add_indicator=True)),
      ("scale",StandardScaler()),
      ("clf",LogisticRegression(max_iter=2000,class_weight="balanced",random_state=42))
    ])
    logistic.fit(data.loc[tr,feats],ytr)
    lp=logistic.predict_proba(data.loc[te,feats]); lc=list(logistic.classes_)
    lpred=np.array(lc)[np.argmax(lp,axis=1)]

    # Nonlinear candidate + held-out calibration.
    base=HistGradientBoostingClassifier(loss="log_loss",learning_rate=0.05,max_iter=300,
        max_leaf_nodes=11,min_samples_leaf=10,l2_regularization=1.0,random_state=42)
    base.fit(data.loc[tr,feats],ytr)
    if FrozenEstimator is not None:
        model=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        model=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    model.fit(data.loc[ca,feats],yca)
    p=model.predict_proba(data.loc[te,feats]); classes=list(model.classes_)
    pred=np.array(classes)[np.argmax(p,axis=1)]

    metrics={
      "matched_rows":int(len(data)),
      "class_counts":data.star_truth_class.value_counts().to_dict(),
      "split_counts":data.split.value_counts().to_dict(),
      "test_rows":int(te.sum()),
      "feature_count":len(feats),
      "logistic_baseline":score_block(y,lpred,lp,lc),
      "hist_gradient_boosting":score_block(y,pred,p,classes),
      "interpretation_guard":"Gaia broadband-only prototype; do not deploy DA/DB subtype unless performance and external validation are sufficient"
    }
    pd.DataFrame(confusion_matrix(y,lpred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"logistic_confusion.csv")
    pd.DataFrame(confusion_matrix(y,pred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"hgb_confusion.csv")
    q=data.loc[te,["benchmark_id","star_truth_class"]].copy()
    q["logistic_prediction"]=lpred; q["hgb_prediction"]=pred
    q["p_db"]=p[:,classes.index("DB")]
    q.to_csv(a.out/"test_predictions.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()

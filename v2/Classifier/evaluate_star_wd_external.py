#!/usr/bin/env python3
"""Train the STAR WD model on SDSS truth and evaluate unchanged on LAMOST truth."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
    precision_score, recall_score, confusion_matrix, classification_report, log_loss)

from train_validate_star_wd import prepare, split_for, brier_binary, CLASSES

def align(train_x,test_x,features):
    for c in features:
        if c not in test_x.columns:
            test_x[c]=np.nan
    return test_x[["benchmark_id"]+features]

def hr_baseline(data):
    usable=(data.parallax_over_error>1)&data.absolute_g.notna()&data.bp_rp.notna()
    pred=np.where(usable & (data.absolute_g > 6+5*data.bp_rp),"WHITE_DWARF","NORMAL_STAR")
    return pred,usable.to_numpy()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sdss-features",type=Path,required=True)
    ap.add_argument("--external-features",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    sraw=pd.read_csv(a.sdss_features)
    eraw=pd.read_csv(a.external_features)
    sx=prepare(sraw); ex=prepare(eraw)
    s=sraw[["benchmark_id","star_truth_class"]].merge(sx,on="benchmark_id")
    e=eraw[["benchmark_id","star_truth_class","truth_source"]].merge(ex,on="benchmark_id")
    s["split"]=s.benchmark_id.map(split_for)

    feats=[c for c in sx.columns if c!="benchmark_id"]
    ex=align(sx,ex,feats)
    e=e[["benchmark_id","star_truth_class","truth_source"]].merge(ex,on="benchmark_id")

    tr=s.split.eq("train"); ca=s.split.eq("calibration")
    base=HistGradientBoostingClassifier(loss="log_loss",learning_rate=0.05,max_iter=300,
        max_leaf_nodes=15,min_samples_leaf=15,l2_regularization=1.0,random_state=42)
    base.fit(s.loc[tr,feats],s.loc[tr,"star_truth_class"])
    if FrozenEstimator is not None:
        model=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        model=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    model.fit(s.loc[ca,feats],s.loc[ca,"star_truth_class"])

    y=e.star_truth_class.to_numpy()
    p=model.predict_proba(e[feats]); classes=list(model.classes_)
    pred=np.asarray(classes)[np.argmax(p,axis=1)]
    pwd=p[:,classes.index("WHITE_DWARF")]
    bpred,busable=hr_baseline(e)

    metrics={
      "training_source":"SDSS_DR18_SPECTROSCOPY",
      "external_source_counts":e.truth_source.value_counts().to_dict(),
      "sdss_train_rows":int(tr.sum()),
      "sdss_calibration_rows":int(ca.sum()),
      "external_rows":int(len(e)),
      "external_class_counts":e.star_truth_class.value_counts().to_dict(),
      "feature_count":len(feats),
      "baseline":{
        "usable_fraction":float(busable.mean()),
        "accuracy":float(accuracy_score(y,bpred)),
        "balanced_accuracy":float(balanced_accuracy_score(y,bpred)),
        "wd_precision":float(precision_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_recall":float(recall_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_f1":float(f1_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
      },
      "learned":{
        "accuracy":float(accuracy_score(y,pred)),
        "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
        "macro_f1":float(f1_score(y,pred,average="macro")),
        "wd_precision":float(precision_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_recall":float(recall_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_f1":float(f1_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "log_loss":float(log_loss(y,p,labels=classes)),
        "brier_white_dwarf":brier_binary(y,pwd),
      }
    }
    if busable.any():
        metrics["baseline"]["usable_only_accuracy"]=float(accuracy_score(y[busable],bpred[busable]))
        metrics["learned"]["on_baseline_usable_accuracy"]=float(accuracy_score(y[busable],pred[busable]))

    pd.DataFrame(confusion_matrix(y,bpred,labels=CLASSES),
        index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"baseline_confusion.csv")
    pd.DataFrame(confusion_matrix(y,pred,labels=CLASSES),
        index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"learned_confusion.csv")
    pd.DataFrame(classification_report(y,pred,labels=CLASSES,output_dict=True,zero_division=0)).T.to_csv(a.out/"classification_report.csv")
    q=e[["benchmark_id","star_truth_class","truth_source"]].copy()
    q["baseline_prediction"]=bpred; q["learned_prediction"]=pred; q["p_white_dwarf"]=pwd
    q.to_csv(a.out/"external_predictions.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    print(json.dumps(metrics,indent=2))

if __name__=="__main__": main()

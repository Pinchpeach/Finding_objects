#!/usr/bin/env python3
"""Train on SDSS STAR truth and evaluate on independent LAMOST spectroscopy."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, log_loss

ROOT=Path(__file__).resolve().parent
CLASSES=["NORMAL_STAR","WHITE_DWARF"]

def load_core():
    p=ROOT/"train_validate_star_wd.py"
    s=importlib.util.spec_from_file_location("starwd_core",p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def brier(y,p):
    yy=(np.asarray(y)=="WHITE_DWARF").astype(float)
    return float(np.mean((p-yy)**2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sdss-features",type=Path,required=True)
    ap.add_argument("--external-features",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

    core=load_core()
    sd=pd.read_csv(a.sdss_features); ex=pd.read_csv(a.external_features)
    xs=core.prepare(sd); xe=core.prepare(ex)
    ds=sd[["benchmark_id","star_truth_class"]].merge(xs,on="benchmark_id")
    de=ex[["benchmark_id","star_truth_class","truth_source"]].merge(xe,on="benchmark_id")

    # Keep the exact same deterministic SDSS train/calibration partition used in
    # the internal benchmark; the former SDSS test partition is not used here.
    ds["split"]=ds.benchmark_id.map(core.split_for)
    tr=ds.split.eq("train"); ca=ds.split.eq("calibration")
    feats=[c for c in xs.columns if c!="benchmark_id"]
    # External data can have a different missingness pattern. Align columns to
    # the SDSS-trained feature schema without inventing measurements.
    for c in feats:
        if c not in de.columns:
            if c.startswith("missing__"):
                base_name=c[len("missing__"):]
                de[c]=de[base_name].isna().astype(float) if base_name in de.columns else 1.0
            else:
                de[c]=np.nan
    de=de.copy()

    base=HistGradientBoostingClassifier(loss="log_loss",learning_rate=0.05,max_iter=300,
        max_leaf_nodes=15,min_samples_leaf=15,l2_regularization=1.0,random_state=42)
    base.fit(ds.loc[tr,feats],ds.loc[tr,"star_truth_class"])
    if FrozenEstimator is not None:
        model=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        model=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    model.fit(ds.loc[ca,feats],ds.loc[ca,"star_truth_class"])

    y=de.star_truth_class.to_numpy()
    p=model.predict_proba(de[feats]); classes=list(model.classes_)
    pred=np.array(classes)[np.argmax(p,axis=1)]
    pwd=p[:,classes.index("WHITE_DWARF")]

    usable=(de.parallax_over_error>1)&de.absolute_g.notna()&de.bp_rp.notna()
    bpred=np.where(usable&(de.absolute_g>6+5*de.bp_rp),"WHITE_DWARF","NORMAL_STAR")
    um=usable.to_numpy()
    hybrid=np.where(um,bpred,pred)
    conf=np.max(p,axis=1)
    consensus=np.full(len(y),"UNKNOWN",dtype=object)
    agree=um & (bpred==pred)
    consensus[agree]=pred[agree]
    fallback=(~um) & (conf>=0.90)
    consensus[fallback]=pred[fallback]
    classified=consensus!="UNKNOWN"

    metrics={
      "sdss_training_rows":int(tr.sum()),
      "sdss_calibration_rows":int(ca.sum()),
      "external_rows":int(len(de)),
      "external_class_counts":de.star_truth_class.value_counts().to_dict(),
      "external_truth_sources":de.truth_source.value_counts().to_dict(),
      "baseline":{
        "usable_fraction":float(um.mean()),
        "accuracy":float(accuracy_score(y,bpred)),
        "balanced_accuracy":float(balanced_accuracy_score(y,bpred)),
        "wd_precision":float(precision_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_recall":float(recall_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_f1":float(f1_score(y,bpred,pos_label="WHITE_DWARF",zero_division=0)),
        "usable_only":{
          "n":int(um.sum()),
          "accuracy":float(accuracy_score(y[um],bpred[um])) if um.any() else None,
          "balanced_accuracy":float(balanced_accuracy_score(y[um],bpred[um])) if um.any() else None,
          "wd_f1":float(f1_score(y[um],bpred[um],pos_label="WHITE_DWARF",zero_division=0)) if um.any() else None,
        }
      },
      "consensus":{
        "policy":"classify when HR baseline and calibrated model agree; if HR unavailable use model only at p>=0.90; otherwise UNKNOWN",
        "coverage":float(classified.mean()),
        "classified_rows":int(classified.sum()),
        "accuracy_when_classified":float(accuracy_score(y[classified],consensus[classified])) if classified.any() else None,
        "balanced_accuracy_when_classified":float(balanced_accuracy_score(y[classified],consensus[classified])) if classified.any() else None,
        "macro_f1_when_classified":float(f1_score(y[classified],consensus[classified],average="macro")) if classified.any() else None,
        "unknown_rows":int((~classified).sum())
      },
      "hybrid":{
        "policy":"literature HR baseline when usable; calibrated SDSS-trained model only as fallback",
        "accuracy":float(accuracy_score(y,hybrid)),
        "balanced_accuracy":float(balanced_accuracy_score(y,hybrid)),
        "macro_f1":float(f1_score(y,hybrid,average="macro")),
        "wd_precision":float(precision_score(y,hybrid,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_recall":float(recall_score(y,hybrid,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_f1":float(f1_score(y,hybrid,pos_label="WHITE_DWARF",zero_division=0)),
        "fallback_rows":int((~um).sum())
      },
      "learned":{
        "accuracy":float(accuracy_score(y,pred)),
        "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
        "macro_f1":float(f1_score(y,pred,average="macro")),
        "wd_precision":float(precision_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_recall":float(recall_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "wd_f1":float(f1_score(y,pred,pos_label="WHITE_DWARF",zero_division=0)),
        "log_loss":float(log_loss(y,p,labels=classes)),
        "wd_brier":brier(y,pwd),
        "on_baseline_usable_subset":{
          "n":int(um.sum()),
          "accuracy":float(accuracy_score(y[um],pred[um])) if um.any() else None,
          "balanced_accuracy":float(balanced_accuracy_score(y[um],pred[um])) if um.any() else None,
          "macro_f1":float(f1_score(y[um],pred[um],average="macro")) if um.any() else None,
        }
      }
    }

    pd.DataFrame(confusion_matrix(y,bpred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"baseline_confusion.csv")
    pd.DataFrame(confusion_matrix(y,pred,labels=CLASSES),
      index=[f"true_{c}" for c in CLASSES],columns=[f"pred_{c}" for c in CLASSES]).to_csv(a.out/"learned_confusion.csv")
    q=de[["benchmark_id","star_truth_class","truth_source"]].copy()
    q["baseline_prediction"]=bpred; q["learned_prediction"]=pred; q["hybrid_prediction"]=hybrid; q["consensus_prediction"]=consensus; q["p_white_dwarf"]=pwd
    q.to_csv(a.out/"external_predictions.csv",index=False)
    (a.out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()

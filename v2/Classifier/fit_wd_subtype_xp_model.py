#!/usr/bin/env python3
"""Fit a reproducible deployable Gaia-XP DA/DB classifier.

Uses all non-calibration LAMOST XP rows for the Random Forest base estimator and
keeps the deterministic calibration partition separate for sigmoid calibration.
External SDSS DR14 data are never used for fitting or calibration.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator=None

ROOT=Path(__file__).resolve().parent

def load_core():
    p=ROOT/"train_validate_wd_subtype_xp.py"
    s=importlib.util.spec_from_file_location("wdxp_core",p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",type=Path,required=True)
    ap.add_argument("--model-out",type=Path,required=True)
    ap.add_argument("--metadata-out",type=Path)
    a=ap.parse_args()

    d=pd.read_csv(a.features)
    if set(d.star_truth_class)!={"DA","DB"}:
        raise ValueError("deploy fitter requires exact DA/DB training truth")
    xp=[c for c in d.columns if (c.startswith("xp_bp_") or c.startswith("xp_rp_")) and c[-2:].isdigit()]
    if len(xp)!=110:
        raise ValueError(f"expected 110 Gaia XP coefficients, found {len(xp)}")
    core=load_core()
    d["split"]=d.benchmark_id.map(core.split_for)
    cal=d.split.eq("calibration")
    train=~cal
    if min(d.loc[cal,"star_truth_class"].value_counts().reindex(["DA","DB"],fill_value=0))<8:
        raise RuntimeError("calibration partition too small")

    base=RandomForestClassifier(
        n_estimators=1000,max_features="sqrt",class_weight="balanced",
        random_state=42,n_jobs=-1,
    )
    base.fit(d.loc[train,xp],d.loc[train,"star_truth_class"])
    if FrozenEstimator is not None:
        model=CalibratedClassifierCV(FrozenEstimator(base),method="sigmoid")
    else:
        model=CalibratedClassifierCV(base,method="sigmoid",cv="prefit")
    model.fit(d.loc[cal,xp],d.loc[cal,"star_truth_class"])

    a.model_out.parent.mkdir(parents=True,exist_ok=True)
    payload={
      "model":model,
      "features":xp,
      "classes":list(model.classes_),
      "subtype_confidence_threshold":0.90,
      "supported_subtypes":["DA","DB"],
      "training_domain":"LAMOST_DR5_GUO2022",
      "external_validation_domain":"SDSS_DR14_KEPLER2019",
    }
    joblib.dump(payload,a.model_out)
    meta={
      "rows":int(len(d)),
      "fit_rows":int(train.sum()),
      "calibration_rows":int(cal.sum()),
      "class_counts":d.star_truth_class.value_counts().to_dict(),
      "features":len(xp),
      "confidence_threshold":0.90,
      "supported_subtypes":["DA","DB"],
      "external_validation_run":36304882268,
    }
    mp=a.metadata_out or a.model_out.with_suffix(".json")
    Path(mp).write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,indent=2))

if __name__=="__main__": main()

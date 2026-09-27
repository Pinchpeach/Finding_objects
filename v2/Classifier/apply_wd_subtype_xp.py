#!/usr/bin/env python3
"""Annotate XP-enriched rows with calibrated DA/DB predictions.

This script does not decide whether an object is a white dwarf. It only appends
model outputs. The STAR routing branch independently checks WD-candidate status
and the >=0.90 confidence gate before exposing spectral_type.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

def run(inp:Path,model_path:Path,out:Path):
    d=pd.read_csv(inp)
    pack=joblib.load(model_path)
    model=pack["model"]; features=list(pack["features"])
    missing=[c for c in features if c not in d.columns]
    if missing:
        raise KeyError(f"missing Gaia XP coefficients: {missing[:8]}{'...' if len(missing)>8 else ''}")
    p=model.predict_proba(d[features])
    classes=list(model.classes_)
    pred=np.array(classes)[np.argmax(p,axis=1)]
    conf=np.max(p,axis=1)
    extra={
        "wd_xp_subtype_prediction":pred,
        "wd_xp_subtype_confidence":conf,
    }
    for i,cls in enumerate(classes):
        extra[f"p_wd_xp_{str(cls).lower()}"]=p[:,i]
    d=pd.concat([d,pd.DataFrame(extra,index=d.index)],axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); d.to_csv(out,index=False)
    print(f"[OK] XP subtype predictions rows={len(d)} threshold={pack.get('subtype_confidence_threshold',0.90)} -> {out}")
    print(pd.Series(pred).value_counts().to_string())
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(); run(a.input,a.model,a.out)
if __name__=="__main__": main()

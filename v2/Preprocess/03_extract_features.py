#!/usr/bin/env python3
"""Stage 3: derive rule-required classification features.

Preserves all integrated columns and adds deterministic derived features used by
classification_rules.csv. It does not classify objects.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def safe_div(a,b):
    a=pd.to_numeric(a,errors="coerce"); b=pd.to_numeric(b,errors="coerce")
    return a.div(b.where(b.ne(0)))

def run(objects:Path,rules_path:Path,out:Path)->Path:
    df=pd.read_csv(objects); rules=pd.read_csv(rules_path,keep_default_na=False)
    required=set()
    for cell in rules["feature_columns"]:
        required.update(x for x in str(cell).split("|") if x)
    # Build all derived columns together, then concatenate once. This avoids
    # repeated DataFrame.insert calls and fragmentation as feature count grows.
    derived={}
    if {"parallax","parallax_error"}.issubset(df.columns):
        derived["parallax_snr"]=safe_div(df["parallax"].abs(),df["parallax_error"])
        derived["normalized_corrected_parallax"]=safe_div((pd.to_numeric(df["parallax"],errors="coerce")+0.017).abs(),df["parallax_error"])
    pm={"pmra","pmra_error","pmdec","pmdec_error"}
    if pm.issubset(df.columns):
        a=safe_div(df["pmra"],df["pmra_error"]); d=safe_div(df["pmdec"],df["pmdec_error"])
        derived["proper_motion_significance"]=np.sqrt(a*a+d*d)
    if derived:
        df=pd.concat([df,pd.DataFrame(derived,index=df.index)],axis=1)

    available=[c for c in required if c in df.columns]
    coverage=df[available].notna().sum(axis=1) if available else pd.Series(0,index=df.index)
    metadata=pd.DataFrame({
        "rule_feature_coverage":coverage.astype(int),
        "rule_feature_total":len(required),
    },index=df.index)
    df=pd.concat([df,metadata],axis=1)

    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] required_features={len(required)} objects={len(df)} -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--objects",type=Path,default=root/"integrated_objects.csv")
    p.add_argument("--rules",type=Path,default=root/"classification_rules.csv")
    p.add_argument("--out",type=Path,default=root/"features.csv")
    a=p.parse_args(); run(a.objects,a.rules,a.out)
if __name__=="__main__": main()

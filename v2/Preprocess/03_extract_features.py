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
    # Pan-STARRS photometric colours and PSF-Kron morphology proxies.
    # These are continuous measurements only; no class threshold is applied here.
    ps1_bands=("g","r","i","z","y")
    def ps1_col(name):
        if name in df.columns:
            return name
        pref=f"pan_starrs1_dr2_meanobject__{name}"
        return pref if pref in df.columns else None
    psf={b:ps1_col(f"{b}MeanPSFMag") for b in ps1_bands}
    kron={b:ps1_col(f"{b}MeanKronMag") for b in ps1_bands}
    def valid_ps1_mag(col):
        s=pd.to_numeric(df[col],errors="coerce")
        # PS1 uses sentinel/non-physical values (notably -999) for missing photometry.
        return s.where((s>0)&(s<40))
    psf_mag={b:(valid_ps1_mag(psf[b]) if psf[b] else None) for b in ps1_bands}
    kron_mag={b:(valid_ps1_mag(kron[b]) if kron[b] else None) for b in ps1_bands}
    for b1,b2 in zip(ps1_bands,ps1_bands[1:]):
        if psf_mag[b1] is not None and psf_mag[b2] is not None:
            derived[f"ps1_{b1}_{b2}_color"]=psf_mag[b1]-psf_mag[b2]
    for b in ps1_bands:
        if psf_mag[b] is not None and kron_mag[b] is not None:
            derived[f"ps1_{b}_psf_minus_kron"]=psf_mag[b]-kron_mag[b]
    # Preserve uncertainty and per-band detection counts so later evidence
    # rules can gate on measurement quality rather than colour alone.
    for b in ps1_bands:
        err_col=ps1_col(f"{b}MeanPSFMagErr")
        n_col=ps1_col(f"n{b}")
        if err_col:
            err=pd.to_numeric(df[err_col],errors="coerce")
            derived[f"ps1_{b}_psf_mag_err"]=err.where((err>0)&(err<5))
        if n_col:
            n=pd.to_numeric(df[n_col],errors="coerce")
            derived[f"ps1_n_{b}"]=n.where(n>=0)

    ndet=ps1_col("nDetections")
    if ndet:
        n=pd.to_numeric(df[ndet],errors="coerce")
        derived["ps1_n_detections"]=n.where(n>=0)

    # Data-quality flags only. These do not imply an astronomical class.
    # A band is usable when it has a physical PSF magnitude, a finite positive
    # uncertainty, and at least one contributing detection.
    for b in ps1_bands:
        if psf_mag[b] is None: continue
        err=derived.get(f"ps1_{b}_psf_mag_err")
        n=derived.get(f"ps1_n_{b}")
        if err is not None and n is not None:
            derived[f"ps1_{b}_photometry_valid"]=(psf_mag[b].notna()&err.notna()&(n>0)).astype("Int64")

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

#!/usr/bin/env python3
"""Build balanced, spectroscopically labelled benchmark seeds.

Ground truth comes only from SDSS spectroscopy with ZWARNING=0.  The output
catalog files contain coordinates + hidden truth metadata and are intended to
seed independent catalog lookups.  Truth columns must never be passed to the
classifier as features.
"""
from __future__ import annotations
import argparse,io,urllib.parse,urllib.request
from pathlib import Path
import pandas as pd

CLASSES=("STAR","GALAXY","QSO")
CATALOGS=("gaia_dr3","panstarrs1","allwise","twomass","galex","sdss_dr18",
          "desi_legacy","nvss","first","lotss","vlass","chandra","xmm","erosita")
SKY_URL="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def query_sdss(per_class:int)->pd.DataFrame:
    blocks=[]
    # Deterministic, spatially spread sample. TOP is deliberately larger than
    # requested so deduplication/quality filtering still leaves the quota.
    for cls in CLASSES:
        sql=f"""SELECT TOP {per_class*3} s.specObjID,s.bestObjID,s.ra,s.dec,
 s.class,s.subClass,s.z,s.zErr,s.zWarning,s.plate,s.mjd,s.fiberID
 FROM SpecObj AS s
 WHERE s.class='{cls}' AND s.zWarning=0
   AND s.sciencePrimary=1 AND s.ra IS NOT NULL AND s.dec IS NOT NULL
 ORDER BY s.specObjID"""
        url=SKY_URL+"?"+urllib.parse.urlencode({"cmd":sql,"format":"csv"})
        with urllib.request.urlopen(url,timeout=90) as resp:
            d=pd.read_csv(io.BytesIO(resp.read()))
        # SkyServer column casing can vary by endpoint/release. Canonicalize
        # immediately so all downstream identifiers are deterministic.
        d.columns=[str(x).strip().lower() for x in d.columns]
        if "specobjid" not in d.columns:
            raise KeyError(f"SDSS response missing specobjid; got {list(d.columns)}")
        d["truth_class"]=cls; blocks.append(d)
    df=pd.concat(blocks,ignore_index=True)
    df=df.drop_duplicates("specobjid")
    return pd.concat([df[df["truth_class"].eq(c)].head(per_class) for c in CLASSES],ignore_index=True)

def run(out_dir:Path,total:int=300):
    if total%len(CLASSES): raise ValueError("total must be divisible by 3")
    per=total//len(CLASSES); truth=query_sdss(per)
    if any((truth.truth_class==c).sum()!=per for c in CLASSES):
        raise RuntimeError("SDSS did not return enough clean labels for every class")
    truth.columns=[str(c).strip().lower() for c in truth.columns]
    truth["truth_source"]="SDSS_DR18_SPECTROSCOPY"
    truth["truth_quality"]="ZWARNING_0_SCIENCEPRIMARY"
    truth["benchmark_id"]=[f"TRD{i+1:06d}" for i in range(len(truth))]
    out_dir.mkdir(parents=True,exist_ok=True)
    truth.to_csv(out_dir/"ground_truth.csv",index=False)
    # One seed file per feature catalog, exactly as requested.  The same balanced
    # objects are used across catalogs so catalog coverage can be compared fairly.
    cols=["benchmark_id","ra","dec","truth_class","truth_source","truth_quality"]
    for cat in CATALOGS:
        truth[cols].to_csv(out_dir/f"{cat}_trd.csv",index=False)
    summary=truth.groupby("truth_class").size().rename("count").reset_index()
    summary.to_csv(out_dir/"truth_summary.csv",index=False)
    print(summary.to_string(index=False))
    print(f"[OK] {len(truth)} balanced truth objects -> {out_dir}")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--out-dir",type=Path,default=Path(__file__).resolve().parent/"truth_data")
    p.add_argument("--total",type=int,default=300); a=p.parse_args(); run(a.out_dir,a.total)
if __name__=="__main__": main()

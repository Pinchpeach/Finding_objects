#!/usr/bin/env python3
"""Build balanced, spectroscopically labelled benchmark seeds.

Ground truth comes only from SDSS spectroscopy with ZWARNING=0.  The output
catalog files contain coordinates + hidden truth metadata and are intended to
seed independent catalog lookups.  Truth columns must never be passed to the
classifier as features.
"""
from __future__ import annotations
import argparse,io,time,urllib.parse,urllib.request
from pathlib import Path
import pandas as pd

CLASSES=("STAR","GALAXY","QSO")
CATALOGS=("gaia_dr3","panstarrs1","allwise","twomass","galex","sdss_dr18",
          "desi_legacy","nvss","first","lotss","vlass","chandra","xmm","erosita")
SKY_URL="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def _fetch_csv(sql:str,retries:int=5,timeout:int=180)->pd.DataFrame:
    url=SKY_URL+"?"+urllib.parse.urlencode({"cmd":sql,"format":"csv"})
    last=None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url,timeout=timeout) as resp:
                raw=resp.read()
            return pd.read_csv(io.BytesIO(raw),comment="#")
        except Exception as e:
            last=e
            if attempt+1<retries:
                time.sleep(min(30,2**attempt*2))
    raise RuntimeError(f"SDSS query failed after {retries} attempts: {last}")

def _normalize_sdss(d:pd.DataFrame)->pd.DataFrame:
    d.columns=[str(x).strip().lower() for x in d.columns]
    if "specobjid" not in d.columns:
        raise KeyError(f"SDSS response missing specobjid; got {list(d.columns)}")
    return d

def query_first_radio(per_class:int)->pd.DataFrame:
    """Return a bounded radio-selected supplement using the SDSS-FIRST match table."""
    blocks=[]
    for cls in ("GALAXY","QSO"):
        sql=f"""SELECT TOP {per_class*3} s.specObjID,s.bestObjID,s.ra,s.dec,
 s.class,s.subClass,s.z,s.zErr,s.zWarning,s.plate,s.mjd,s.fiberID
 FROM SpecObj AS s
 JOIN First AS f ON f.objID=s.bestObjID
 WHERE s.class='{cls}' AND s.zWarning=0 AND s.sciencePrimary=1
   AND s.ra IS NOT NULL AND s.dec IS NOT NULL
 ORDER BY s.specObjID"""
        d=_normalize_sdss(_fetch_csv(sql))
        d["truth_class"]=cls
        d["truth_selection"]="FIRST_RADIO"
        d["truth_radio_catalog"]="FIRST"
        blocks.append(d.head(per_class))
    return pd.concat(blocks,ignore_index=True) if blocks else pd.DataFrame()

def query_sdss(per_class:int,radio_per_extragalactic:int=50)->pd.DataFrame:
    radio=query_first_radio(radio_per_extragalactic)
    blocks=[]
    # Deterministic, spatially spread sample. TOP is deliberately larger than
    # requested so deduplication/quality filtering still leaves the quota.
    for cls in CLASSES:
        sql=f"""SELECT TOP {per_class+80} s.specObjID,s.bestObjID,s.ra,s.dec,
 s.class,s.subClass,s.z,s.zErr,s.zWarning,s.plate,s.mjd,s.fiberID
 FROM SpecObj AS s
 WHERE s.class='{cls}' AND s.zWarning=0
   AND s.sciencePrimary=1 AND s.ra IS NOT NULL AND s.dec IS NOT NULL
 ORDER BY s.specObjID"""
        # Retry transient SkyServer timeouts instead of failing the whole build.
        d=_fetch_csv(sql)
        d=_normalize_sdss(d)
        d["truth_class"]=cls; d["truth_selection"]="GENERAL"; d["truth_radio_catalog"]=""
        # Reserve part of GALAXY/QSO for radio-selected truth, then fill from
        # the general spectroscopic population without duplicating spectra.
        reserved=radio[radio["truth_class"].eq(cls)] if len(radio) else pd.DataFrame()
        need=per_class-len(reserved)
        if len(radio):
            d=d[~d["specobjid"].isin(set(radio["specobjid"]))]
        blocks.append(pd.concat([reserved,d.head(max(0,need))],ignore_index=True))
    df=pd.concat(blocks,ignore_index=True).drop_duplicates("specobjid")
    return pd.concat([df[df["truth_class"].eq(c)].head(per_class) for c in CLASSES],ignore_index=True)

def run(out_dir:Path,total:int=999):
    if total%len(CLASSES): raise ValueError("total must be divisible by 3")
    per=total//len(CLASSES); truth=query_sdss(per,radio_per_extragalactic=min(50,per//3))
    if any((truth.truth_class==c).sum()!=per for c in CLASSES):
        raise RuntimeError("SDSS did not return enough clean labels for every class")
    truth.columns=[str(c).strip().lower() for c in truth.columns]
    truth["truth_source"]="SDSS_DR18_SPECTROSCOPY"
    truth["truth_quality"]="ZWARNING_0_SCIENCEPRIMARY"
    if "truth_selection" not in truth: truth["truth_selection"]="GENERAL"
    if "truth_radio_catalog" not in truth: truth["truth_radio_catalog"]=""
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
    p.add_argument("--total",type=int,default=999); a=p.parse_args(); run(a.out_dir,a.total)
if __name__=="__main__": main()

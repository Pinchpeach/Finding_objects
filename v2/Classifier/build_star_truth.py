#!/usr/bin/env python3
"""Build an independent STAR-branch truth set from clean SDSS spectroscopy.

Initial validated task: WHITE_DWARF vs NORMAL_STAR.
Binary and variability truth are intentionally excluded because SDSS subclass
labels are not sufficient independent truth for those axes.
"""
from __future__ import annotations
import argparse, io, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

URL="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def fetch(sql,retries=5,timeout=180):
    q=URL+"?"+urllib.parse.urlencode({"cmd":sql,"format":"csv"})
    last=None
    for i in range(retries):
        try:
            with urllib.request.urlopen(q,timeout=timeout) as r: raw=r.read()
            d=pd.read_csv(io.BytesIO(raw),comment="#")
            d.columns=[str(c).strip().lower() for c in d.columns]
            return d
        except Exception as e:
            last=e
            if i+1<retries: time.sleep(min(30,2**i*2))
    raise RuntimeError(f"SDSS query failed: {last}")

def query(label,where,n):
    sql=f"""SELECT TOP {n*3}
      s.specObjID,s.bestObjID,s.ra,s.dec,s.class,s.subClass,s.z,s.zErr,s.zWarning,
      s.plate,s.mjd,s.fiberID
      FROM SpecObj AS s
      WHERE s.class='STAR' AND s.zWarning=0 AND s.sciencePrimary=1
        AND s.ra IS NOT NULL AND s.dec IS NOT NULL
        AND ({where})
      ORDER BY s.specObjID"""
    d=fetch(sql)
    if "specobjid" not in d: raise KeyError(f"missing specobjid: {list(d.columns)}")
    d["star_truth_class"]=label
    return d.drop_duplicates("specobjid").head(n)

def run(out:Path,total=1000):
    n=total//2
    # SDSS uses WD-bearing subclass strings for spectroscopically identified
    # white dwarfs. Normal-star sample is explicitly restricted to common
    # Morgan-Keenan-leading subclass families to avoid exotic stellar objects.
    wd=query("WHITE_DWARF","UPPER(s.subClass) LIKE 'WD%'",n)
    normal=query("NORMAL_STAR",
      "(UPPER(s.subClass) LIKE 'O%' OR UPPER(s.subClass) LIKE 'B%' OR "
      "UPPER(s.subClass) LIKE 'A%' OR UPPER(s.subClass) LIKE 'F%' OR "
      "UPPER(s.subClass) LIKE 'G%' OR UPPER(s.subClass) LIKE 'K%' OR "
      "UPPER(s.subClass) LIKE 'M%') AND UPPER(s.subClass) NOT LIKE 'WD%'",n)
    d=pd.concat([wd,normal],ignore_index=True)
    if len(wd)<max(100,n//2) or len(normal)<max(100,n//2):
        raise RuntimeError(f"insufficient spectroscopy truth WD={len(wd)} normal={len(normal)}")
    d["benchmark_id"]=[f"STARTRD{i+1:06d}" for i in range(len(d))]
    d["truth_source"]="SDSS_DR18_SPECTROSCOPY"
    d["truth_quality"]="ZWARNING_0_SCIENCEPRIMARY"
    out.parent.mkdir(parents=True,exist_ok=True)
    d.to_csv(out,index=False)
    print(d.star_truth_class.value_counts().to_string())
    print(f"[OK] STAR truth rows={len(d)} -> {out}")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"star_truth.csv")
    p.add_argument("--total",type=int,default=1000)
    a=p.parse_args(); run(a.out,a.total)
if __name__=="__main__": main()

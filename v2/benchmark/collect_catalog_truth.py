#!/usr/bin/env python3
"""Cross-query balanced truth coordinates against existing v2 catalog collectors."""
from __future__ import annotations
import argparse, importlib.util, time, traceback
from pathlib import Path
import numpy as np, pandas as pd

V2=Path(__file__).resolve().parents[1]
GET=V2/"Get_data"
DEFAULT_TRUTH=Path(__file__).resolve().parent/"truth_data"/"ground_truth.csv"
DEFAULT_OUT=Path(__file__).resolve().parent/"catalog_data"
# Catalogs with existing independent collectors. Spectroscopic truth providers are
# deliberately excluded to prevent target leakage.
COLLECTORS=["gaia_dr3","panstarrs1","allwise","twomass","galex","desi_legacy",
            "nvss","first","lotss","vlass","chandra","xmm","erosita"]
RADII={"gaia_dr3":0.10,"panstarrs1":0.10,"allwise":0.15,"twomass":0.10,
       "galex":0.15,"desi_legacy":0.10,"nvss":0.25,"first":0.10,"lotss":0.15,
       "vlass":0.10,"chandra":0.15,"xmm":0.20,"erosita":0.30}

def load(name):
 p=GET/f"{name}.py"; s=importlib.util.spec_from_file_location("trd_"+name,p)
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def sep_arcsec(ra1,dec1,ra2,dec2):
 r1,d1,r2,d2=map(np.radians,[ra1,dec1,ra2,dec2])
 a=np.sin((d2-d1)/2)**2+np.cos(d1)*np.cos(d2)*np.sin((r2-r1)/2)**2
 return np.degrees(2*np.arcsin(np.sqrt(np.clip(a,0,1))))*3600

def run(truth_path,out_dir,limit=None):
 truth=pd.read_csv(truth_path)
 if limit: truth=pd.concat([g.head(limit) for _,g in truth.groupby("truth_class")],ignore_index=True)
 out_dir.mkdir(parents=True,exist_ok=True); summary=[]
 for name in COLLECTORS:
  mod=load(name); rows=[]; ok=empty=errors=0; radius=RADII[name]
  for i,t in truth.iterrows():
   try:
    d=mod.fetch(float(t.ra),float(t.dec),radius)
    if d is None or d.empty: empty+=1; continue
    d=d.copy()
    d["_sep_arcsec"]=sep_arcsec(float(t.ra),float(t.dec),
                                pd.to_numeric(d.ra,errors="coerce").to_numpy(),
                                pd.to_numeric(d.dec,errors="coerce").to_numpy())
    d=d.sort_values("_sep_arcsec").head(1)
    d.insert(0,"benchmark_id",t.benchmark_id); d.insert(1,"truth_class",t.truth_class)
    d.insert(2,"truth_source",t.truth_source); d.insert(3,"truth_ra",t.ra); d.insert(4,"truth_dec",t.dec)
    rows.append(d); ok+=1
   except Exception as e:
    errors+=1; print(f"[{name}] {t.benchmark_id} ERROR {e!r}",flush=True)
   if (i+1)%25==0: print(f"[{name}] {i+1}/{len(truth)} matched={ok} empty={empty} errors={errors}",flush=True)
   time.sleep(0.05)
  out=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=["benchmark_id","truth_class"])
  out.to_csv(out_dir/f"{name}_trd.csv",index=False)
  counts=out["truth_class"].value_counts().to_dict() if len(out) else {}
  summary.append({"catalog":name,"targets":len(truth),"matched":ok,"empty":empty,"errors":errors,
                  "STAR":counts.get("STAR",0),"GALAXY":counts.get("GALAXY",0),"QSO":counts.get("QSO",0)})
 pd.DataFrame(summary).to_csv(out_dir/"catalog_coverage.csv",index=False)
 print(pd.DataFrame(summary).to_string(index=False))

def main():
 p=argparse.ArgumentParser(); p.add_argument("--truth",type=Path,default=DEFAULT_TRUTH)
 p.add_argument("--out-dir",type=Path,default=DEFAULT_OUT); p.add_argument("--limit-per-class",type=int)
 a=p.parse_args(); run(a.truth,a.out_dir,a.limit_per_class)
if __name__=="__main__": main()

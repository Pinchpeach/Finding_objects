#!/usr/bin/env python3
"""Cross-query balanced truth coordinates against existing v2 catalog collectors."""
from __future__ import annotations
import argparse, importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np, pandas as pd

V2=Path(__file__).resolve().parents[1]
GET=V2/"Get_data"
DEFAULT_TRUTH=Path(__file__).resolve().parent/"truth_data"/"ground_truth.csv"
DEFAULT_OUT=Path(__file__).resolve().parent/"catalog_data"
COLLECTORS=["gaia_dr3","panstarrs1","allwise","twomass","galex","desi_legacy",
            "nvss","first","lotss","vlass","chandra","xmm","erosita"]
# Query radii (arcmin) are deliberately wider than the accepted counterpart radii.
RADII={"gaia_dr3":0.10,"panstarrs1":0.10,"allwise":0.15,"twomass":0.10,
       "galex":0.15,"desi_legacy":0.10,"nvss":0.25,"first":0.10,"lotss":0.15,
       "vlass":0.10,"chandra":0.15,"xmm":0.20,"erosita":0.30}
# Conservative project crossmatch gates in arcsec. These are engineering gates, not
# calibrated association probabilities; downstream validation must inspect separation
# distributions and can tighten them per survey/quality regime.
MATCH_ARCSEC={"gaia_dr3":2.0,"panstarrs1":2.0,"allwise":3.0,"twomass":2.5,
              "galex":5.0,"desi_legacy":2.0,"nvss":10.0,"first":3.0,"lotss":5.0,
              "vlass":3.0,"chandra":5.0,"xmm":8.0,"erosita":10.0}

def load(name):
 p=GET/f"{name}.py"; s=importlib.util.spec_from_file_location("trd_"+name,p)
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def sep_arcsec(ra1,dec1,ra2,dec2):
 r1,d1,r2,d2=map(np.radians,[ra1,dec1,ra2,dec2])
 a=np.sin((d2-d1)/2)**2+np.cos(d1)*np.cos(d2)*np.sin((r2-r1)/2)**2
 return np.degrees(2*np.arcsin(np.sqrt(np.clip(a,0,1))))*3600

def query_one(mod,name,radius,t):
 try:
  d=mod.fetch(float(t.ra),float(t.dec),radius)
  if d is None or d.empty: return "empty",None,None
  d=d.copy(); d["_sep_arcsec"]=sep_arcsec(float(t.ra),float(t.dec),pd.to_numeric(d.ra,errors="coerce").to_numpy(),pd.to_numeric(d.dec,errors="coerce").to_numpy())
  d=d[np.isfinite(d["_sep_arcsec"]) & (d["_sep_arcsec"] <= MATCH_ARCSEC[name])].sort_values("_sep_arcsec").head(1)
  if d.empty: return "empty",None,None
  d.insert(0,"benchmark_id",t.benchmark_id); d.insert(1,"truth_class",t.truth_class); d.insert(2,"truth_source",t.truth_source); d.insert(3,"truth_ra",t.ra); d.insert(4,"truth_dec",t.dec)
  d.insert(5,"match_threshold_arcsec",MATCH_ARCSEC[name])
  return "matched",d,None
 except Exception as e: return "error",None,repr(e)

def run_gaia(truth,out_dir):
 """Query Gaia once for all truth cones; avoids hundreds of slow joined TAP jobs."""
 from astroquery.gaia import Gaia
 mod=load("gaia_dr3"); radius=RADII["gaia_dr3"]/60.0
 select=[f"g.{c}" for c in mod.BASE]+[f"ap.{c}" for c in mod.DSC]+["vc.best_class_name","vc.best_class_score"]
 cones=[f"1=CONTAINS(POINT('ICRS',g.ra,g.dec),CIRCLE('ICRS',{float(t.ra)},{float(t.dec)},{radius}))" for _,t in truth.iterrows()]
 q=f"SELECT {','.join(select)} FROM gaiadr3.gaia_source AS g LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap ON g.source_id=ap.source_id LEFT OUTER JOIN gaiadr3.vari_classifier_result AS vc ON g.source_id=vc.source_id WHERE " + " OR ".join(cones)
 try: allg=Gaia.launch_job_async(q).get_results().to_pandas()
 except Exception as e:
  print(f"[gaia_dr3] batch ERROR {e!r}",flush=True); allg=pd.DataFrame()
 rows=[]
 if len(allg):
  allg.insert(0,"catalog",mod.CATALOG); allg.insert(1,"catalog_object_id",allg["source_id"].astype("Int64").astype(str)); allg.insert(2,"object_name",allg["designation"].astype(str))
 for _,t in truth.iterrows():
  if allg.empty: continue
  s=sep_arcsec(float(t.ra),float(t.dec),pd.to_numeric(allg.ra,errors="coerce").to_numpy(),pd.to_numeric(allg.dec,errors="coerce").to_numpy())
  idx=np.where(np.isfinite(s) & (s <= MATCH_ARCSEC["gaia_dr3"]))[0]
  if not len(idx): continue
  k=idx[np.argmin(s[idx])]; d=allg.iloc[[k]].copy(); d["_sep_arcsec"]=float(s[k])
  d.insert(0,"benchmark_id",t.benchmark_id); d.insert(1,"truth_class",t.truth_class); d.insert(2,"truth_source",t.truth_source); d.insert(3,"truth_ra",t.ra); d.insert(4,"truth_dec",t.dec); d.insert(5,"match_threshold_arcsec",MATCH_ARCSEC["gaia_dr3"]); rows.append(d)
 out=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=["benchmark_id","truth_class"]); out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
 counts=out.truth_class.value_counts().to_dict() if len(out) else {}; ok=len(out)
 print(f"[gaia_dr3] targets={len(truth)} matched={ok} empty={len(truth)-ok}",flush=True)
 return {"catalog":"gaia_dr3","targets":len(truth),"matched":ok,"empty":len(truth)-ok,"errors":0,"STAR":counts.get("STAR",0),"GALAXY":counts.get("GALAXY",0),"QSO":counts.get("QSO",0)}

def run_catalog(name,truth,out_dir,workers):
 if name=="gaia_dr3": return run_gaia(truth,out_dir)
 mod=load(name); radius=RADII[name]; rows=[]; ok=empty=errors=done=0
 with ThreadPoolExecutor(max_workers=workers) as ex:
  futs={ex.submit(query_one,mod,name,radius,t):t for _,t in truth.iterrows()}
  for f in as_completed(futs):
   t=futs[f]; status,d,err=f.result(); done+=1
   if status=="matched": rows.append(d); ok+=1
   elif status=="empty": empty+=1
   else: errors+=1; print(f"[{name}] {t.benchmark_id} ERROR {err}",flush=True)
   if done%25==0 or done==len(truth): print(f"[{name}] {done}/{len(truth)} matched={ok} empty={empty} errors={errors}",flush=True)
 out=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=["benchmark_id","truth_class"]); out=out.sort_values("benchmark_id") if len(out) else out; out.to_csv(out_dir/f"{name}_trd.csv",index=False)
 counts=out["truth_class"].value_counts().to_dict() if len(out) else {}
 return {"catalog":name,"targets":len(truth),"matched":ok,"empty":empty,"errors":errors,"STAR":counts.get("STAR",0),"GALAXY":counts.get("GALAXY",0),"QSO":counts.get("QSO",0)}

def run(truth_path,out_dir,limit=None,catalog=None,workers=8):
 truth=pd.read_csv(truth_path)
 if limit: truth=pd.concat([g.head(limit) for _,g in truth.groupby("truth_class")],ignore_index=True)
 out_dir.mkdir(parents=True,exist_ok=True); names=[catalog] if catalog else COLLECTORS
 summary=[run_catalog(name,truth,out_dir,workers) for name in names]; pd.DataFrame(summary).to_csv(out_dir/"catalog_coverage.csv",index=False); print(pd.DataFrame(summary).to_string(index=False))

def main():
 p=argparse.ArgumentParser(); p.add_argument("--truth",type=Path,default=DEFAULT_TRUTH); p.add_argument("--out-dir",type=Path,default=DEFAULT_OUT); p.add_argument("--limit-per-class",type=int); p.add_argument("--catalog",choices=COLLECTORS); p.add_argument("--workers",type=int,default=8)
 a=p.parse_args(); run(a.truth,a.out_dir,a.limit_per_class,a.catalog,max(1,a.workers))
if __name__=="__main__": main()

#!/usr/bin/env python3
"""Cross-query balanced truth coordinates against existing v2 catalog collectors."""
from __future__ import annotations
import argparse, importlib.util, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np, pandas as pd

V2=Path(__file__).resolve().parents[1]
GET=V2/"Get_data"
DEFAULT_TRUTH=Path(__file__).resolve().parent/"truth_data"/"ground_truth.csv"
DEFAULT_OUT=Path(__file__).resolve().parent/"catalog_data"
COLLECTORS=["gaia_dr3","panstarrs1","allwise","twomass","galex","desi_legacy","nvss","first","lotss","vlass","chandra","xmm","erosita"]
RADII={"gaia_dr3":0.10,"panstarrs1":0.10,"allwise":0.15,"twomass":0.10,"galex":0.15,"desi_legacy":0.10,"nvss":0.25,"first":0.10,"lotss":0.15,"vlass":0.10,"chandra":0.15,"xmm":0.20,"erosita":0.30}
MATCH_ARCSEC={"gaia_dr3":2.0,"panstarrs1":2.0,"allwise":3.0,"twomass":2.5,"galex":5.0,"desi_legacy":2.0,"nvss":10.0,"first":3.0,"lotss":5.0,"vlass":3.0,"chandra":5.0,"xmm":8.0,"erosita":10.0}

def load(name):
 p=GET/f"{name}.py"; s=importlib.util.spec_from_file_location("trd_"+name,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def sep_arcsec(ra1,dec1,ra2,dec2):
 r1,d1,r2,d2=map(np.radians,[ra1,dec1,ra2,dec2]); a=np.sin((d2-d1)/2)**2+np.cos(d1)*np.cos(d2)*np.sin((r2-r1)/2)**2
 return np.degrees(2*np.arcsin(np.sqrt(np.clip(a,0,1))))*3600

def query_one(mod,name,radius,t):
 last=None
 for attempt in range(5):
  try:
   d=mod.fetch(float(t.ra),float(t.dec),radius); last=None; break
  except Exception as e:
   last=e
   # MAST/other public services can throttle bursts. Retry transient failures,
   # with stronger backoff for explicit HTTP 429 responses.
   msg=repr(e); delay=(2**attempt)*(1.0 if "429" in msg else 0.5)
   if attempt<4: time.sleep(delay)
 if last is not None: return "error",None,repr(last)
 try:
  if d is None or d.empty: return "empty",None,None
  d=d.copy(); d["_sep_arcsec"]=sep_arcsec(float(t.ra),float(t.dec),pd.to_numeric(d.ra,errors="coerce").to_numpy(),pd.to_numeric(d.dec,errors="coerce").to_numpy())
  d=d[np.isfinite(d["_sep_arcsec"]) & (d["_sep_arcsec"] <= MATCH_ARCSEC[name])].sort_values("_sep_arcsec").head(1)
  if d.empty: return "empty",None,None
  d.insert(0,"benchmark_id",t.benchmark_id); d.insert(1,"truth_class",t.truth_class); d.insert(2,"truth_source",t.truth_source); d.insert(3,"truth_ra",t.ra); d.insert(4,"truth_dec",t.dec); d.insert(5,"match_threshold_arcsec",MATCH_ARCSEC[name])
  return "matched",d,None
 except Exception as e: return "error",None,repr(e)

def run_gaia(truth,out_dir):
 from astroquery.gaia import Gaia
 from astropy.table import Table
 mod=load("gaia_dr3")
 # Server-side upload join avoids both ~1000 serial cones and a giant OR clause.
 # First retrieve only source ids/positions, choose the nearest match locally,
 # then fetch the wider Gaia feature payload by source_id in bounded chunks.
 upload=truth[["benchmark_id","ra","dec"]].rename(columns={"ra":"truth_ra","dec":"truth_dec"}).copy()
 ut=Table.from_pandas(upload)
 radius_deg=MATCH_ARCSEC["gaia_dr3"]/3600.0
 q=f"""SELECT t.benchmark_id,t.truth_ra,t.truth_dec,g.source_id,g.ra,g.dec
 FROM tap_upload.truth AS t
 JOIN gaiadr3.gaia_source AS g
 ON 1=CONTAINS(POINT('ICRS',g.ra,g.dec),CIRCLE('ICRS',t.truth_ra,t.truth_dec,{radius_deg}))"""
 try:
  cand=Gaia.launch_job_async(q,upload_resource=ut,upload_table_name="truth").get_results().to_pandas()
 except Exception as e:
  print(f"[gaia_dr3] upload crossmatch ERROR {e!r}",flush=True)
  cand=pd.DataFrame()
 if cand.empty:
  out=pd.DataFrame(columns=["benchmark_id","truth_class"]); out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
  return {"catalog":"gaia_dr3","targets":len(truth),"matched":0,"empty":len(truth),"errors":1,"STAR":0,"GALAXY":0,"QSO":0}

 cand["_sep_arcsec"]=sep_arcsec(pd.to_numeric(cand["truth_ra"],errors="coerce").to_numpy(),
   pd.to_numeric(cand["truth_dec"],errors="coerce").to_numpy(),
   pd.to_numeric(cand["ra"],errors="coerce").to_numpy(),
   pd.to_numeric(cand["dec"],errors="coerce").to_numpy())
 cand=cand.sort_values(["benchmark_id","_sep_arcsec"]).drop_duplicates("benchmark_id",keep="first")
 ids=[str(int(x)) for x in pd.to_numeric(cand["source_id"],errors="coerce").dropna().astype("int64").unique()]
 select=[f"g.{c}" for c in mod.BASE]+[f"ap.{c}" for c in mod.DSC]+["vc.best_class_name","vc.best_class_score"]
 detail=[]; errors=0
 for i in range(0,len(ids),100):
  chunk=ids[i:i+100]
  dq=f"""SELECT {','.join(select)}
  FROM gaiadr3.gaia_source AS g
  LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap ON g.source_id=ap.source_id
  LEFT OUTER JOIN gaiadr3.vari_classifier_result AS vc ON g.source_id=vc.source_id
  WHERE g.source_id IN ({','.join(chunk)})"""
  got=None
  for attempt in range(4):
   try:
    got=Gaia.launch_job_async(dq).get_results().to_pandas(); break
   except Exception as e:
    if attempt==3:
     errors+=1; print(f"[gaia_dr3] detail chunk {i//100+1} ERROR {e!r}",flush=True)
    else: time.sleep(2**attempt)
  if got is not None and len(got): detail.append(got)
 allg=pd.concat(detail,ignore_index=True).drop_duplicates("source_id") if detail else pd.DataFrame()
 if allg.empty:
  out=pd.DataFrame(columns=["benchmark_id","truth_class"]); out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
  return {"catalog":"gaia_dr3","targets":len(truth),"matched":0,"empty":len(truth),"errors":max(1,errors),"STAR":0,"GALAXY":0,"QSO":0}

 allg.insert(0,"catalog",mod.CATALOG)
 allg.insert(1,"catalog_object_id",allg["source_id"].astype("Int64").astype(str))
 allg.insert(2,"object_name",allg["designation"].astype(str))
 merged=cand[["benchmark_id","source_id","_sep_arcsec"]].merge(allg,on="source_id",how="inner")
 meta=truth[["benchmark_id","truth_class","truth_source","ra","dec"]].rename(columns={"ra":"truth_ra","dec":"truth_dec"})
 out=meta.merge(merged,on="benchmark_id",how="inner")
 out.insert(5,"match_threshold_arcsec",MATCH_ARCSEC["gaia_dr3"])
 out=out.sort_values("benchmark_id")
 out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
 counts=out.truth_class.value_counts().to_dict(); ok=len(out)
 print(f"[gaia_dr3] targets={len(truth)} matched={ok} empty={len(truth)-ok} detail_errors={errors}",flush=True)
 return {"catalog":"gaia_dr3","targets":len(truth),"matched":ok,"empty":len(truth)-ok,"errors":errors,
         "STAR":counts.get("STAR",0),"GALAXY":counts.get("GALAXY",0),"QSO":counts.get("QSO",0)}

def run_catalog(name,truth,out_dir,workers):
 if name=="gaia_dr3": return run_gaia(truth,out_dir)
 mod=load(name); radius=RADII[name]; rows=[]; ok=empty=errors=done=0
 # Pan-STARRS MAST endpoint throttles aggressive parallel cone searches.
 workers=min(workers,2) if name=="panstarrs1" else workers
 with ThreadPoolExecutor(max_workers=workers) as ex:
  futs={ex.submit(query_one,mod,name,radius,t):t for _,t in truth.iterrows()}
  for f in as_completed(futs):
   t=futs[f]; status,d,err=f.result(); done+=1
   if status=="matched": rows.append(d); ok+=1
   elif status=="empty": empty+=1
   else: errors+=1; print(f"[{name}] {t.benchmark_id} ERROR {err}",flush=True)
   if done%25==0 or done==len(truth): print(f"[{name}] {done}/{len(truth)} matched={ok} empty={empty} errors={errors}",flush=True)
 out=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=["benchmark_id","truth_class"]); out=out.sort_values("benchmark_id") if len(out) else out; out.to_csv(out_dir/f"{name}_trd.csv",index=False); counts=out["truth_class"].value_counts().to_dict() if len(out) else {}
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

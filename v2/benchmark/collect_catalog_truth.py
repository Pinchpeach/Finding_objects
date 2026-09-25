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
 from astroquery.xmatch import XMatch
 from astropy.table import Table
 import astropy.units as u
 mod=load("gaia_dr3")
 # Gaia Archive can be unstable during DR4 preparation.  For benchmark
 # crossmatching use the CDS/VizieR mirror of the Gaia DR3 main-source table,
 # which supports a single bulk XMatch for all truth coordinates.
 upload=truth[["benchmark_id","ra","dec"]].rename(columns={"ra":"truth_ra","dec":"truth_dec"}).copy()
 try:
  xm=XMatch.query(cat1=Table.from_pandas(upload),cat2="vizier:I/355/gaiadr3",
                  max_distance=MATCH_ARCSEC["gaia_dr3"]*u.arcsec,
                  colRA1="truth_ra",colDec1="truth_dec").to_pandas()
 except Exception as e:
  print(f"[gaia_dr3] CDS XMatch ERROR {e!r}",flush=True)
  out=pd.DataFrame(columns=["benchmark_id","truth_class"]); out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
  return {"catalog":"gaia_dr3","targets":len(truth),"matched":0,"empty":len(truth),"errors":1,"STAR":0,"GALAXY":0,"QSO":0}
 if xm.empty:
  out=pd.DataFrame(columns=["benchmark_id","truth_class"]); out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
  return {"catalog":"gaia_dr3","targets":len(truth),"matched":0,"empty":len(truth),"errors":0,"STAR":0,"GALAXY":0,"QSO":0}

 # Normalize VizieR Gaia DR3 column names to the same schema used by the native
 # Gaia collector.  Missing optional fields remain NaN rather than being forged.
 mp={
  "Source":"source_id","RA_ICRS":"ra","DE_ICRS":"dec","e_RA_ICRS":"ra_error","e_DE_ICRS":"dec_error",
  "Plx":"parallax","e_Plx":"parallax_error","pmRA":"pmra","e_pmRA":"pmra_error","pmDE":"pmdec","e_pmDE":"pmdec_error",
  "RUWE":"ruwe","FG":"phot_g_mean_flux","e_FG":"phot_g_mean_flux_error","Gmag":"phot_g_mean_mag",
  "FBP":"phot_bp_mean_flux","e_FBP":"phot_bp_mean_flux_error","BPmag":"phot_bp_mean_mag",
  "FRP":"phot_rp_mean_flux","e_FRP":"phot_rp_mean_flux_error","RPmag":"phot_rp_mean_mag","BP-RP":"bp_rp",
  "RV":"radial_velocity","e_RV":"radial_velocity_error","Teff":"teff_gspphot","logg":"logg_gspphot"
 }
 for old,new in mp.items():
  if old in xm.columns and new not in xm.columns: xm=xm.rename(columns={old:new})
 if "source_id" not in xm.columns:
  raise KeyError(f"Gaia VizieR XMatch missing source identifier; columns={list(xm.columns)}")
 if "ra" not in xm.columns or "dec" not in xm.columns:
  raise KeyError(f"Gaia VizieR XMatch missing coordinates; columns={list(xm.columns)}")
 if "angDist" in xm.columns:
  xm["_sep_arcsec"]=pd.to_numeric(xm["angDist"],errors="coerce")
 else:
  xm["_sep_arcsec"]=sep_arcsec(pd.to_numeric(xm["truth_ra"],errors="coerce").to_numpy(),
    pd.to_numeric(xm["truth_dec"],errors="coerce").to_numpy(),
    pd.to_numeric(xm["ra"],errors="coerce").to_numpy(),pd.to_numeric(xm["dec"],errors="coerce").to_numpy())
 xm=xm[np.isfinite(pd.to_numeric(xm["_sep_arcsec"],errors="coerce"))]
 xm=xm[pd.to_numeric(xm["_sep_arcsec"],errors="coerce")<=MATCH_ARCSEC["gaia_dr3"]]
 xm=xm.sort_values(["benchmark_id","_sep_arcsec"]).drop_duplicates("benchmark_id",keep="first")
 xm.insert(0,"catalog",mod.CATALOG)
 xm.insert(1,"catalog_object_id",pd.to_numeric(xm["source_id"],errors="coerce").astype("Int64").astype(str))
 xm.insert(2,"object_name","Gaia DR3 "+xm["catalog_object_id"].astype(str))
 meta=truth[["benchmark_id","truth_class","truth_source","ra","dec"]].rename(columns={"ra":"truth_ra_meta","dec":"truth_dec_meta"})
 out=meta.merge(xm,on="benchmark_id",how="inner")
 # Keep the benchmark truth coordinates in canonical columns.
 out["truth_ra"]=out.pop("truth_ra_meta"); out["truth_dec"]=out.pop("truth_dec_meta")
 out["match_threshold_arcsec"]=MATCH_ARCSEC["gaia_dr3"]
 out=out.sort_values("benchmark_id")
 out.to_csv(out_dir/"gaia_dr3_trd.csv",index=False)
 counts=out.truth_class.value_counts().to_dict(); ok=len(out)
 print(f"[gaia_dr3] CDS targets={len(truth)} matched={ok} empty={len(truth)-ok}",flush=True)
 return {"catalog":"gaia_dr3","targets":len(truth),"matched":ok,"empty":len(truth)-ok,"errors":0,
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

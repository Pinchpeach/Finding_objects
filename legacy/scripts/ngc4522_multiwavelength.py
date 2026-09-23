"""Bulk multiwavelength census for NGC4522 field. Candidate associations only; no calibrated posterior."""
import json,pathlib,time,traceback
import numpy as np,pandas as pd
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u
IN=pathlib.Path("results/ngc4522_field10/sdss_optical_census.csv");OUT=pathlib.Path("results/ngc4522_multiwavelength");OUT.mkdir(parents=True,exist_ok=True)
RA0=188.4155;DEC0=9.1751;RADIUS=15*u.arcmin
SURVEYS={"GALEX":{"catalog":"II/335/galex_ais","radius":5.0,"fwhm":5.0},"2MASS":{"catalog":"II/246/out","radius":5.0,"fwhm":2.5},"AllWISE":{"catalog":"II/328/allwise","radius":8.0,"fwhm":6.1},"NVSS":{"catalog":"VIII/65/nvss","radius":60.0,"fwhm":45.0},"FIRST":{"catalog":"VIII/92/first14","radius":15.0,"fwhm":5.0},"XMM":{"catalog":"IX/65/xmm4d13s","radius":20.0,"fwhm":6.0}}
def state(**kw):
 p=OUT/"checkpoint.json";d={}
 if p.exists():
  try:d=json.load(open(p))
  except:pass
 d.update(kw);json.dump(d,open(p,"w"),indent=2,default=str)
def bulk(cfg):
 v=Vizier(columns=["*"],row_limit=-1);err=None
 for k in range(3):
  try:
   t=v.query_region(SkyCoord(RA0*u.deg,DEC0*u.deg),radius=RADIUS,catalog=cfg["catalog"]);return pd.DataFrame() if not t else t[0].to_pandas()
  except Exception as e:err=e;time.sleep(3*(k+1))
 raise err
def coords(df):
 cols={str(c).lower():c for c in df.columns}
 for a,b in [("_raj2000","_dej2000"),("raj2000","dej2000"),("raicrs","deicrs"),("ra","dec")]:
  if a in cols and b in cols:return cols[a],cols[b]
 raise ValueError(f"coordinate columns not found: {list(df.columns)[:40]}")
def main():
 base=pd.read_csv(IN);bc=SkyCoord(base.ra.to_numpy()*u.deg,base.dec.to_numpy()*u.deg);allrows=[];summary={}
 for name,cfg in SURVEYS.items():
  try:
   d=bulk(cfg);d.to_csv(OUT/f"{name}_field.csv",index=False)
   if len(d)==0:summary[name]={"query_status":"ok","field_rows":0,"matched_objects":0};state(**{name:summary[name]});continue
   a,b=coords(d);ra=pd.to_numeric(d[a],errors="coerce");de=pd.to_numeric(d[b],errors="coerce");valid=ra.notna()&de.notna();d=d.loc[valid].reset_index(drop=True);dc=SkyCoord(ra[valid].to_numpy()*u.deg,de[valid].to_numpy()*u.deg)
   idx,sep,_=bc.match_to_catalog_sky(dc);ok=sep.arcsec<=cfg["radius"]
   for i in np.where(ok)[0]:allrows.append({"objid":str(base.iloc[i].objid),"survey":name,"catalog":cfg["catalog"],"separation_arcsec":float(sep.arcsec[i]),"search_radius_arcsec":cfg["radius"],"survey_fwhm_arcsec":cfg["fwhm"],"association_status":"CANDIDATE_UNCALIBRATED","catalog_row":int(idx[i])})
   summary[name]={"query_status":"ok","field_rows":len(d),"matched_objects":int(ok.sum()),"search_radius_arcsec":cfg["radius"],"fwhm_arcsec":cfg["fwhm"],"note":"FWHM requires official provenance/calibration before probability use."};state(**{name:summary[name]})
  except Exception as e:summary[name]={"query_status":"failed","error":repr(e)};state(**{name:summary[name]})
 pd.DataFrame(allrows).to_csv(OUT/"candidate_associations.csv",index=False);json.dump(summary,open(OUT/"summary.json","w"),indent=2);state(stage="complete");print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:state(stage="failed",error=repr(e),traceback=traceback.format_exc());raise

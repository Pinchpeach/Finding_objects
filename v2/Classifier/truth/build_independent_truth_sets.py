#!/usr/bin/env python3
"""Build larger per-axis truth samples with explicit evidence-exclusion metadata.

These truth sets are for evaluation/calibration only.  If a truth catalogue is
also available as production evidence, `excluded_evidence_catalog` records that
it must be masked during evaluation to prevent leakage.
"""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
import pandas as pd


def _pick(df,names):
 low={str(c).lower():c for c in df.columns}
 for n in names:
  if n in df.columns:return n
  if n.lower() in low:return low[n.lower()]
 return None

def _vizier(catalog,row_limit=1000,**constraints):
 from astroquery.vizier import Vizier
 last=None
 for attempt in range(3):
  try:
   v=Vizier(columns=["**","_RAJ2000","_DEJ2000"],row_limit=row_limit,timeout=180)
   tabs=v.query_constraints(catalog=catalog,**constraints) if constraints else v.get_catalogs(catalog)
   return tabs[0].to_pandas() if tabs else pd.DataFrame()
  except Exception as exc:
   last=exc
   if attempt<2:time.sleep(2**attempt)
 raise last

def _coords(df):
 ra=_pick(df,["RAJ2000","RA_ICRS","_RA","_RAJ2000"]);de=_pick(df,["DEJ2000","DE_ICRS","_DE","_DEJ2000"])
 if ra is None or de is None:return pd.Series(pd.NA,index=df.index),pd.Series(pd.NA,index=df.index)
 r=pd.to_numeric(df[ra],errors="coerce");d=pd.to_numeric(df[de],errors="coerce")
 if r.notna().all() and d.notna().all():return r,d
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 for i in df.index[r.isna()|d.isna()]:
  try:
   rs=str(df.at[i,ra]);ds=str(df.at[i,de]);c=SkyCoord(rs,ds,unit=(u.hourangle,u.deg));r.at[i]=c.ra.deg;d.at[i]=c.dec.deg
  except Exception:pass
 return r,d

def red_giants(limit):
 # Vrard+ 2025 table4: EV=1 certain RGB, EV=2 candidate AGB.
 df=_vizier("J/A+A/697/A165/table4",row_limit=max(limit*3,1000))
 if df.empty:return df
 ev=_pick(df,["EV"]);idc=_pick(df,["KIC"]);ra,dec=_coords(df)
 out=pd.DataFrame({"truth_id":df[idc].astype("string") if idc else df.index.astype(str),"ra":ra,"dec":dec,"truth_axis":"physical","truth_class":df[ev].map({1:"RGB",2:"AGB"})})
 out=out.dropna(subset=["truth_class","ra","dec"]);out["truth_source"]="Vrard+2025 Kepler RGB/AGB";out["excluded_evidence_catalog"]="";return out.groupby("truth_class",group_keys=False).head(limit)

def variables(limit):
 specs=[("RRAB","RR_LYRAE"),("RRC","RR_LYRAE"),("DCEP","CEPHEID"),("DCEPS","CEPHEID"),("M","MIRA"),("SR","LPV")];parts=[]
 for typ,label in specs:
  try:df=_vizier("II/366/catv2021",row_limit=limit,Type=typ)
  except Exception:continue
  if df.empty:continue
  idc=_pick(df,["ASASSN-V","ID"]);ra,dec=_coords(df);p=_pick(df,["Prob"])
  part=pd.DataFrame({"truth_id":df[idc].astype("string"),"ra":ra,"dec":dec,"truth_axis":"variability","truth_class":label,"truth_quality":pd.to_numeric(df[p],errors="coerce") if p else pd.NA})
  part["truth_source"]="ASAS-SN Variable Stars II/366";part["excluded_evidence_catalog"]="";parts.append(part)
 return pd.concat(parts,ignore_index=True).dropna(subset=["ra","dec"]) if parts else pd.DataFrame()

def pulsars(limit):
 df=_vizier("B/psr/psr",row_limit=limit)
 if df.empty:return df
 idc=_pick(df,["PSRJ","Name"]);ra,dec=_coords(df);out=pd.DataFrame({"truth_id":df[idc].astype("string"),"ra":ra,"dec":dec,"truth_axis":"compact","truth_class":"PULSAR"})
 out["truth_source"]="ATNF B/psr";out["excluded_evidence_catalog"]="ATNF Pulsar Catalog";return out.dropna(subset=["ra","dec"])

def pns(limit):
 df=_vizier("V/84/main",row_limit=limit)
 if df.empty:return df
 idc=_pick(df,["PNG"]);ra,dec=_coords(df);out=pd.DataFrame({"truth_id":df[idc].astype("string"),"ra":ra,"dec":dec,"truth_axis":"phenomenon","truth_class":"PN"})
 out["truth_source"]="Acker V/84 PN catalogue";out["excluded_evidence_catalog"]="Acker PN Spectroscopy";return out.dropna(subset=["ra","dec"])

def supernovae(limit):
 df=_vizier("B/sn/sncat",row_limit=max(limit*5,1250))
 if df.empty:return df
 idc=_pick(df,["SN"]);typec=_pick(df,["Type"]);ra,dec=_coords(df);out=pd.DataFrame({"truth_id":df[idc].astype("string"),"ra":ra,"dec":dec,"truth_axis":"phenomenon","truth_class":"SN","truth_subtype":df[typec].astype("string") if typec else pd.NA})
 out["truth_source"]="Asiago B/sn";out["excluded_evidence_catalog"]="Asiago Supernova Catalog";return out.dropna(subset=["ra","dec"]).head(limit)

def build(out_dir:Path,limit:int):
 out_dir.mkdir(parents=True,exist_ok=True);builders={"rgb_agb":red_giants,"variables":variables,"pulsars":pulsars,"pn":pns,"sn":supernovae};summary=[]
 for name,fn in builders.items():
  try:df=fn(limit);status="ok"
  except Exception as exc:df=pd.DataFrame();status=f"error:{type(exc).__name__}:{exc}"
  df.to_csv(out_dir/f"{name}_truth.csv",index=False);summary.append({"set":name,"rows":len(df),"status":status,"classes":"|".join(sorted(df.get("truth_class",pd.Series(dtype=str)).dropna().astype(str).unique()))})
 pd.DataFrame(summary).to_csv(out_dir/"truth_build_summary.csv",index=False)
 (out_dir/"README.md").write_text("# Independent per-axis truth sets\n\nGenerated truth sets carry `excluded_evidence_catalog` so evaluation code can mask same-catalog evidence and avoid circular validation. Candidate AGB labels from Vrard+2025 remain candidates and must not be described as spectroscopic certainty.\n",encoding="utf-8")
 return summary

def main():
 p=argparse.ArgumentParser();p.add_argument("--out-dir",type=Path,default=Path(__file__).resolve().parent/"generated");p.add_argument("--limit",type=int,default=250);a=p.parse_args();print(json.dumps(build(a.out_dir,a.limit),indent=2))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Build an external LAMOST spectroscopy truth set for STAR WD validation.

Positive truth: published LAMOST DR5 white-dwarf catalogue (Guo et al. 2022).
Negative truth: general LAMOST DR5 spectra with ordinary O/B/A/F/G/K/M subclass.
Objects spatially overlapping the SDSS training/validation truth are excluded.
"""
from __future__ import annotations
import argparse, re
from pathlib import Path
import numpy as np
import pandas as pd

WD_CAT="J/MNRAS/509/2674/table6"
LAMOST_CAT="V/164/dr5"

def _norm_cols(d):
    d=d.copy(); d.columns=[str(c).strip() for c in d.columns]; return d

def _coord_cols(d):
    ra=next((c for c in ("RAJ2000","RAdeg","RA_ICRS","RA") if c in d.columns),None)
    dec=next((c for c in ("DEJ2000","DEdeg","DE_ICRS","Dec","DEC") if c in d.columns),None)
    if not ra or not dec: raise KeyError(f"coordinate columns not found: {list(d.columns)}")
    return ra,dec

def _exclude_sdss_overlap(d,sdss,max_sep_arcsec=2.0):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    if d.empty or sdss.empty: return d
    c=SkyCoord(d.ra.to_numpy()*u.deg,d.dec.to_numpy()*u.deg)
    s=SkyCoord(sdss.ra.to_numpy()*u.deg,sdss.dec.to_numpy()*u.deg)
    _,sep,_=c.match_to_catalog_sky(s)
    keep=sep.arcsec>max_sep_arcsec
    return d.loc[keep].copy()

def fetch_wd(n):
    from astroquery.vizier import Vizier
    v=Vizier(columns=["**"],row_limit=-1)
    tabs=v.get_catalogs(WD_CAT)
    if not tabs: raise RuntimeError("LAMOST WD catalogue unavailable")
    d=_norm_cols(tabs[0].to_pandas())
    ra,dec=_coord_cols(d)
    out=pd.DataFrame({
      "external_id":d["ObsID"].astype(str) if "ObsID" in d else np.arange(len(d)).astype(str),
      "ra":pd.to_numeric(d[ra],errors="coerce"),
      "dec":pd.to_numeric(d[dec],errors="coerce"),
      "lamost_subclass":d["SpType"].astype(str) if "SpType" in d else "DA",
      "star_truth_class":"WHITE_DWARF",
      "truth_source":"LAMOST_DR5_GUO2022_WD",
      "truth_quality":"PUBLISHED_DA_WHITE_DWARF_SAMPLE",
    }).dropna(subset=["ra","dec"])
    return out.drop_duplicates(["ra","dec"]).head(n)

def fetch_normal(n):
    from astroquery.vizier import Vizier
    # Query subclasses server-side rather than downloading the multi-million-row
    # LAMOST DR5 table. Sample across ordinary MK leading classes.
    pieces=[]
    families=["A","F","G","K","M","B","O"]
    per=max(25,int(np.ceil(n/len(families))))
    for fam in families:
        v=Vizier(columns=["**"],row_limit=per*3)
        try:
            tabs=v.query_constraints(catalog=LAMOST_CAT,SubClass=f"{fam}*")
        except Exception as e:
            print(f"[LAMOST] subclass {fam} query failed: {e!r}",flush=True)
            continue
        if not tabs: continue
        d=_norm_cols(tabs[0].to_pandas())
        ra,dec=_coord_cols(d)
        sub_col=next((x for x in ("SubClass","subclass","SUBCLASS") if x in d.columns),None)
        if not sub_col: continue
        sub=d[sub_col].fillna("").astype(str).str.upper().str.strip()
        ordinary=sub.str.match(r"^[OBAFGKM][0-9]?") & ~sub.str.contains(r"WD|SD|CV|D[ABCOQZ]",regex=True)
        q=d.loc[ordinary].copy(); sq=sub.loc[ordinary]
        piece=pd.DataFrame({
          "external_id":q["ObsID"].astype(str) if "ObsID" in q else [f"{fam}_{i}" for i in range(len(q))],
          "ra":pd.to_numeric(q[ra],errors="coerce"),
          "dec":pd.to_numeric(q[dec],errors="coerce"),
          "lamost_subclass":sq.to_numpy(),
          "star_truth_class":"NORMAL_STAR",
          "truth_source":"LAMOST_DR5_GENERAL_SPECTROSCOPY",
          "truth_quality":"LAMOST_DR5_PIPELINE_SUBCLASS",
        }).dropna(subset=["ra","dec"]).head(per)
        pieces.append(piece)
    if not pieces: return pd.DataFrame()
    out=pd.concat(pieces,ignore_index=True).drop_duplicates(["ra","dec"])
    if len(out)>n:
        idx=np.linspace(0,len(out)-1,n,dtype=int)
        out=out.iloc[idx]
    return out

def run(sdss_truth:Path,out:Path,total=1000):
    sdss=pd.read_csv(sdss_truth)[["ra","dec"]].dropna()
    n=total//2
    wd=_exclude_sdss_overlap(fetch_wd(max(n*2,n+100)),sdss).head(n)
    normal=_exclude_sdss_overlap(fetch_normal(max(n*2,n+100)),sdss).head(n)
    if len(wd)<200 or len(normal)<200:
        raise RuntimeError(f"insufficient independent LAMOST truth WD={len(wd)} normal={len(normal)}")
    d=pd.concat([wd,normal],ignore_index=True)
    d["benchmark_id"]=[f"LAMTRD{i+1:06d}" for i in range(len(d))]
    out.parent.mkdir(parents=True,exist_ok=True); d.to_csv(out,index=False)
    print(d.star_truth_class.value_counts().to_string())
    print(f"[OK] independent external truth rows={len(d)} -> {out}")
    return out

def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser()
    p.add_argument("--sdss-truth",type=Path,default=root/"star_truth.csv")
    p.add_argument("--out",type=Path,default=root/"lamost_star_external_truth.csv")
    p.add_argument("--total",type=int,default=1000)
    a=p.parse_args(); run(a.sdss_truth,a.out,a.total)
if __name__=="__main__": main()

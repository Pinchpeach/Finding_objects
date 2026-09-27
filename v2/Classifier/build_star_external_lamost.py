#!/usr/bin/env python3
"""Build an external LAMOST spectroscopy truth set for STAR WD validation.

Positive truth: Guo et al. LAMOST DR3/4/5 white-dwarf catalogue
                (VizieR J/MNRAS/509/2674/table3).
Negative truth: LAMOST DR5 general catalogue spectroscopic STAR entries
                with ordinary O/B/A/F/G/K/M subclasses (VizieR V/164/dr5).

Objects within 2 arcsec of the SDSS training truth are removed so that the
external test is not contaminated by identical sky sources used for training.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def _pick(df,names):
    for n in names:
        if n in df.columns:
            return n
    return None

def _coords(df):
    ra=_pick(df,["RAJ2000","RA_ICRS","RAdeg","ra","RA"])
    dec=_pick(df,["DEJ2000","DE_ICRS","DEdeg","dec","DEC","DE"])
    if not ra or not dec:
        raise KeyError(f"coordinate columns not found: {list(df.columns)}")
    return pd.to_numeric(df[ra],errors="coerce"),pd.to_numeric(df[dec],errors="coerce")

def _remove_sdss_overlap(d,sdss,max_sep_arcsec=2.0):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    a=SkyCoord(d.ra.to_numpy()*u.deg,d.dec.to_numpy()*u.deg)
    b=SkyCoord(sdss.ra.to_numpy()*u.deg,sdss.dec.to_numpy()*u.deg)
    idx,sep,_=a.match_to_catalog_sky(b)
    keep=sep.arcsec>max_sep_arcsec
    return d.loc[keep].copy(),int((~keep).sum())

def run(sdss_truth:Path,out:Path,total=1000):
    from astroquery.vizier import Vizier

    sdss=pd.read_csv(sdss_truth)
    sdss=sdss[pd.to_numeric(sdss.ra,errors="coerce").notna() & pd.to_numeric(sdss.dec,errors="coerce").notna()].copy()

    # Curated LAMOST WD catalogue.
    v=Vizier(columns=["**"],row_limit=-1)
    tabs=v.get_catalogs("J/MNRAS/509/2674/table3")
    if not tabs:
        raise RuntimeError("LAMOST WD catalogue unavailable")
    wd=tabs[0].to_pandas()
    wr,wdc=_coords(wd)
    wdout=pd.DataFrame({
        "external_id":wd[_pick(wd,["ObsID","Name","GroupID"])].astype(str) if _pick(wd,["ObsID","Name","GroupID"]) else np.arange(len(wd)).astype(str),
        "ra":wr,"dec":wdc,
        "star_truth_class":"WHITE_DWARF",
        "truth_source":"LAMOST_DR5_GUO_WD_CATALOG",
    }).dropna(subset=["ra","dec"]).drop_duplicates(["ra","dec"])

    # General LAMOST spectroscopic stars. Limit query size because only a
    # balanced negative sample is needed.
    vg=Vizier(columns=["**"],column_filters={"Class":"STAR"},row_limit=max(5000,total*8))
    gtabs=vg.get_catalogs("V/164/dr5")
    if not gtabs:
        raise RuntimeError("LAMOST DR5 general catalogue unavailable")
    g=gtabs[0].to_pandas()
    class_col=_pick(g,["Class","class"])
    sub_col=_pick(g,["SubClass","Subclass","subclass"])
    if class_col:
        g=g[g[class_col].astype(str).str.upper().eq("STAR")].copy()
    if not sub_col:
        raise KeyError(f"LAMOST subclass column unavailable: {list(g.columns)}")
    sub=g[sub_col].fillna("").astype(str).str.upper().str.strip()
    normal=sub.str.match(r"^[OBAFGKM]")
    # Explicitly reject WD-like, carbon/emission/exotic strings from negatives.
    normal &= ~sub.str.contains("WD|WHITE|CV|CARBON|EMISSION",regex=True)
    g=g[normal].copy()
    gr,gdc=_coords(g)
    gout=pd.DataFrame({
        "external_id":g[_pick(g,["ObsID","obsid","Designation"])].astype(str) if _pick(g,["ObsID","obsid","Designation"]) else np.arange(len(g)).astype(str),
        "ra":gr,"dec":gdc,
        "star_truth_class":"NORMAL_STAR",
        "truth_source":"LAMOST_DR5_GENERAL_SPECTROSCOPY",
        "lamost_subclass":g[sub_col].astype(str).to_numpy(),
    }).dropna(subset=["ra","dec"]).drop_duplicates(["ra","dec"])

    wdout,wd_overlap=_remove_sdss_overlap(wdout,sdss)
    gout,g_overlap=_remove_sdss_overlap(gout,sdss)

    n=total//2
    # Deterministic spatially diversified sampling: sort by RA then take evenly
    # spaced indices across the available catalogue rather than first-N rows.
    def spread(d,n):
        d=d.sort_values(["ra","dec"]).reset_index(drop=True)
        if len(d)<=n: return d
        idx=np.linspace(0,len(d)-1,n,dtype=int)
        return d.iloc[idx].copy()
    wdout=spread(wdout,n)
    gout=spread(gout,n)
    ext=pd.concat([wdout,gout],ignore_index=True)
    if len(wdout)<200 or len(gout)<200:
        raise RuntimeError(f"insufficient independent LAMOST truth WD={len(wdout)} normal={len(gout)}")
    ext["benchmark_id"]=[f"LAMSTAR{i+1:06d}" for i in range(len(ext))]
    ext["truth_quality"]="LAMOST_SPECTROSCOPIC_EXTERNAL"
    out.parent.mkdir(parents=True,exist_ok=True)
    ext.to_csv(out,index=False)
    print(f"[OK] external rows={len(ext)} WD={len(wdout)} normal={len(gout)}")
    print(f"[overlap removed] WD={wd_overlap} normal={g_overlap}")
    print(ext.star_truth_class.value_counts().to_string())
    return out

def main():
    p=argparse.ArgumentParser()
    root=Path(__file__).resolve().parent
    p.add_argument("--sdss-truth",type=Path,default=root/"star_truth.csv")
    p.add_argument("--out",type=Path,default=root/"star_external_lamost_truth.csv")
    p.add_argument("--total",type=int,default=1000)
    a=p.parse_args(); run(a.sdss_truth,a.out,a.total)

if __name__=="__main__": main()

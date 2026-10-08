#!/usr/bin/env python3
"""Bulk-crossmatch STAR-branch spectroscopy truth to Gaia DR3 via CDS XMatch."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def run(truth_path:Path,out:Path,max_sep_arcsec:float=2.0,min_matches:int=500):
    from astroquery.xmatch import XMatch
    from astropy.table import Table
    import astropy.units as u

    truth=pd.read_csv(truth_path)
    req={"benchmark_id","ra","dec","star_truth_class"}
    if not req.issubset(truth.columns):
        raise KeyError(f"truth missing {sorted(req-set(truth.columns))}")
    upload=truth[["benchmark_id","ra","dec"]].rename(columns={"ra":"truth_ra","dec":"truth_dec"})
    xm=XMatch.query(cat1=Table.from_pandas(upload),cat2="vizier:I/355/gaiadr3",
                    max_distance=max_sep_arcsec*u.arcsec,
                    colRA1="truth_ra",colDec1="truth_dec").to_pandas()
    mp={
      "Source":"source_id","RA_ICRS":"ra","DE_ICRS":"dec","RAdeg":"ra","DEdeg":"dec",
      "Plx":"parallax","e_Plx":"parallax_error","pmRA":"pmra","e_pmRA":"pmra_error",
      "pmDE":"pmdec","e_pmDE":"pmdec_error","RUWE":"ruwe",
      "Gmag":"phot_g_mean_mag","BPmag":"phot_bp_mean_mag","RPmag":"phot_rp_mean_mag",
      "BP-RP":"bp_rp","FG":"phot_g_mean_flux","e_FG":"phot_g_mean_flux_error",
      "FBP":"phot_bp_mean_flux","e_FBP":"phot_bp_mean_flux_error",
      "FRP":"phot_rp_mean_flux","e_FRP":"phot_rp_mean_flux_error",
      "E(BP/RP)":"phot_bp_rp_excess_factor",
    }
    for old,new in mp.items():
        if old in xm.columns and new not in xm.columns:
            xm=xm.rename(columns={old:new})
    if "angDist" in xm.columns:
        xm["_sep_arcsec"]=pd.to_numeric(xm["angDist"],errors="coerce")
    else:
        def sep(ra1,dec1,ra2,dec2):
            r1,d1,r2,d2=map(np.radians,[ra1,dec1,ra2,dec2])
            a=np.sin((d2-d1)/2)**2+np.cos(d1)*np.cos(d2)*np.sin((r2-r1)/2)**2
            return np.degrees(2*np.arcsin(np.sqrt(np.clip(a,0,1))))*3600
        xm["_sep_arcsec"]=sep(pd.to_numeric(xm.truth_ra,errors="coerce"),
                              pd.to_numeric(xm.truth_dec,errors="coerce"),
                              pd.to_numeric(xm.ra,errors="coerce"),
                              pd.to_numeric(xm.dec,errors="coerce"))
    xm=xm[pd.to_numeric(xm["_sep_arcsec"],errors="coerce")<=max_sep_arcsec]
    xm=xm.sort_values(["benchmark_id","_sep_arcsec"]).drop_duplicates("benchmark_id")
    meta=truth[[c for c in ("benchmark_id","star_truth_class","truth_source","truth_quality","origin_class") if c in truth.columns]]
    outdf=meta.merge(xm,on="benchmark_id",how="inner")
    out.parent.mkdir(parents=True,exist_ok=True); outdf.to_csv(out,index=False)
    cov=len(outdf)/len(truth)
    print(f"[OK] truth={len(truth)} Gaia matched={len(outdf)} coverage={cov:.4f} -> {out}")
    print(outdf.star_truth_class.value_counts().to_string())
    if len(outdf)<min_matches:
        raise RuntimeError(f"Gaia coverage too low: {len(outdf)}/{len(truth)}; min_matches={min_matches}")
    return out

def main():
    p=argparse.ArgumentParser()
    root=Path(__file__).resolve().parent
    p.add_argument("--truth",type=Path,default=root/"star_truth.csv")
    p.add_argument("--out",type=Path,default=root/"star_gaia_features.csv")
    p.add_argument("--min-matches",type=int,default=500)
    a=p.parse_args(); run(a.truth,a.out,min_matches=a.min_matches)
if __name__=="__main__": main()

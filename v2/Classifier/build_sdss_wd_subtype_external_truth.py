#!/usr/bin/env python3
"""Build an independent SDSS DR14 DA/DB truth set for Gaia-XP validation.

Source: Kepler et al. (2019), VizieR J/MNRAS/486/2169/table2.
Only exact pure DA and DB labels with g-band spectral S/N >= 10 are used.
Objects within 2 arcsec of the LAMOST DA/DB training truth are removed.
"""
from __future__ import annotations
import argparse, re, time
from pathlib import Path
import numpy as np
import pandas as pd

CAT="J/MNRAS/486/2169/table2"
_TABLE_CACHE=None

def parse_sdss_name(v):
    s=str(v).strip().upper().replace("SDSS","").replace("J","").replace(" ","")
    m=re.match(r"^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([+-])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)$",s)
    if not m:
        return np.nan,np.nan
    hh,mm,ss,sg,dd,dm,ds=m.groups()
    ra=15.0*(float(hh)+float(mm)/60.0+float(ss)/3600.0)
    dec=float(dd)+float(dm)/60.0+float(ds)/3600.0
    if sg=="-": dec=-dec
    return ra,dec

def query_type(cls):
    global _TABLE_CACHE
    if _TABLE_CACHE is None:
        from astroquery.vizier import Vizier
        last=None
        for server in ("vizier.cds.unistra.fr","vizier.cfa.harvard.edu","vizier.nao.ac.jp"):
            for attempt in range(3):
                try:
                    q=Vizier(columns=["**"],row_limit=-1)
                    q.VIZIER_SERVER=server
                    tabs=q.get_catalogs(CAT)
                    if tabs:
                        d=tabs[0].to_pandas()
                        d.columns=[str(c).strip() for c in d.columns]
                        _TABLE_CACHE=d
                        print(f"[VizieR] loaded SDSS DR14 WD table rows={len(d)} server={server}",flush=True)
                        break
                except Exception as e:
                    last=e
                    print(f"[VizieR] table server={server} attempt={attempt+1} failed: {e!r}",flush=True)
                    time.sleep(2**attempt)
            if _TABLE_CACHE is not None:
                break
        if _TABLE_CACHE is None:
            raise RuntimeError(f"SDSS DR14 WD table unavailable: {last!r}")
    return _TABLE_CACHE.copy()

def remove_lamost_overlap(d,lamost_truth,max_sep_arcsec=2.0):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    l=pd.read_csv(lamost_truth)
    if d.empty or l.empty: return d
    a=SkyCoord(d.ra.to_numpy()*u.deg,d.dec.to_numpy()*u.deg)
    b=SkyCoord(pd.to_numeric(l.ra,errors="coerce").to_numpy()*u.deg,
               pd.to_numeric(l.dec,errors="coerce").to_numpy()*u.deg)
    _,sep,_=a.match_to_catalog_sky(b)
    keep=sep.arcsec>max_sep_arcsec
    print(f"[overlap] removed={(~keep).sum()} SDSS rows within {max_sep_arcsec} arcsec of LAMOST subtype truth")
    return d.loc[keep].reset_index(drop=True)

def build_one(cls,per_class,min_sn):
    d=query_type(cls)
    ncol=next((c for c in ("Name","SDSS","name") if c in d.columns),None)
    tcol=next((c for c in ("Type","type") if c in d.columns),None)
    scol=next((c for c in ("S/Ng","SNg","SN","S/N") if c in d.columns),None)
    if not ncol or not tcol:
        raise KeyError(f"missing Name/Type columns: {list(d.columns)}")
    typ=d[tcol].fillna("").astype(str).str.upper().str.strip()
    q=d.loc[typ.eq(cls)].copy()
    if scol:
        sn=pd.to_numeric(q[scol],errors="coerce")
        q=q.loc[sn>=min_sn].copy()
    coords=q[ncol].map(parse_sdss_name)
    q["ra"]=[x[0] for x in coords]; q["dec"]=[x[1] for x in coords]
    q=q[np.isfinite(q.ra)&np.isfinite(q.dec)].copy()
    q["external_id"]=q[ncol].astype(str)
    q["wd_subtype"]=cls
    q["star_truth_class"]=cls
    q["truth_source"]="SDSS_DR14_KEPLER2019_VISUAL_WD_TYPE"
    q["truth_quality"]=f"PURE_{cls}_SNG_GE_{min_sn:g}"
    q=q.drop_duplicates("external_id").sort_values("external_id")
    if len(q)>per_class*3:
        # deterministic spread across catalogue ordering before overlap removal
        idx=np.linspace(0,len(q)-1,per_class*3,dtype=int)
        q=q.iloc[idx]
    return q

def run(out:Path,lamost_truth:Path,per_class=200,min_sn=10.0):
    parts=[]
    for cls in ("DA","DB"):
        q=build_one(cls,per_class,min_sn)
        q=remove_lamost_overlap(q,lamost_truth)
        q=q.head(per_class)
        if len(q)<100:
            raise RuntimeError(f"insufficient independent {cls}: {len(q)}")
        parts.append(q)
    n=min(len(x) for x in parts)
    parts=[x.head(n) for x in parts]
    d=pd.concat(parts,ignore_index=True)
    d["benchmark_id"]=[f"SDSSWDX{i+1:05d}" for i in range(len(d))]
    d=d[["external_id","ra","dec","wd_subtype","star_truth_class","benchmark_id","truth_source","truth_quality"]]
    out.parent.mkdir(parents=True,exist_ok=True); d.to_csv(out,index=False)
    print(d.star_truth_class.value_counts().to_string())
    print(f"[OK] independent SDSS DA/DB truth rows={len(d)} per_class={n} -> {out}")
    return out

def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=root/"sdss_wd_subtype_external_truth.csv")
    p.add_argument("--lamost-truth",type=Path,default=root/"wd_subtype_truth.csv")
    p.add_argument("--per-class",type=int,default=200)
    p.add_argument("--min-sn",type=float,default=10.0)
    a=p.parse_args(); run(a.out,a.lamost_truth,a.per_class,a.min_sn)
if __name__=="__main__": main()

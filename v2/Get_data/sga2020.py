"""Siena Galaxy Atlas 2020 (Moustakas et al. 2023, ApJS 269, 3; VizieR J/ApJS/269/3).

Large-galaxy ellipses (D26 isophotal diameter, position angle, axis ratio)
from DESI Legacy Surveys imaging.  Survey catalogs often shred such galaxies
into many detections (HII regions, spiral arms); Stage 2 uses these ellipses
to flag detections that lie inside a large galaxy.  The cone is widened by
``MAX_EXTRA_ARCMIN`` so galaxies centred outside the field but overlapping it
are returned too.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, numeric, pick

CATALOG="SGA-2020"
VIZIER_CATALOG="J/ApJS/269/3"
MAX_EXTRA_ARCMIN=10.0

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    centre=SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs")
    tabs=Vizier(columns=["**"],row_limit=-1).query_region(
        centre,radius=(float(radius_arcmin)+MAX_EXTRA_ARCMIN)*u.arcmin,catalog=VIZIER_CATALOG)
    cols=["catalog","catalog_object_id","object_name","ra","dec","sga_d26_arcmin","sga_pa_deg","sga_ba"]
    if not tabs: return pd.DataFrame(columns=cols)
    df=tabs[0].to_pandas()
    if df.empty: return pd.DataFrame(columns=cols)
    ra_v,dec_v=coordinates(df,["RAdeg","RA_ICRS","RAJ2000","_RAJ2000","RA"],["DEdeg","DE_ICRS","DEJ2000","_DEJ2000","DE"])
    idc=pick(df,["SGA","SGA_ID","SGA-ID","ID"]); namec=pick(df,["Name","GALAXY","Gal"])
    d26=pick(df,["D26","Diam26"]); pa=pick(df,["PA","PAdeg"]); ba=pick(df,["b/a","BA","ba"])
    if d26 is None: raise KeyError(f"SGA D26 column missing; got {list(df.columns)}")
    ids=df[idc].astype("string") if idc else df[namec].astype("string")
    out=pd.DataFrame({"catalog":CATALOG,"catalog_object_id":ids,
        "object_name":df[namec].astype("string") if namec else "SGA "+ids,
        "ra":ra_v,"dec":dec_v,
        "sga_d26_arcmin":numeric(df[d26]),
        "sga_pa_deg":numeric(df[pa]) if pa else pd.NA,
        "sga_ba":numeric(df[ba]) if ba else pd.NA})
    out=add_standard_metadata(out,radius_arcmin=radius_arcmin,poserr_arcsec=1.0)
    return out.dropna(subset=["ra","dec","sga_d26_arcmin"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    if not {"catalog","catalog_object_id","object_name","ra","dec"}.issubset(df.columns): raise ValueError("invalid SGA output")
    Path(path).parent.mkdir(parents=True,exist_ok=True); df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

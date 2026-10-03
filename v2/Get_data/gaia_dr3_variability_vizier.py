"""Lightweight Gaia DR3 variability collector for large independent validation.

Reads the official Gaia DR3 variability classification table through VizieR.
It preserves the production column names/semantics while avoiding multiple TAP
round-trips per truth object. This module is validation infrastructure, not a
different evidence source.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick,coordinates,add_standard_metadata

CATALOG="Gaia DR3"
TABLE="I/358/vclassre"

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    tabs=Vizier(columns=["Source","Class","ClassSc","RA_ICRS","DE_ICRS"],row_limit=-1).query_region(
        SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs"),
        radius=float(radius_arcmin)*u.arcmin,catalog=TABLE)
    if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","best_class_name","best_class_score"])
    df=tabs[0].to_pandas()
    if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","best_class_name","best_class_score"])
    sid=pick(df,["Source"]); cl=pick(df,["Class"]); sc=pick(df,["ClassSc"])
    rav,dev=coordinates(df,["RA_ICRS","RAJ2000","_RAJ2000"],["DE_ICRS","DEJ2000","_DEJ2000"])
    out=pd.DataFrame({
        "catalog":CATALOG,
        "catalog_object_id":df[sid].astype("string") if sid else df.index.astype(str),
        "object_name":("Gaia DR3 "+df[sid].astype("string")) if sid else ("Gaia DR3 "+df.index.astype(str)),
        "ra":rav,"dec":dev,
        "best_class_name":df[cl].astype("string") if cl else pd.NA,
        "best_class_score":pd.to_numeric(df[sc],errors="coerce") if sc else pd.NA,
    })
    out=add_standard_metadata(out,radius_arcmin=radius_arcmin,ref_epoch=2016.0,poserr_arcsec=0.1,psf_fwhm_arcsec=0.18)
    return out.dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""Asiago Supernova Catalogue (B/sn) collector for historical transient coverage.

The VizieR snapshot contains SNe through 2017, complementing the 2018-2020
ASAS-SN bright-SN catalogue.  This is independent event-catalog evidence and is
kept separate from persistent host-galaxy detections.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick,coordinates,add_standard_metadata

CATALOG="Asiago Supernova Catalog"
VIZIER_CATALOG="B/sn/sncat"

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    tabs=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs"),radius=float(radius_arcmin)*u.arcmin,catalog=VIZIER_CATALOG)
    if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","sn_subtype","entity_kind"])
    df=tabs[0].to_pandas()
    if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","sn_subtype","entity_kind"])
    idc=pick(df,["SN","Name"]); typec=pick(df,["Type","SNType"]); disc=pick(df,["Disc","Discoverer"])
    if idc is None:raise KeyError(f"Asiago identifier missing; got {list(df.columns)}")
    raval,decval=coordinates(df,["RAJ2000","RA_ICRS","_RAJ2000"],["DEJ2000","DE_ICRS","_DEJ2000"])
    out=df.copy();out["ra"]=raval;out["dec"]=decval
    out["sn_subtype"]=out[typec].astype("string") if typec else pd.NA
    out["event_time_raw"]=pd.NA
    out["event_discoverer"]=out[disc].astype("string") if disc else pd.NA
    out.insert(0,"catalog",CATALOG)
    # VizieR stores identifiers such as 2011fe; normalize display name only.
    ids=out[idc].astype("string").str.strip();out.insert(1,"catalog_object_id",ids);out.insert(2,"object_name","SN "+ids)
    out=add_standard_metadata(out,radius_arcmin=radius_arcmin,ref_epoch=2000.0,poserr_arcsec=1.0,entity_kind="transient_event")
    return out.dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

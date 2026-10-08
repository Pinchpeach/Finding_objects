"""ASAS-SN bright-supernova catalogue collector via CDS VizieR.

Neumann et al. (2023), J/MNRAS/520/4356, covers bright SNe from 2018-2020.
Rows are represented as transient events, not persistent host-galaxy sources.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick,coordinates,add_standard_metadata

CATALOG="ASAS-SN Supernova Catalog"
TABLES=("J/MNRAS/520/4356/table1","J/MNRAS/520/4356/table2")

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    coord=SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs")
    frames=[]
    for table in TABLES:
        try:
            result=Vizier(columns=["**"],row_limit=-1).query_region(coord,radius=float(radius_arcmin)*u.arcmin,catalog=table)
        except Exception:
            continue
        if not result:continue
        df=result[0].to_pandas()
        if df.empty:continue
        idc=pick(df,["IAUName","SNName","Name","ASASSN"])
        typec=pick(df,["SpType","Type","SNType"])
        datec=pick(df,["DiscDate","DiscoveryDate","Date","MJD"])
        if idc is None:continue
        try:raval,decval=coordinates(df,["RAJ2000","RA_ICRS","RAdeg","_RAJ2000","RA"],["DEJ2000","DE_ICRS","DEdeg","_DEJ2000","DE"])
        except Exception:continue
        out=df.copy(); out["ra"]=raval; out["dec"]=decval
        out["sn_subtype"]=out[typec].astype("string") if typec else pd.NA
        out["event_time_raw"]=out[datec].astype("string") if datec else pd.NA
        if datec and datec.upper()=="MJD":
            out["event_mjd"]=pd.to_numeric(out[datec],errors="coerce")
        elif datec:
            parsed=pd.to_datetime(out[datec],errors="coerce",utc=True)
            out["event_mjd"]=parsed.map(lambda x: (x.timestamp()/86400.0+40587.0) if pd.notna(x) else pd.NA)
        else:out["event_mjd"]=pd.NA
        out["sn_catalog_table"]=table
        out.insert(0,"catalog",CATALOG);out.insert(1,"catalog_object_id",out[idc].astype("string"));out.insert(2,"object_name",out[idc].astype("string"))
        out=add_standard_metadata(out,radius_arcmin=radius_arcmin,ref_epoch=2000.0,poserr_arcsec=1.0,entity_kind="transient_event")
        frames.append(out)
    if not frames:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","sn_subtype","event_mjd","entity_kind"])
    return pd.concat(frames,ignore_index=True,sort=False).dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):raise ValueError("invalid ASAS-SN output")
    Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""ASAS-SN bright-supernova catalogue collector via CDS VizieR.

Neumann et al. (2023), J/MNRAS/520/4356, tables 1 and 2 cover bright
supernovae from 2018-2020. Retrieval only; association remains in Preprocess.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CATALOG="ASAS-SN Supernova Catalog"
TABLES=("J/MNRAS/520/4356/table1","J/MNRAS/520/4356/table2")

def _pick(df,names):
    low={str(c).lower():c for c in df.columns}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return None

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    coord=SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs")
    frames=[]
    for table in TABLES:
        try:
            result=Vizier(columns=["**"],row_limit=-1).query_region(
                coord,radius=float(radius_arcmin)*u.arcmin,catalog=table
            )
        except Exception:
            continue
        if not result:
            continue
        df=result[0].to_pandas()
        if df.empty:
            continue
        rac=_pick(df,["RAJ2000","RA_ICRS","RAdeg","_RAJ2000","RA"])
        decc=_pick(df,["DEJ2000","DE_ICRS","DEdeg","_DEJ2000","DE"])
        idc=_pick(df,["IAUName","SNName","Name"])
        namec=_pick(df,["IAUName","SNName","Name"])
        typec=_pick(df,["SpType","Type","SNType"])
        if not all([rac,decc,idc]):
            continue
        out=df.copy()
        out["ra"]=pd.to_numeric(out[rac],errors="coerce")
        out["dec"]=pd.to_numeric(out[decc],errors="coerce")
        out["sn_subtype"]=out[typec].astype("string") if typec else pd.NA
        out["sn_catalog_table"]=table
        out.insert(0,"catalog",CATALOG)
        out.insert(1,"catalog_object_id",out[idc].astype("string"))
        out.insert(2,"object_name",out[namec].astype("string"))
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","sn_subtype"])
    df=pd.concat(frames,ignore_index=True,sort=False).dropna(subset=["ra","dec"])
    return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):
        raise ValueError("invalid ASAS-SN output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

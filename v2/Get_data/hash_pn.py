"""HASH planetary-nebula catalogue collector via CDS VizieR.

Catalog: V/163/pnmain (HASH main catalogue). Retrieval only; association remains
in v2/Preprocess.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CATALOG="HASH PN Catalog"
VIZIER_CATALOG="V/163/pnmain"

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
    result=Vizier(columns=["**"],row_limit=-1).query_region(
        coord,radius=float(radius_arcmin)*u.arcmin,catalog=VIZIER_CATALOG
    )
    if not result:
        return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
    df=result[0].to_pandas()
    if df.empty:
        return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])

    rac=_pick(df,["RAJ2000","RA_ICRS","RAdeg","_RAJ2000"])
    decc=_pick(df,["DEJ2000","DE_ICRS","DEdeg","_DEJ2000"])
    idc=_pick(df,["HASH","PNG","Name"])
    namec=_pick(df,["Name","PNG","HASH"])
    if not all([rac,decc,idc]):
        raise KeyError(f"HASH PN required columns missing; got {list(df.columns)}")

    out=df.copy()
    out["ra"]=pd.to_numeric(out[rac],errors="coerce")
    out["dec"]=pd.to_numeric(out[decc],errors="coerce")
    out.insert(0,"catalog",CATALOG)
    out.insert(1,"catalog_object_id",out[idc].astype("string"))
    out.insert(2,"object_name",out[namec].astype("string") if namec else out[idc].astype("string"))
    return out.dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):
        raise ValueError("invalid HASH PN output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

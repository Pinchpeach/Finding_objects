"""Roma-BZCAT 5th edition blazar catalogue collector (VizieR VII/274; 2.22.0).

Massaro et al. (2015, Ap&SS 357, 75): 3561 sources, every one radio-detected
and checked on optical spectra; the name prefix gives the type
(5BZB BL Lac, 5BZQ flat-spectrum radio quasar, 5BZG BL Lac with a dominant
host galaxy, 5BZU blazar of uncertain type).  Membership is identity
evidence, like ATNF for pulsars.  Columns checked against VizieR
(v2_new_targets.yml probe, 2026-10-13).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick,coordinates,add_standard_metadata
CATALOG="Roma-BZCAT";VIZIER_CATALOG="VII/274/bzcat5"
BZ_TYPES={"5BZB":"BL_LAC","5BZQ":"FSRQ","5BZG":"BL_LAC_GALAXY_DOMINATED","5BZU":"UNCERTAIN"}

def blazar_type(name)->str|None:
    s=str(name or "").strip().upper()
    return BZ_TYPES.get(s[:4])

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    empty=pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","blazar_type"])
    result=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs"),radius=float(radius_arcmin)*u.arcmin,catalog=VIZIER_CATALOG)
    if not result:return empty
    df=result[0].to_pandas()
    if df.empty:return empty
    namec=pick(df,["Name","5BZCAT"])
    if namec is None:raise KeyError(f"BZCAT name column missing; got {list(df.columns)}")
    raval,decval=coordinates(df,["RAJ2000","_RAJ2000","RA_ICRS"],["DEJ2000","_DEJ2000","DE_ICRS"])
    out=df.copy();out["ra"]=raval;out["dec"]=decval
    names=out[namec].astype("string").str.strip()
    out["blazar_type"]=names.map(blazar_type)
    out.insert(0,"catalog",CATALOG);out.insert(1,"catalog_object_id",names);out.insert(2,"object_name",names)
    out=add_standard_metadata(out,radius_arcmin=radius_arcmin,ref_epoch=2000.0,poserr_arcsec=1.0)
    return out.dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):raise ValueError("invalid BZCAT output")
    Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

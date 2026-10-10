"""Independent Chandra CSC 2.0 cone-search collector. No cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="Chandra CSC 2.0"; VIZIER_CATALOG="IX/57/csc2master"
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 tabs=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=tabs[0].to_pandas()
 if "name" not in df: raise KeyError("identifier column missing: "+"name")
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["name"].astype("string"));df.insert(2,"object_name",df["name"].astype("string"))
 df.insert(3,"ra",pd.to_numeric(df["RAICRS"],errors="coerce"));df.insert(4,"dec",pd.to_numeric(df["DEICRS"],errors="coerce"))
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

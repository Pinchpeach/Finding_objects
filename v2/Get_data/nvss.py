"""Independent NVSS cone-search collector via VizieR. No cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="NVSS"; VIZIER_CATALOG="VIII/65/nvss"
def _degrees(df:pd.DataFrame):
 """VizieR gives this catalogue's RAJ2000/DEJ2000 as sexagesimal strings
 ("00 34 08.71"); pd.to_numeric made them NaN and every source was dropped
 before association.  Use VizieR's computed decimal _RAJ2000/_DEJ2000, else
 parse the sexagesimal columns."""
 if "_RAJ2000" in df and "_DEJ2000" in df:
  ra=pd.to_numeric(df["_RAJ2000"],errors="coerce");dec=pd.to_numeric(df["_DEJ2000"],errors="coerce")
  if ra.notna().all() and dec.notna().all():return ra,dec
 ra=pd.to_numeric(df["RAJ2000"],errors="coerce");dec=pd.to_numeric(df["DEJ2000"],errors="coerce")
 if len(df) and (ra.isna().any() or dec.isna().any()):
  # Row by row (2.23.0): one empty or malformed value made the bulk
  # SkyCoord parse raise and the whole collector fail.
  from _catalog_utils import coordinates
  ra,dec=coordinates(df,["RAJ2000"],["DEJ2000"])
 return ra,dec
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 v=Vizier(columns=["**","_RAJ2000","_DEJ2000"],row_limit=-1)
 tables=v.query_region(SkyCoord(ra*u.deg,dec*u.deg,frame="icrs"),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not tables:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=tables[0].to_pandas()
 if "NVSS" not in df.columns: raise KeyError("catalog identifier column missing")
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["NVSS"].astype("string"))
 df.insert(2,"object_name",CATALOG+" "+df["catalog_object_id"].astype("string"))
 ra,dec=_degrees(df);df.insert(3,"ra",ra);df.insert(4,"dec",dec)
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""NED cone-search collector. Extragalactic reference metadata."""
from pathlib import Path
import pandas as pd
CATALOG="NED"
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.ipac.ned import Ned
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 t=Ned.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=t.to_pandas();n="Object Name";df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[n].astype("string"));df.insert(2,"object_name",df[n].astype("string"));df.insert(3,"ra",pd.to_numeric(df["RA"],errors="coerce"));df.insert(4,"dec",pd.to_numeric(df["DEC"],errors="coerce"))
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

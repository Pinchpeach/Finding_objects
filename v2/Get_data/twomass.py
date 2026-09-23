"""Independent 2MASS PSC cone-search collector via VizieR."""
from pathlib import Path
import pandas as pd
CATALOG="2MASS PSC";VIZIER_CATALOG="II/246/out"
def fetch(ra,dec,radius_arcmin):
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 ts=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not ts:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=ts[0].to_pandas()
 def pick(names):
  low={str(c).lower():c for c in df.columns}
  for n in names:
   if n in df.columns:return n
   if n.lower() in low:return low[n.lower()]
 idc=pick(["_2MASS","2MASS","2MASS_name"]);rac=pick(["RAJ2000","RA_ICRS"]);dcc=pick(["DEJ2000","DE_ICRS"])
 if not all([idc,rac,dcc]):raise KeyError(f"2MASS required columns missing; got {list(df.columns)}")
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[idc].astype("string"));df.insert(2,"object_name",CATALOG+" "+df["catalog_object_id"]);df.insert(3,"ra",pd.to_numeric(df[rac],errors="coerce"));df.insert(4,"dec",pd.to_numeric(df[dcc],errors="coerce"))
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

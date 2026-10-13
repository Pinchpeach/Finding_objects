"""Independent Chandra CSC 2.0 cone-search collector. No cross-match/classification.

VizieR column names are matched case-insensitively from candidate lists
(2.19.1): the live tables name the identifier "2CXO" (not "name"), and the old exact
names made every query raise, so this catalogue never reached a result.
"""
from pathlib import Path
import pandas as pd
from _catalog_utils import pick, coordinates
CATALOG="Chandra CSC 2.0"; VIZIER_CATALOG="IX/57/csc2master"
ID_COLUMNS=['2CXO', 'name', 'Name']
RA_COLUMNS=['RAICRS', 'RA_ICRS', 'RAJ2000', '_RAJ2000']
DEC_COLUMNS=['DEICRS', 'DE_ICRS', 'DEJ2000', '_DEJ2000']
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 tabs=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=tabs[0].to_pandas()
 idc=pick(df,ID_COLUMNS)
 if idc is None: raise KeyError(f"identifier column missing (tried {ID_COLUMNS}); got {list(df.columns)[:20]}")
 rv,dv=coordinates(df,RA_COLUMNS,DEC_COLUMNS)
 ident=df[idc].astype("string").str.strip()
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",ident);df.insert(2,"object_name",ident)
 df.insert(3,"ra",pd.to_numeric(rv,errors="coerce"));df.insert(4,"dec",pd.to_numeric(dv,errors="coerce"))
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

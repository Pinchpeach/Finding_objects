"""Independent TGSS ADR1 (GMRT 150 MHz; Intema et al. 2017, A&A 598, A78) cone-search
collector via VizieR.  No cross-match/classification.

150 MHz with NVSS 1.4 GHz gives the radio spectral index used by the pulsar
rule (Frail et al. 2018: alpha <= -1.5 and compactness S_total / S_peak <= 1.5).
"""
from pathlib import Path
import pandas as pd
CATALOG="TGSS ADR1"; VIZIER_CATALOG="J/A+A/598/A78/table3"
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 tables=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(ra*u.deg,dec*u.deg,frame="icrs"),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not tables:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=tables[0].to_pandas()
 if "TGSSADR" not in df.columns: raise KeyError("catalog identifier column missing")
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["TGSSADR"].astype("string"))
 df.insert(2,"object_name","TGSS "+df["catalog_object_id"].astype("string"))
 df.insert(3,"ra",pd.to_numeric(df["RAJ2000"],errors="coerce"));df.insert(4,"dec",pd.to_numeric(df["DEJ2000"],errors="coerce"))
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""Independent LAMOST DR catalog cone-search collector. No cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="LAMOST DR catalog"; VIZIER_CATALOG="V/164/dr5"; STELLAR_CATALOG="V/164/stellar5"
LASP={"Teff":"lasp_teff","e_Teff":"lasp_teff_err","logg":"lasp_logg","e_logg":"lasp_logg_err","[Fe/H]":"lasp_feh","e_[Fe/H]":"lasp_feh_err"}
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.vizier import Vizier
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 tabs=Vizier(columns=["**"],row_limit=-1).query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,catalog=VIZIER_CATALOG)
 if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=tabs[0].to_pandas()
 if "ObsID" not in df: raise KeyError("identifier column missing: "+"ObsID")
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["ObsID"].astype("string"));df.insert(2,"object_name",df["ObsID"].astype("string"))
 df.insert(3,"ra",pd.to_numeric(df["RAJ2000"],errors="coerce"));df.insert(4,"dec",pd.to_numeric(df["DEJ2000"],errors="coerce"))
 df=df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
 # LASP Teff / log g / [Fe/H] of A, F, G, K stars (V/164/stellar5; Luo et al.
 # 2015).  A failed query leaves them empty and keeps the spectra.
 try:
  st=Vizier(columns=["ObsID","Teff","e_Teff","logg","e_logg","[Fe/H]","e_[Fe/H]"],row_limit=-1).query_region(
      SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,catalog=STELLAR_CATALOG)
  if st:
   p=st[0].to_pandas().rename(columns=LASP)
   p["catalog_object_id"]=p.pop("ObsID").astype("string")
   df=df.merge(p.drop_duplicates("catalog_object_id")[["catalog_object_id",*[c for c in LASP.values() if c in p]]],on="catalog_object_id",how="left")
 except Exception as exc:
  print(f"[lamost_spectroscopy] LASP parameter query failed: {type(exc).__name__}: {str(exc)[:120]}")
 for c in LASP.values():
  if c not in df:df[c]=pd.NA
 return df
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

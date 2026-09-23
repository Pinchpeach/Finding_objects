"""SIMBAD cone-search collector. Reference metadata; keep separate from raw evidence."""
from pathlib import Path
import pandas as pd
CATALOG="SIMBAD"
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.simbad import Simbad
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 s=Simbad();s.add_votable_fields("otype","sp","plx","pmra","pmdec","rvz_redshift")
 t=s.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=t.to_pandas();idc="main_id" if "main_id" in df else "MAIN_ID";rac="ra" if "ra" in df else "RA";dcc="dec" if "dec" in df else "DEC"
 coord=SkyCoord(df[rac].astype(str).to_numpy(),df[dcc].astype(str).to_numpy(),unit=(u.hourangle,u.deg))
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[idc].astype("string"));df.insert(2,"object_name",df[idc].astype("string"));df.insert(3,"ra",coord.ra.deg);df.insert(4,"dec",coord.dec.deg)
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

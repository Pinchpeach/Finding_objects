"""SIMBAD cone-search collector. Reference metadata."""
from pathlib import Path
import pandas as pd
CATALOG="SIMBAD"
def fetch(ra,dec,radius_arcmin):
 from astroquery.simbad import Simbad
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 s=Simbad();s.add_votable_fields("otype","sp","plx","pmra","pmdec","rvz_redshift")
 t=s.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=t.to_pandas();low={str(c).lower():c for c in df.columns};idc=low.get("main_id");rac=low.get("ra");dcc=low.get("dec")
 if not all([idc,rac,dcc]):raise KeyError(f"SIMBAD required columns missing; got {list(df.columns)}")
 rv=pd.to_numeric(df[rac],errors="coerce");dv=pd.to_numeric(df[dcc],errors="coerce")
 if rv.isna().any() or dv.isna().any():
  coord=SkyCoord(df[rac].astype(str).to_numpy(),df[dcc].astype(str).to_numpy(),unit=(u.hourangle,u.deg));rv=coord.ra.deg;dv=coord.dec.deg
 df["ra_raw"]=df[rac];df["dec_raw"]=df[dcc];df[rac]=rv;df[dcc]=dv
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[idc].astype("string"));df.insert(2,"object_name",df[idc].astype("string"))
 if rac!="ra":df.insert(3,"ra",rv)
 if dcc!="dec":df.insert(4 if "ra" in df else 3,"dec",dv)
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

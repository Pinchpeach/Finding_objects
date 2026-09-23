"""SDSS DR18 spectroscopy metadata collector. Spectra can be downloaded later by specobjid."""
from pathlib import Path
import pandas as pd
CATALOG="SDSS DR18 spectroscopy"
FIELDS=["specobjid","bestobjid","ra","dec","plate","mjd","fiberid","class","subclass","z","zerr","zwarning"]
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.sdss import SDSS
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 t=SDSS.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,spectro=True,specobj_fields=FIELDS,data_release=18)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name",*FIELDS])
 df=t.to_pandas();df["specobjid"]=df["specobjid"].astype("uint64").astype(str);df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["specobjid"]);df.insert(2,"object_name","SDSS spectrum "+df["specobjid"])
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""SDSS DR18 independent photometric collector. No cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="SDSS DR18 PhotoObj"
COLUMNS=["objid","ra","dec","type","clean","mode","run","rerun","camcol","field",
"psfMag_u","psfMagErr_u","psfMag_g","psfMagErr_g","psfMag_r","psfMagErr_r","psfMag_i","psfMagErr_i","psfMag_z","psfMagErr_z",
"modelMag_u","modelMagErr_u","modelMag_g","modelMagErr_g","modelMag_r","modelMagErr_r","modelMag_i","modelMagErr_i","modelMag_z","modelMagErr_z",
"petroMag_u","petroMagErr_u","petroMag_g","petroMagErr_g","petroMag_r","petroMagErr_r","petroMag_i","petroMagErr_i","petroMag_z","petroMagErr_z"]
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.sdss import SDSS
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 pos=SkyCoord(ra=ra*u.deg,dec=dec*u.deg,frame="icrs")
 t=SDSS.query_region(pos,radius=radius_arcmin*u.arcmin,photoobj_fields=COLUMNS,data_release=18)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name",*COLUMNS])
 df=t.to_pandas()
 # Preserve SDSS's 64-bit identifier as text before CSV serialization.
 df["objid"]=df["objid"].astype("uint64").astype(str)
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["objid"]);df.insert(2,"object_name","SDSS J"+df["ra"].map(lambda x:f"{x:.6f}")+df["dec"].map(lambda x:f"{x:+.6f}"))
 return df
def save(df:pd.DataFrame,path:str|Path)->None:
 required={"catalog","catalog_object_id","object_name","ra","dec"}
 if not required.issubset(df.columns):raise ValueError("invalid SDSS output")
 if df["catalog_object_id"].duplicated().any():raise ValueError("duplicate SDSS objid")
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.to_csv(path,index=False)

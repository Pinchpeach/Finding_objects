"""Independent LAMOST spectroscopy collector definition. Get_data performs no cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="LAMOST spectroscopy"
FIELDS=["obsid","designation","ra","dec","obsdate","planid","spid","fiberid","class","subclass","z","z_err","snr_u","snr_g","snr_r","snr_i","snr_z"]

def normalize(rows:pd.DataFrame,id_column:str,name_column:str|None=None)->pd.DataFrame:
 df=rows.copy();df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[id_column].astype("string"))
 names=df[name_column].astype("string") if name_column and name_column in df else pd.Series([CATALOG+" "+x for x in df["catalog_object_id"].astype(str)],index=df.index,dtype="string")
 df.insert(2,"object_name",names);return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 raise NotImplementedError("official LAMOST spectroscopy query endpoint/client wiring pending")

def save(df:pd.DataFrame,path:str|Path)->None:
 if not {"catalog","catalog_object_id","object_name","ra","dec"}.issubset(df.columns):raise ValueError("invalid LAMOST spectroscopy output")
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

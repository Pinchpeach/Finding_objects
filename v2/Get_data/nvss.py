"""Independent NVSS collector. No cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="NVSS"
def normalize(rows:pd.DataFrame,id_column:str,name_column:str|None=None)->pd.DataFrame:
 df=rows.copy();df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[id_column].astype("string"));names=df[name_column].astype("string") if name_column and name_column in df else CATALOG+" "+df["catalog_object_id"].astype("string");df.insert(2,"object_name",names);return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 raise NotImplementedError("official query wiring pending")
def save(df:pd.DataFrame,path:str|Path)->None:
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

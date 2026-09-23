"""Independent LoTSS collector (radio measurements). No cross-match/classification in Get_data."""
from pathlib import Path
import pandas as pd
CATALOG="LoTSS"
FIELDS=["source_id","source_name","ra","dec","e_ra","e_dec","peak_flux","peak_flux_err","total_flux","total_flux_err","maj","min","pa"]

def normalize(rows:pd.DataFrame,id_column:str,name_column:str|None=None)->pd.DataFrame:
    """Normalize adapter query results after the service-specific query returns."""
    df=rows.copy()
    df.insert(0,"catalog",CATALOG)
    df.insert(1,"catalog_object_id",df[id_column].astype("string"))
    if name_column and name_column in df: names=df[name_column].astype("string")
    else: names=pd.Series([CATALOG+" "+x for x in df["catalog_object_id"].astype(str)],index=df.index,dtype="string")
    df.insert(2,"object_name",names)
    return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    """Service-specific network query entry point. Must return FIELDS plus standard identity columns."""
    raise NotImplementedError("Wire the official LoTSS query endpoint/client here")

def save(df:pd.DataFrame,path:str|Path)->None:
    if not {"catalog","catalog_object_id","object_name","ra","dec"}.issubset(df.columns): raise ValueError("invalid LoTSS output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""Independent DESI Legacy Surveys collector (tractor photometry). No cross-match/classification in Get_data."""
from pathlib import Path
import pandas as pd
CATALOG="DESI Legacy Surveys"
FIELDS=["release","brickid","objid","type","ra","dec","ra_ivar","dec_ivar","flux_g","flux_r","flux_z","flux_w1","flux_w2","flux_w3","flux_w4","flux_ivar_g","flux_ivar_r","flux_ivar_z","flux_ivar_w1","flux_ivar_w2","flux_ivar_w3","flux_ivar_w4","mw_transmission_g","mw_transmission_r","mw_transmission_z","mw_transmission_w1","mw_transmission_w2","maskbits"]

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
    raise NotImplementedError("Wire the official DESI Legacy Surveys query endpoint/client here")

def save(df:pd.DataFrame,path:str|Path)->None:
    if not {"catalog","catalog_object_id","object_name","ra","dec"}.issubset(df.columns): raise ValueError("invalid DESI Legacy Surveys output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

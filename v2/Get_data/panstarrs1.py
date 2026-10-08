"""Pan-STARRS1 DR2 independent photometry collector. No cross-match/classification."""
from io import StringIO
from pathlib import Path
import pandas as pd, requests
MIN_DETECTIONS=2
CATALOG="Pan-STARRS1 DR2 MeanObject"; API="https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/mean.csv"
COLUMNS=["objID","objName","raMean","decMean","raMeanErr","decMeanErr","nDetections","ng","nr","ni","nz","ny","gMeanPSFMag","gMeanPSFMagErr","rMeanPSFMag","rMeanPSFMagErr","iMeanPSFMag","iMeanPSFMagErr","zMeanPSFMag","zMeanPSFMagErr","yMeanPSFMag","yMeanPSFMagErr","gMeanKronMag","gMeanKronMagErr","rMeanKronMag","rMeanKronMagErr","iMeanKronMag","iMeanKronMagErr","zMeanKronMag","zMeanKronMagErr","yMeanKronMag","yMeanKronMagErr","gMeanApMag","gMeanApMagErr","rMeanApMag","rMeanApMagErr","iMeanApMag","iMeanApMagErr","zMeanApMag","zMeanApMagErr","yMeanApMag","yMeanApMagErr"]
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 # nDetections >= 2 (STScI PS1 guidance): single-detection MeanObject rows are
 # mostly spurious/moving; they duplicated real sources and made Stage-1
 # association ambiguous in real fields.
 p={"ra":ra,"dec":dec,"radius":radius_arcmin/60.0,"nDetections.gte":MIN_DETECTIONS,"columns":"["+",".join(COLUMNS)+"]"};r=requests.get(API,params=p,timeout=120);r.raise_for_status()
 df=pd.read_csv(StringIO(r.text),dtype={"objID":"string","objName":"string"})
 if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec",*COLUMNS])
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["objID"].astype("string"));df.insert(2,"object_name",df["objName"].fillna("PS1 "+df["objID"].astype("string")));df.insert(3,"ra",df["raMean"]);df.insert(4,"dec",df["decMean"])
 return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
def save(df:pd.DataFrame,path:str|Path)->None:
 if not {"catalog","catalog_object_id","object_name","ra","dec"}.issubset(df.columns):raise ValueError("invalid Pan-STARRS output")
 Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

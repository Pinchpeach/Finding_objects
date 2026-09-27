"""Suh (2021) Galactic AGB catalog collector via CDS VizieR.

Catalog: J/ApJS/256/43
Tables 9-12 contain O-rich/C-rich AGB samples based on IRAS/WISE positions.
Cross-survey counterpart association is deferred to v2/Preprocess.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CATALOG="Suh 2021 AGB Catalog"
TABLES={
    "J/ApJS/256/43/table9":"OAGB_IRAS",
    "J/ApJS/256/43/table10":"CAGB_IRAS",
    "J/ApJS/256/43/table11":"OAGB_WISE",
    "J/ApJS/256/43/table12":"CAGB_WISE",
}

def _pick(df:pd.DataFrame,names):
    low={str(c).lower():c for c in df.columns}
    for name in names:
        if name.lower() in low:return low[name.lower()]
    return None

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    coord=SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs")
    frames=[]
    for table_id,subtype in TABLES.items():
        try:
            result=Vizier(columns=["**"],row_limit=-1).query_region(
                coord,
                radius=float(radius_arcmin)*u.arcmin,
                catalog=table_id,
            )
        except Exception:
            continue
        if not result:continue
        df=result[0].to_pandas()
        if df.empty:continue
        rac=_pick(df,["RAdeg","RAJ2000","RA_ICRS"])
        decc=_pick(df,["DEdeg","DEJ2000","DE_ICRS"])
        if not rac or not decc:continue
        idc=_pick(df,["WISEA","IRAS","OI-N","CI-N","OW-N","CW-N","recStar"])
        out=df.copy()
        out["ra"]=pd.to_numeric(out[rac],errors="coerce")
        out["dec"]=pd.to_numeric(out[decc],errors="coerce")
        out["agb_subclass"]=subtype
        if idc:
            ids=out[idc].astype("string")
        else:
            ids=pd.Series(range(len(out)),index=out.index).astype("string")
        out.insert(0,"catalog",CATALOG)
        out.insert(1,"catalog_object_id",subtype+":"+ids.fillna(""))
        out.insert(2,"object_name",out["catalog_object_id"])
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","agb_subclass"])
    df=pd.concat(frames,ignore_index=True,sort=False).dropna(subset=["ra","dec"])
    return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec","agb_subclass"}
    if not required.issubset(df.columns):
        raise ValueError("invalid Suh AGB output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

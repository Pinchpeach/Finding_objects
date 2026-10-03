"""Independent gamma-ray pulsar evidence from the Fermi-LAT 4FGL catalogue.

Only sources with the identified class PSR (pulsations detected) are promoted
to pulsar evidence. Lower-case associated candidates are deliberately excluded.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick,coordinates,add_standard_metadata

CATALOG="Fermi 4FGL Pulsar Catalog"
TABLE="J/ApJS/247/33/4fgl"

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    # LAT localizations are much broader than optical catalogues. Query up to
    # 12 arcmin, then retain only explicitly identified pulsars; association
    # uses the catalogue localization uncertainty below.
    qr=max(float(radius_arcmin),12.0)
    tabs=Vizier(columns=["**"],row_limit=-1).query_region(
        SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs"),
        radius=qr*u.arcmin,catalog=TABLE)
    if not tabs:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","fermi_class"])
    df=tabs[0].to_pandas()
    if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","fermi_class"])
    cls=pick(df,["CLASS1","Class1","Class","CLASS"])
    if cls is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","fermi_class"])
    # Upper-case PSR is the identified-by-pulsations class in 4FGL.
    df=df[df[cls].astype(str).str.strip()=="PSR"].copy()
    if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec","fermi_class"])
    ident=pick(df,["4FGL","Source_Name"]); rav,dev=coordinates(df,["RAJ2000","RA_ICRS","_RA"],["DEJ2000","DE_ICRS","_DE"])
    amaj=pick(df,["amaj95","Conf_95_SemiMajor"])
    poserr=pd.to_numeric(df[amaj],errors="coerce")*3600.0 if amaj else pd.Series(300.0,index=df.index)
    ids=df[ident].astype("string") if ident else df.index.astype(str)
    out=pd.DataFrame({"catalog":CATALOG,"catalog_object_id":ids,"object_name":ids,"ra":rav,"dec":dev,
                      "fermi_class":"PSR","poserr_arcsec":poserr})
    out=add_standard_metadata(out,radius_arcmin=qr,ref_epoch=2012.0,entity_kind="persistent_source")
    return out.dropna(subset=["ra","dec"]).drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

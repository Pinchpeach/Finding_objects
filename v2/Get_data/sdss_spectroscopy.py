"""SDSS DR18 spectroscopy metadata collector. Spectra can be downloaded later by specobjid.

Galaxy spectra also get the MPA-JHU emission-line and 4000 A break
measurements (galSpecLine, galSpecIndx; Brinchmann et al. 2004, Kauffmann et
al. 2003) used by the BPT / WHAN / Dn4000 rules of Classifier/subclass.py.
A failed line query leaves those columns empty; it never drops the spectra.
"""
from pathlib import Path
import pandas as pd
CATALOG="SDSS DR18 spectroscopy"
FIELDS=["specobjid","bestobjid","ra","dec","plate","mjd","fiberid","class","subclass","z","zerr","zwarning"]
LINE_FIELDS=["h_alpha_flux","h_alpha_flux_err","h_beta_flux","h_beta_flux_err","oiii_5007_flux","oiii_5007_flux_err",
             "nii_6584_flux","nii_6584_flux_err","h_alpha_eqw","nii_6584_eqw","d4000_n"]
LINE_SQL=("SELECT l.specobjid,"+",".join(("i." if c=="d4000_n" else "l.")+c for c in LINE_FIELDS)+
          " FROM galSpecLine AS l LEFT JOIN galSpecIndx AS i ON i.specobjid=l.specobjid WHERE l.specobjid IN ({ids})")
def _lines(ids:list[str])->pd.DataFrame:
 from astroquery.sdss import SDSS
 parts=[]
 for s in range(0,len(ids),80):   # SkyServer answers 404 to over-long GET queries
  t=SDSS.query_sql(LINE_SQL.format(ids=",".join(ids[s:s+80])),data_release=18)
  if t is not None and len(t):parts.append(t.to_pandas())
 if not parts:return pd.DataFrame(columns=["specobjid",*LINE_FIELDS])
 out=pd.concat(parts,ignore_index=True);out.columns=[c.lower() for c in out.columns]
 out["specobjid"]=out["specobjid"].astype("uint64").astype(str)
 return out.drop_duplicates("specobjid")
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.sdss import SDSS
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 t=SDSS.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin,spectro=True,specobj_fields=FIELDS,data_release=18)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name",*FIELDS,*LINE_FIELDS])
 df=t.to_pandas();df["specobjid"]=df["specobjid"].astype("uint64").astype(str);df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df["specobjid"]);df.insert(2,"object_name","SDSS spectrum "+df["specobjid"])
 df=df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
 gal=df.loc[df["class"].astype(str).str.strip().str.upper().eq("GALAXY"),"specobjid"].tolist()
 try:lines=_lines(gal) if gal else pd.DataFrame(columns=["specobjid",*LINE_FIELDS])
 except Exception as exc:
  print(f"[sdss_spectroscopy] emission-line query failed: {type(exc).__name__}: {str(exc)[:120]}")
  lines=pd.DataFrame(columns=["specobjid",*LINE_FIELDS])
 return df.merge(lines[["specobjid",*[c for c in LINE_FIELDS if c in lines]]],on="specobjid",how="left")
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

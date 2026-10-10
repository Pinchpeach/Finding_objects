"""SIMBAD cone-search collector. Reference metadata.

Besides the basic fields, the literature behind each object is attached
(best effort; a failed reference query leaves these columns empty and never
fails the collector):
  simbad_otype_label     readable object type (SIMBAD otypedef)
  simbad_nbref           number of papers citing the object
  simbad_ref_bibcodes    up to 3 papers that discuss the object most
                         (has_ref.obj_freq), then most recent; '|' separated
  simbad_ref_titles / simbad_ref_years   matching titles and years
"""
from pathlib import Path
import pandas as pd
CATALOG="SIMBAD"
def fetch(ra,dec,radius_arcmin):
 from astroquery.simbad import Simbad
 from astropy.coordinates import SkyCoord
 import astropy.units as u
 s=Simbad();s.add_votable_fields("otype","sp","plx","pmra","pmdec","rvz_redshift")
 t=s.query_region(SkyCoord(ra*u.deg,dec*u.deg),radius=radius_arcmin*u.arcmin)
 if t is None:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"])
 df=t.to_pandas();low={str(c).lower():c for c in df.columns};idc=low.get("main_id");rac=low.get("ra");dcc=low.get("dec")
 if not all([idc,rac,dcc]):raise KeyError(f"SIMBAD required columns missing; got {list(df.columns)}")
 rv=pd.to_numeric(df[rac],errors="coerce");dv=pd.to_numeric(df[dcc],errors="coerce")
 if rv.isna().any() or dv.isna().any():
  coord=SkyCoord(df[rac].astype(str).to_numpy(),df[dcc].astype(str).to_numpy(),unit=(u.hourangle,u.deg));rv=coord.ra.deg;dv=coord.dec.deg
 df["ra_raw"]=df[rac];df["dec_raw"]=df[dcc];df[rac]=rv;df[dcc]=dv
 df.insert(0,"catalog",CATALOG);df.insert(1,"catalog_object_id",df[idc].astype("string"));df.insert(2,"object_name",df[idc].astype("string"))
 if rac!="ra":df.insert(3,"ra",rv)
 if dcc!="dec":df.insert(4 if "ra" in df else 3,"dec",dv)
 df=df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)
 try:
  df=_attach_references(s,df)
 except Exception as exc:  # reference metadata is optional
  df["simbad_reference_status"]="error:"+type(exc).__name__
 return df

def _adql_list(values):
 return ",".join("'"+str(v).replace("'","''")+"'" for v in values)

def _attach_references(s,df,chunk=300,per_object=3):
 ids=df["catalog_object_id"].astype(str).tolist()
 rows=[];labels={}
 for i in range(0,len(ids),chunk):
  part=_adql_list(ids[i:i+chunk])
  q=("SELECT b.main_id, b.nbref, r.bibcode, r.\"year\" AS ref_year, r.title, h.obj_freq "
     "FROM basic AS b JOIN has_ref AS h ON h.oidref=b.oid JOIN ref AS r ON r.oidbib=h.oidbibref "
     f"WHERE b.main_id IN ({part})")
  t=s.query_tap(q)
  if t is not None and len(t):rows.append(t.to_pandas())
 try:
  od=s.query_tap("SELECT otype, label, description FROM otypedef").to_pandas()
  labels=dict(zip(od["otype"].astype(str),od["description"].astype(str)))
 except Exception:
  pass
 df["simbad_otype_label"]=df.get("otype",pd.Series(index=df.index,dtype=object)).astype(str).map(labels)
 if not rows:
  df["simbad_reference_status"]="no_references";return df
 r=pd.concat(rows,ignore_index=True)
 r.columns=[str(c).lower() for c in r.columns]
 r["obj_freq"]=pd.to_numeric(r.get("obj_freq"),errors="coerce").fillna(0)
 r["ref_year"]=pd.to_numeric(r.get("ref_year"),errors="coerce")
 r=r.sort_values(["main_id","obj_freq","ref_year"],ascending=[True,False,False])
 top=r.groupby("main_id").head(per_object).groupby("main_id")
 agg=pd.DataFrame({"simbad_nbref":r.groupby("main_id")["nbref"].first(),
                   "simbad_ref_bibcodes":top["bibcode"].agg(lambda x:"|".join(map(str,x))),
                   "simbad_ref_titles":top["title"].agg(lambda x:"|".join(str(v).replace("|","/") for v in x)),
                   "simbad_ref_years":top["ref_year"].agg(lambda x:"|".join(str(int(v)) if v==v else "" for v in x))})
 df=df.merge(agg,left_on="catalog_object_id",right_index=True,how="left")
 df["simbad_reference_status"]="ok"
 return df
def save(df,path):Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

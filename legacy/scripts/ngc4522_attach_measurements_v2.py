"""Rebuild NGC4522 measured-counterpart table with lossless SDSS objid handling.

Never round-trip objid through numeric inference. Canonicalize integer-looking IDs from
legacy CSVs, then validate cardinality before downstream SED/vector work.
"""
import json,pathlib,re,pandas as pd,numpy as np
M=pathlib.Path("results/ngc4522_multiwavelength");F=pathlib.Path("results/ngc4522_final");O=pathlib.Path("results/ngc4522_observed_v2");O.mkdir(parents=True,exist_ok=True)
def oid(v):
 s=str(v).strip()
 if re.fullmatch(r"\d+\.0",s):s=s[:-2]
 if "e" in s.lower():
  try:s=str(int(float(s)))
  except:pass
 return s
def main():
 a=pd.read_csv(F/"associations_v3.csv",dtype=str,keep_default_na=False)
 for c in ["catalog_row","separation_arcsec"]:a[c]=pd.to_numeric(a[c],errors="coerce")
 a["objid"]=a.objid.map(oid);rows=[]
 for sv,g in a.groupby("survey",sort=False):
  fp=M/f"{sv}_field.csv"
  if not fp.exists():continue
  d=pd.read_csv(fp,low_memory=False)
  for _,r in g.iterrows():
   rec={"objid":oid(r.objid),"survey":sv,"association_status":r.association_status_v3,"separation_arcsec":r.separation_arcsec,"catalog_row":r.catalog_row}
   k=r.catalog_row
   if pd.notna(k) and int(k)==k and 0<=int(k)<len(d):
    for c,v in d.iloc[int(k)].items():rec[f"{sv}__{c}"]=v
    rec["catalog_measurements_attached"]=True
   else:rec["catalog_measurements_attached"]=False
   rows.append(rec)
 z=pd.DataFrame(rows);z.to_csv(O/"all_counterpart_measurements.csv",index=False)
 q=z[(z.association_status=="PROBABLE") & z.catalog_measurements_attached].copy()
 # Integrity checks: object IDs must retain SDSS 18-19 digit form where applicable.
 lengths=q.objid.str.len().value_counts().sort_index().to_dict()
 per=q.groupby("survey").agg(rows=("objid","size"),objects=("objid","nunique")).reset_index()
 per.to_csv(O/"probable_counts_by_survey.csv",index=False)
 wide=q.set_index(["objid","survey"]).sort_index()
 # one row per object; survey-specific measurement columns remain prefixed
 out=[]
 for object_id,h in q.groupby("objid",sort=False):
  rec={"objid":object_id,"probable_surveys":";".join(sorted(h.survey.unique()))}
  for _,r in h.iterrows():
   for c,v in r.items():
    if c.startswith(str(r.survey)+"__"):rec[c]=v
  out.append(rec)
 pd.DataFrame(out).to_csv(O/"probable_photometry_wide.csv",index=False)
 summary={"association_rows":len(z),"attached":int(z.catalog_measurements_attached.sum()),"probable_rows":len(q),"probable_unique_objects":int(q.objid.nunique()),"objid_length_distribution":{str(k):int(v) for k,v in lengths.items()},"by_survey":per.to_dict("records"),"integrity":"PASS" if len(q)>0 and q.objid.nunique()>26 else "FAIL"}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
 if summary["integrity"]!="PASS":raise RuntimeError("objid integrity/cardinality check failed")
if __name__=="__main__":main()

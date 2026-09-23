"""Attach actual catalog photometry/flux rows to NGC4522 counterparts.

All catalog columns are preserved with survey prefixes so later likelihood models can use
measured values rather than mere counterpart presence. No magnitude-system conversion is
performed here; raw provenance is retained.
"""
import json,pathlib,pandas as pd,numpy as np
M=pathlib.Path("results/ngc4522_multiwavelength");F=pathlib.Path("results/ngc4522_final");O=pathlib.Path("results/ngc4522_observed");O.mkdir(parents=True,exist_ok=True)
def main():
 a=pd.read_csv(F/"associations_v3.csv",dtype={"objid":str}); rows=[]
 for sv,g in a.groupby("survey"):
  fp=M/f"{sv}_field.csv"
  if not fp.exists():continue
  d=pd.read_csv(fp)
  for _,r in g.iterrows():
   rec={"objid":str(r.objid),"survey":sv,"association_status":r.association_status_v3,"separation_arcsec":r.separation_arcsec}
   try:
    k=int(r.catalog_row)
    if 0<=k<len(d):
     for c,v in d.iloc[k].items():rec[f"{sv}__{c}"]=v
     rec["catalog_measurements_attached"]=True
    else:rec["catalog_measurements_attached"]=False
   except:rec["catalog_measurements_attached"]=False
   rows.append(rec)
 z=pd.DataFrame(rows);z.to_csv(O/"all_counterpart_measurements.csv",index=False)
 # wide table for probable associations only
 q=z[(z.association_status=="PROBABLE") & z.catalog_measurements_attached].copy()
 wide=[]
 for oid,h in q.groupby("objid"):
  rec={"objid":oid}
  for _,r in h.iterrows():
   sv=r.survey
   for c,v in r.items():
    if c.startswith(f"{sv}__"):rec[c]=v
  wide.append(rec)
 pd.DataFrame(wide).to_csv(O/"probable_photometry_wide.csv",index=False)
 summary={"association_rows":len(z),"rows_with_catalog_measurements":int(z.catalog_measurements_attached.sum()),"probable_rows_with_measurements":len(q),"objects_with_probable_measurements":q.objid.nunique(),"columns_by_survey":{sv:len([c for c in z.columns if c.startswith(sv+"__")]) for sv in z.survey.unique()}}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

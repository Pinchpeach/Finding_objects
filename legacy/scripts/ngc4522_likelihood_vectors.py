"""Likelihood-vector classification architecture.

For every master optical object, collect every currently observed evidence stream first,
then produce a class-likelihood VECTOR. Missing/unobserved streams are masked (neutral).
This initial implementation uses normalized evidence support; it is NOT yet a calibrated
posterior. Spectroscopic labels remain anchors, not prerequisites.
"""
from __future__ import annotations
import json,pathlib,math
import numpy as np,pandas as pd
B=pathlib.Path("results/ngc4522_field10");F=pathlib.Path("results/ngc4522_final");O=pathlib.Path("results/ngc4522_vector");O.mkdir(parents=True,exist_ok=True)
CLASSES=["STAR","GALAXY","AGN"]
def softmax(v):
 a=np.array(v,float);a-=a.max();e=np.exp(a);return e/e.sum()
def main():
 x=pd.read_csv(F/"final_classifications_v3.csv",dtype={"objid":str});p=pd.read_csv(B/"sdss_optical_census.csv",dtype={"objid":str});a=pd.read_csv(F/"associations_v3.csv",dtype={"objid":str})
 keep=["objid","type"]+[c for c in p if c.startswith(("psfmag_","modelmag_"))];x=x.merge(p[keep],on="objid",how="left",suffixes=("","_photo"))
 grp={k:g for k,g in a.groupby("objid")}
 rows=[]
 for _,r in x.iterrows():
  oid=str(r.objid); streams={}; support=dict.fromkeys(CLASSES,0.0); total=0.0
  spec=str(r.get("spectrum_class","")).strip().upper()
  if spec in {"STAR","GALAXY","QSO"}:
   v={"STAR":[1,0,0],"GALAXY":[0,1,0],"QSO":[0,0,1]}[spec];streams["spectroscopy"]={"observed":True,"vector":v,"weight":10};total+=10
   for c,q in zip(CLASSES,v):support[c]+=10*q
  else:streams["spectroscopy"]={"observed":False,"vector":None,"weight":0}
  typ=r.get("type")
  if pd.notna(typ):
   v=[.55,.15,.30] if int(float(typ))==6 else [.05,.80,.15] if int(float(typ))==3 else [.33,.34,.33]
   streams["sdss_morphology"]={"observed":True,"vector":v,"weight":4};total+=4
   for c,q in zip(CLASSES,v):support[c]+=4*q
  if str(r.get("final_classification",""))=="STAR":
   v=[.95,.03,.02];streams["gaia_astrometry"]={"observed":True,"vector":v,"weight":8};total+=8
   for c,q in zip(CLASSES,v):support[c]+=8*q
  else:streams["gaia_astrometry"]={"observed":False,"vector":None,"weight":0}
  ag=grp.get(oid)
  statuses={} if ag is None else dict(zip(ag.survey,ag.association_status_v3))
  templates={"GALEX":([.15,.45,.40],2.5),"2MASS":([.45,.45,.10],1.5),"AllWISE":([.20,.40,.40],2.5),"NVSS":([.03,.37,.60],4),"FIRST":([.03,.32,.65],4),"XMM":([.10,.20,.70],5)}
  for sv,(v,w) in templates.items():
   st=statuses.get(sv,"NOT_OBSERVED_OR_NO_ASSOCIATION")
   if st=="PROBABLE":
    streams[sv]={"observed":True,"association":"PROBABLE","vector":v,"weight":w};total+=w
    for c,q in zip(CLASSES,v):support[c]+=w*q
   else:streams[sv]={"observed":st not in {"NOT_OBSERVED_OR_NO_ASSOCIATION","not_observed"},"association":st,"vector":None,"weight":0}
  raw=np.array([support[c]/total if total else 1/3 for c in CLASSES]);lv=raw/raw.sum()
  top=int(np.argmax(lv));ordered=np.sort(lv);margin=float(ordered[-1]-ordered[-2])
  label=CLASSES[top] if lv[top]>=.65 and margin>=.20 else CLASSES[top]+"_CANDIDATE" if lv[top]>=.48 and margin>=.10 else "UNRESOLVED"
  rows.append({"objid":oid,"ra":r.ra,"dec":r.dec,"likelihood_star":lv[0],"likelihood_galaxy":lv[1],"likelihood_agn":lv[2],"vector_margin":margin,"vector_classification":label,"spectroscopic_anchor":spec if spec in {"STAR","GALAXY","QSO"} else "none","observed_streams":sum(bool(q.get("observed")) for q in streams.values()),"evidence_vector_json":json.dumps(streams),"semantics":"normalized evidence-support vector; not calibrated posterior"})
 z=pd.DataFrame(rows);z.to_csv(O/"likelihood_vectors.csv",index=False)
 z[z.vector_classification.str.contains("UNRESOLVED|CANDIDATE",regex=True)].to_csv(O/"followup_vectors.csv",index=False)
 summary={"objects":len(z),"classes":CLASSES,"counts":z.vector_classification.value_counts().to_dict(),"mean_observed_streams":float(z.observed_streams.mean()),"warning":"Vector components are normalized evidence support, not calibrated posterior probabilities. Next calibration must learn per-survey vectors from spectroscopic reference data and use actual band photometry/fluxes."}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

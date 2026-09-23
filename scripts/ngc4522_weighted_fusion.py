"""Weighted evidence fusion for NGC4522.

Principle: ingest BOTH photometry and spectroscopy when observed. Counterpart evidence
is weighted by diagnostic importance; missing/unobserved data contribute zero, never
negative evidence. Scores are evidence strengths, NOT posterior probabilities.
"""
from __future__ import annotations
import json,pathlib, numpy as np, pandas as pd
B=pathlib.Path("results/ngc4522_field10");F=pathlib.Path("results/ngc4522_final");O=pathlib.Path("results/ngc4522_weighted");O.mkdir(parents=True,exist_ok=True)
WEIGHTS={"spectroscopy":10.0,"gaia_astrometry":8.0,"xray":5.0,"radio":4.0,"morphology":4.0,"uv":2.5,"mir":2.5,"nir":1.5,"optical_photometry":2.0}
def finite(x):
 try:return np.isfinite(float(x))
 except:return False
def main():
 x=pd.read_csv(F/"final_classifications_v3.csv",dtype={"objid":str})
 p=pd.read_csv(B/"sdss_optical_census.csv",dtype={"objid":str})
 g=pd.read_csv(B/"gaia_dr3.csv")
 a=pd.read_csv(F/"associations_v3.csv",dtype={"objid":str})
 # preserve all observed optical photometry; spectrum columns already carried by x
 keep=["objid","type"]+[c for c in p.columns if c.startswith(("psfmag_","modelmag_"))]
 x=x.merge(p[keep],on="objid",how="left",suffixes=("","_photo"))
 prob=a[a.association_status_v3=="PROBABLE"].groupby("objid").survey.apply(lambda v:set(v)).to_dict()
 amb=a[a.association_status_v3=="AMBIGUOUS"].groupby("objid").survey.apply(lambda v:set(v)).to_dict()
 rows=[]
 for _,r in x.iterrows():
  oid=str(r.objid); pb=prob.get(oid,set()); am=amb.get(oid,set())
  scores={"STAR":0.0,"GALAXY":0.0,"AGN":0.0}; ev=[]; counter=[]
  spec=str(r.get("spectrum_class","")).strip().upper()
  if spec in {"STAR","GALAXY","QSO"}:
   k="AGN" if spec=="QSO" else spec;scores[k]+=WEIGHTS["spectroscopy"];ev.append(f"spectroscopy:{spec}(w=10)")
  # Existing Gaia/decision-tree stellar identity is allowed as astrometric evidence.
  if str(r.get("final_classification",""))=="STAR":
   scores["STAR"]+=WEIGHTS["gaia_astrometry"];ev.append("Gaia astrometry/stellar tree(w=8)")
  typ=r.get("type")
  if finite(typ):
   if int(float(typ))==3:scores["GALAXY"]+=WEIGHTS["morphology"];ev.append("SDSS extended morphology(w=4)")
   elif int(float(typ))==6:scores["STAR"]+=1.5;ev.append("SDSS point morphology weak stellar evidence(w=1.5)")
  # Optical photometry is ingested, but without a trained color likelihood it is availability evidence only.
  om=[r.get(c) for c in keep if c.startswith("psfmag_")]
  if sum(finite(v) for v in om)>=3:ev.append("SDSS ugriz photometry observed; awaiting calibrated color likelihood")
  if "GALEX" in pb:scores["GALAXY"]+=1.0;scores["AGN"]+=1.5;ev.append("GALEX UV probable(w<=2.5)")
  if "2MASS" in pb:scores["STAR"]+=0.75;scores["GALAXY"]+=0.5;ev.append("2MASS NIR probable(w<=1.5)")
  if "AllWISE" in pb:scores["GALAXY"]+=0.75;scores["AGN"]+=1.25;ev.append("AllWISE MIR probable(w<=2.5)")
  if "NVSS" in pb or "FIRST" in pb:scores["AGN"]+=WEIGHTS["radio"];ev.append("radio probable(w=4)")
  if "XMM" in pb:scores["AGN"]+=WEIGHTS["xray"];ev.append("X-ray probable(w=5)")
  if am:counter.append("ambiguous counterpart:"+",".join(sorted(am)))
  order=sorted(scores,key=scores.get,reverse=True);top,second=order[:2];margin=scores[top]-scores[second]
  if spec in {"STAR","GALAXY","QSO"}: label={"QSO":"AGN/QSO"}.get(spec,spec);conf="HIGH"
  elif scores[top]>=8 and margin>=3:label=top;conf="HIGH"
  elif scores[top]>=4 and margin>=2:label=top+"_CANDIDATE";conf="MODERATE"
  else:label="UNRESOLVED";conf="LOW"
  rows.append({**r.to_dict(),"weighted_classification":label,"weighted_confidence":conf,"star_evidence_score":scores["STAR"],"galaxy_evidence_score":scores["GALAXY"],"agn_evidence_score":scores["AGN"],"evidence_margin":margin,"evidence":"; ".join(ev),"counter_evidence":"; ".join(counter) or "none","missing_decisive_data":"calibrated photometric likelihood / spectrum" if spec not in {"STAR","GALAXY","QSO"} else "none","score_semantics":"weighted evidence, not posterior probability"})
 z=pd.DataFrame(rows);z.to_csv(O/"weighted_classifications.csv",index=False)
 z[z.weighted_classification.str.contains("UNRESOLVED|CANDIDATE",regex=True)].to_csv(O/"followup_candidates.csv",index=False)
 summary={"objects":len(z),"weights":WEIGHTS,"counts":z.weighted_classification.value_counts().to_dict(),"confidence":z.weighted_confidence.value_counts().to_dict(),"warning":"Evidence scores are rule weights, not calibrated posterior probabilities. Photometry is ingested; survey-band flux/color likelihoods need calibration before full weight is used."}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

"""Rank unresolved NGC4522 sources for follow-up without inventing posterior probabilities."""
import json,pathlib,math
import numpy as np,pandas as pd
B=pathlib.Path("results/ngc4522_field10"); F=pathlib.Path("results/ngc4522_final"); O=pathlib.Path("results/ngc4522_followup");O.mkdir(parents=True,exist_ok=True)
def main():
 x=pd.read_csv(F/"final_classifications_v3.csv",dtype={"objid":str})
 opt=pd.read_csv(B/"sdss_optical_census.csv",dtype={"objid":str})
 z=x.merge(opt,on="objid",how="left",suffixes=("","_opt"))
 z=z[z.final_classification.isin(["UNKNOWN","AMBIGUOUS"])].copy()
 # Evidence-availability priority, deliberately not a calibrated anomaly probability.
 bands=[c for c in ["GALEX_probable","2MASS_probable","AllWISE_probable","NVSS_probable","FIRST_probable","XMM_probable"] if c in z]
 z["n_probable_bands"]=z[bands].gt(0).sum(axis=1)
 # SDSS color outlier relative to unresolved pool when usable.
 mags=[c for c in ["psfMag_u","psfMag_g","psfMag_r","psfMag_i","psfMag_z"] if c in z]
 cols=[]
 for a,b in zip(mags[:-1],mags[1:]):
  n=f"{a}-{b}";z[n]=pd.to_numeric(z[a],errors="coerce")-pd.to_numeric(z[b],errors="coerce");cols.append(n)
 score=np.zeros(len(z))
 for c in cols:
  v=z[c];med=v.median();mad=(v-med).abs().median()
  if np.isfinite(mad) and mad>0: score+=((v-med).abs()/(1.4826*mad)).clip(0,10).fillna(0)
 z["photometric_outlier_score"]=score/max(len(cols),1)
 z["followup_priority_score"]=z["photometric_outlier_score"]+0.75*z["n_probable_bands"]
 z["likely_object_type"]="UNRESOLVED"
 z["evidence"]=z.apply(lambda r:";".join([s.replace("_probable","") for s in bands if r[s]>0]) or "optical_only",axis=1)
 z["counter_evidence"]="No decisive spectroscopy/identity evidence in current pipeline"
 z["uncertainty"]="HIGH: ranking is heuristic, not calibrated probability"
 z=z.sort_values("followup_priority_score",ascending=False)
 z.to_csv(O/"unknown_ambiguous_ranked.csv",index=False)
 z.head(50).to_csv(O/"top50_followup.csv",index=False)
 summary={"pool":len(z),"unknown":int((z.final_classification=="UNKNOWN").sum()),"ambiguous":int((z.final_classification=="AMBIGUOUS").sum()),"with_probable_multiwave":int((z.n_probable_bands>0).sum()),"top_score":float(z.followup_priority_score.max()) if len(z) else None,"warning":"Priority score is heuristic and must not be interpreted as anomaly probability."}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

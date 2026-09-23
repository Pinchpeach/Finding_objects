"""Fuse SDSS spectroscopy with validated multiwavelength evidence for NGC4522 classification."""
import json,pathlib,math
import numpy as np,pandas as pd
B=pathlib.Path("results/ngc4522_field10");F=pathlib.Path("results/ngc4522_final");M=pathlib.Path("results/ngc4522_multiwavelength");O=pathlib.Path("results/ngc4522_fused");O.mkdir(parents=True,exist_ok=True)
def main():
 x=pd.read_csv(F/"final_classifications_v3.csv",dtype={"objid":str}); p=pd.read_csv(B/"sdss_optical_census.csv",dtype={"objid":str})
 s=pd.read_csv(B/"sdss_spectroscopy.csv"); a=pd.read_csv(F/"associations_v3.csv",dtype={"objid":str})
 x=x.merge(p[["objid","type","psfmag_u","psfmag_g","psfmag_r","psfmag_i","psfmag_z"]],on="objid",how="left")
 # Only probable associations enter positive evidence. Ambiguous remain counter/uncertainty evidence.
 prob=a[a.association_status_v3=="PROBABLE"].groupby("objid").survey.apply(lambda q:set(q)).to_dict()
 amb=a[a.association_status_v3=="AMBIGUOUS"].groupby("objid").survey.apply(lambda q:set(q)).to_dict()
 out=[]
 for _,r in x.iterrows():
  oid=str(r.objid); pb=prob.get(oid,set()); am=amb.get(oid,set()); spec=str(r.get("spectrum_class","")).upper()
  morph="extended" if pd.notna(r.get("type")) and int(r["type"])==3 else "pointlike"
  ev=[];counter=[];missing=[]
  if spec in {"STAR","GALAXY","QSO"}:
   cls={"QSO":"AGN/QSO"}.get(spec,spec); conf="HIGH"; ev.append("SDSS spectrum:"+spec)
   if pd.notna(r.get("redshift")):ev.append("z="+str(r.redshift))
  else:
   # Identity fusion: morphology first, then Gaia-derived existing tree identity, then multiwave characterization.
   old=str(r.final_classification)
   if old=="STAR": cls="STAR";conf="MODERATE";ev.append("Gaia/decision-tree stellar evidence")
   elif morph=="extended":
    cls="GALAXY_CANDIDATE";conf="MODERATE";ev.append("SDSS extended morphology")
   else:
    cls="UNRESOLVED_POINT_SOURCE";conf="LOW";ev.append("SDSS pointlike morphology")
   if "GALEX" in pb:ev.append("probable GALEX UV counterpart")
   if "AllWISE" in pb:ev.append("probable AllWISE IR counterpart")
   if "2MASS" in pb:ev.append("probable 2MASS NIR counterpart")
   if "NVSS" in pb or "FIRST" in pb:
    ev.append("probable radio counterpart")
    if cls=="GALAXY_CANDIDATE":cls="RADIO_GALAXY_OR_AGN_CANDIDATE"
    elif cls=="UNRESOLVED_POINT_SOURCE":cls="AGN_OR_RADIO_SOURCE_CANDIDATE"
   if "XMM" in pb:
    ev.append("probable X-ray counterpart")
    if cls!="STAR":cls="AGN_CANDIDATE"
   missing.append("diagnostic spectrum" if not spec or spec=="NAN" else "")
  if am:counter.append("ambiguous counterpart:"+",".join(sorted(am)))
  # No WISE color cuts here: candidate table currently carries association, not reliable band photometry.
  out.append({**r.to_dict(),"fused_classification":cls,"fused_confidence":conf,"evidence":"; ".join(ev),"counter_evidence":"; ".join(counter) or "none","missing_decisive_data":"; ".join(q for q in missing if q) or "none","probable_surveys":";".join(sorted(pb)) or "none","ambiguous_surveys":";".join(sorted(am)) or "none"})
 z=pd.DataFrame(out);z.to_csv(O/"fused_classifications.csv",index=False)
 unresolved=z[z.fused_classification.str.contains("UNRESOLVED|CANDIDATE",regex=True,na=False)].copy();unresolved.to_csv(O/"fused_candidates.csv",index=False)
 summary={"objects":len(z),"fused_counts":z.fused_classification.value_counts().to_dict(),"confidence_counts":z.fused_confidence.value_counts().to_dict(),"remaining_candidate_or_unresolved":len(unresolved),"spectroscopic_high_confidence":int((z.fused_confidence=="HIGH").sum()),"note":"Multiwavelength evidence refines identity only when association_v3 is PROBABLE. No calibrated posterior or unsupported color diagnosis is claimed."}
 json.dump(summary,open(O/"summary.json","w"),indent=2);json.dump({"stage":"complete",**summary},open(O/"checkpoint.json","w"),indent=2);print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

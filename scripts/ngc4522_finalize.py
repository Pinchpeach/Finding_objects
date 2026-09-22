"""NGC4522 association calibration and final evidence-aware classification."""
import json,math,pathlib,traceback
import numpy as np,pandas as pd
from finding_objects.survey_specs import SURVEY_SPECS
BASE=pathlib.Path("results/ngc4522_field10"); MW=pathlib.Path("results/ngc4522_multiwavelength"); OUT=pathlib.Path("results/ngc4522_final");OUT.mkdir(parents=True,exist_ok=True)
AREA=math.pi*15**2*3600 # arcsec^2 for 15 arcmin query circle
def save(**x):
 p=OUT/"checkpoint.json";d={}
 if p.exists():
  try:d=json.load(open(p))
  except:pass
 d.update(x);json.dump(d,open(p,"w"),indent=2,default=str)
def main():
 base=pd.read_csv(BASE/"final_classifications.csv",dtype={"objid":str}); assoc=pd.read_csv(MW/"candidate_associations.csv",dtype={"objid":str}); summ=json.load(open(MW/"summary.json"))
 rows=[]
 for _,r in assoc.iterrows():
  s=r.survey;sp=SURVEY_SPECS[s]; n=float(summ.get(s,{}).get("field_rows",0));rho=n/AREA
  fwhm=sp.get("fwhm_arcsec")
  if fwhm is None: ppos=np.nan
  else:
   sigma=fwhm/2.355;ppos=math.exp(-.5*(float(r.separation_arcsec)/sigma)**2)
  pchance=1-math.exp(-rho*math.pi*float(r.separation_arcsec)**2)
  score=np.nan if not np.isfinite(ppos) else ppos*(1-pchance)
  status="UNRESOLVED"
  if np.isfinite(score): status="PROBABLE" if score>=.9 else ("REJECT_POSITIONAL" if score<.2 else "AMBIGUOUS")
  rows.append({**r.to_dict(),"official_fwhm_arcsec":fwhm,"local_density_arcsec2":rho,"p_chance":pchance,"positional_likelihood":ppos,"spec_calibrated_score":score,"association_status_v3":status,"official_spec_url":sp["official"],"calibration_note":"Resolution+density diagnostic, not an empirically calibrated posterior; per-source covariance/flux priors still required."})
 a=pd.DataFrame(rows);a.to_csv(OUT/"associations_v3.csv",index=False);save(association_rows=len(a))
 probable=a[a.association_status_v3=="PROBABLE"].groupby(["objid","survey"]).size().unstack(fill_value=0) if len(a) else pd.DataFrame()
 out=base.copy()
 for s in ["GALEX","2MASS","AllWISE","NVSS","FIRST","XMM"]:out[f"{s}_probable"]=out.objid.map(probable[s] if s in probable else {}).fillna(0).astype(int)
 # Preserve spectroscopy as strongest identity; multi-band evidence refines characterization only.
 def refine(r):
  ident=str(r.get("final_classification","UNKNOWN")); ev=[]
  for s in ["GALEX","2MASS","AllWISE","NVSS","FIRST","XMM"]:
   if r[f"{s}_probable"]>0:ev.append(s)
  likely=ident
  if ident=="QSO":likely="QSO/AGN"
  elif ident=="GALAXY" and ("NVSS" in ev or "FIRST" in ev):likely="GALAXY_WITH_RADIO_COUNTERPART"
  elif ident=="GALAXY" and "GALEX" in ev:likely="UV_DETECTED_GALAXY"
  elif ident=="STAR" and "AllWISE" in ev:likely="STAR_WITH_IR_COUNTERPART"
  return pd.Series([likely,";".join(ev) if ev else "none","HIGH" if str(r.get("basis",""))=="SDSS_DR18_SPECTROSCOPY" else ("MODERATE" if ev else str(r.get("confidence","LOW")))])
 out[["likely_object_type_v3","multiwavelength_evidence","confidence_v3"]]=out.apply(refine,axis=1)
 out.to_csv(OUT/"final_classifications_v3.csv",index=False)
 summary={"objects":len(out),"identity_counts":out.final_classification.value_counts(dropna=False).to_dict(),"likely_type_counts":out.likely_object_type_v3.value_counts(dropna=False).to_dict(),"probable_associations":a[a.association_status_v3=="PROBABLE"].survey.value_counts().to_dict(),"ambiguous_associations":a[a.association_status_v3=="AMBIGUOUS"].survey.value_counts().to_dict(),"rejected_positional":a[a.association_status_v3=="REJECT_POSITIONAL"].survey.value_counts().to_dict(),"warning":"spec_calibrated_score is not a validated posterior probability; official footprint maps/per-source errors and held-out reliability calibration remain required."}
 json.dump(summary,open(OUT/"summary.json","w"),indent=2);save(stage="complete");print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:save(stage="failed",error=repr(e),traceback=traceback.format_exc());raise

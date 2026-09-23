from pathlib import Path
import json,math,time,pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.vizier import Vizier
from finding_objects.association import chance_coincidence_probability,likelihood_ratio,posterior_counterpart_probability
SRC=Path("data/method2ref/spectroscopic_reference_objects.csv"); OUT=Path("results/method2_300_counterparts_v2")
SURVEYS={"GALEX":("II/335/galex_ais",5.,5.),"Pan-STARRS_DR1":("II/349/ps1",3.,1.1),"2MASS":("II/246/out",5.,2.5),"AllWISE":("II/328/allwise",8.,6.1),"NVSS":("VIII/65/nvss",60.,45.),"FIRST":("VIII/92/first14",15.,5.),"Planck_PCCS2":("VIII/100/pcnt",600.,300.),"XMM_4XMM":("IX/65/xmm4dr13s",20.,6.)}
PRIORS={"GALEX":.6,"Pan-STARRS_DR1":.95,"2MASS":.6,"AllWISE":.9,"NVSS":.15,"FIRST":.15,"Planck_PCCS2":.02,"XMM_4XMM":.1}
def q(v,c,cat,rad):
 err=""
 for a in range(5):
  try:
   z=v.query_region(c,radius=rad*u.arcsec,catalog=cat); return (z[0] if len(z) else None),""
  except Exception as e: err=str(e); time.sleep(min(20,2**a))
 return None,err
def main():
 OUT.mkdir(parents=True,exist_ok=True); src=pd.read_csv(SRC,dtype={"objid":str}); v=Vizier(columns=["*","_r"],row_limit=200); v.TIMEOUT=60; rows=[]
 for _,r in src.iterrows():
  c=SkyCoord(float(r.ra)*u.deg,float(r.dec)*u.deg)
  for sv,(cat,rad,beam) in SURVEYS.items():
   local,err=q(v,c,cat,3600.)
   if err: rows.append({"objid":r.objid,"survey":sv,"status":"no_response","error":err}); continue
   if local is None or len(local)==0: rows.append({"objid":r.objid,"survey":sv,"status":"not_observed","coverage_method":"1deg_catalog_probe"}); continue
   rho=len(local)/(math.pi*3600**2); sat=len(local)>=200; near,err=q(v,c,cat,rad)
   if err: rows.append({"objid":r.objid,"survey":sv,"status":"no_response","error":err}); continue
   if near is None or len(near)==0: rows.append({"objid":r.objid,"survey":sv,"status":"observed_no_counterpart","local_density_per_sq_arcsec":rho,"density_lower_bound":sat}); continue
   for rank,x in enumerate(near[:5],1):
    sep=float(x["_r"]); sigma=beam/2.355; lr=likelihood_ratio(sep,sigma,rho); p=posterior_counterpart_probability(lr,PRIORS[sv])
    status="probable_counterpart" if p>=.9 else ("likely_not_same_object" if p<.2 else "ambiguous")
    rows.append({"objid":r.objid,"survey":sv,"status":status,"rank":rank,"separation_arcsec":sep,"beam_fwhm_arcsec":beam,"local_density_per_sq_arcsec":rho,"density_lower_bound":sat,"chance_coincidence_probability":chance_coincidence_probability(rho,sep),"likelihood_ratio":lr,"counterpart_prior_Q":PRIORS[sv],"counterpart_posterior_probability":p,"probability_method":"positional_LR_Bayes","coverage_method":"1deg_catalog_probe"})
 d=pd.DataFrame(rows); d.to_csv(OUT/"counterpart_validation.csv",index=False)
 summary={"objects":len(src),"status_counts":d.status.value_counts().to_dict(),"survey_status_counts":d.groupby(["survey","status"]).size().unstack(fill_value=0).to_dict(orient="index"),"method":"2D Gaussian positional likelihood ratio vs local Poisson background, converted to Bayesian posterior with explicit survey Q prior.","limitations":["1-degree catalog probe is a coverage proxy, not an official footprint mask.","Density is a lower bound when VizieR row limit saturates; flagged in output.","Beam FWHM substitutes for per-source astrometric uncertainty when unavailable.","Probabilities depend on provisional Q priors and require calibration on held-out confirmed matches.","Position-only posterior must later incorporate SED, morphology, redshift and variability evidence."]}
 (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__":main()

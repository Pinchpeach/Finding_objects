"""Method 2 stage 4: retrieve multiwavelength counterpart candidates for the 300 spectroscopy-first reference objects."""
from pathlib import Path
import json,time
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.vizier import Vizier

SRC=Path("data/method2ref/spectroscopic_reference_objects.csv"); OUT=Path("results/method2_300_counterparts")
SURVEYS={
"GALEX":("II/335/galex_ais",5.0), "Pan-STARRS_DR1":("II/349/ps1",3.0),
"2MASS":("II/246/out",5.0), "AllWISE":("II/328/allwise",8.0),
"NVSS":("VIII/65/nvss",60.0), "FIRST":("VIII/92/first14",15.0),
"Planck_PCCS2":("VIII/100/pcnt",600.0), "XMM_4XMM":("IX/65/xmm4dr13s",20.0)}
BEAM={"GALEX":5.0,"Pan-STARRS_DR1":1.1,"2MASS":2.5,"AllWISE":6.1,"NVSS":45.0,"FIRST":5.0,"Planck_PCCS2":300.0,"XMM_4XMM":6.0}
def main():
 OUT.mkdir(parents=True,exist_ok=True); src=pd.read_csv(SRC,dtype={"objid":str}); rows=[]
 v=Vizier(columns=["*","_r"],row_limit=5); v.TIMEOUT=60
 for i,r in src.iterrows():
  c=SkyCoord(float(r.ra)*u.deg,float(r.dec)*u.deg)
  for sv,(cat,rad) in SURVEYS.items():
   tab=None; err=""
   for a in range(5):
    try:
     q=v.query_region(c,radius=rad*u.arcsec,catalog=cat); tab=q[0] if len(q) else None; break
    except Exception as ex:
     err=str(ex); time.sleep(min(20,2**a))
   if tab is None or len(tab)==0:
    rows.append({"objid":r.objid,"survey":sv,"status":"no_response" if err else "no_candidate","search_radius_arcsec":rad,"error":err}); continue
   for rank,x in enumerate(tab[:5],1):
    sep=float(x["_r"]) if "_r" in tab.colnames else float("nan"); beam=BEAM[sv]; norm=sep/(beam/2.355)
    rows.append({"objid":r.objid,"survey":sv,"status":"candidate","rank":rank,"separation_arcsec":sep,"search_radius_arcsec":rad,"beam_fwhm_arcsec":beam,"normalized_sep_beam_sigma":norm,"positional_score":float(__import__("math").exp(-.5*norm*norm))})
 pd.DataFrame(rows).to_csv(OUT/"counterpart_candidates.csv",index=False)
 d=pd.DataFrame(rows); cand=d[d.status=="candidate"]; summary={"objects":len(src),"queries":len(src)*len(SURVEYS),"candidate_rows":len(cand),"objects_with_candidate":int(cand.objid.nunique()),"survey_candidate_objects":cand.groupby("survey").objid.nunique().to_dict(),"notes":["Candidate means a catalog source was found within the survey-specific radius, not that physical identity is confirmed.","Positional score is a beam-scaled triage score, not posterior probability.","Final validation must consider local source density/chance coincidence, SED consistency and morphology/variability where available."]}
 (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__":main()

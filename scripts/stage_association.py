"""Stage 2: turn catalog-radius hits into conservative association evidence."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from finding_objects.association import association_score

IN=Path("data/batch1000_multi/multisurvey_status.csv")
OUT=Path("results/stages/02_association")
PSF={"GALEX":5.0,"Pan-STARRS_DR1":1.1,"2MASS":2.5,"AllWISE":6.1,"NVSS":45.0,"FIRST":5.0,"Planck_PCCS2":300.0,"XMM_4XMM":6.0}
def main():
    d=pd.read_csv(IN,dtype={"objid":str}); rows=[]
    for _,r in d.iterrows():
        sep=r.get("separation_arcsec")
        if r.status!="available" or pd.isna(sep):
            status="no_candidate" if r.status=="not_observed" else r.status
            rows.append({**r.to_dict(),"association_status":status,"positional_score":None}); continue
        ev=association_score(float(sep),source_poserr_arcsec=0.2,counterpart_poserr_arcsec=None,source_beam_arcsec=PSF.get(r.survey))
        score=float(ev.get("positional_likelihood",0.0))
        status="strong_positional_candidate" if score>=0.5 else "weak_positional_candidate"
        rows.append({**r.to_dict(),"association_status":status,"positional_score":score})
    OUT.mkdir(parents=True,exist_ok=True); out=pd.DataFrame(rows); out.to_csv(OUT/"associations.csv",index=False)
    s=out.groupby(["survey","association_status"]).size().unstack(fill_value=0)
    s.to_csv(OUT/"summary_by_survey.csv")
    (OUT/"README.txt").write_text("Positional triage only. Scores are not posterior probabilities; no source identity is asserted. Current no_candidate may include lack of survey coverage.\n")
if __name__=="__main__":main()

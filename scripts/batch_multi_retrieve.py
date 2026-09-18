"""Enrich the 1000-object SDSS sample with multiwavelength catalog presence.

Acquisition-first stage: preserve response/coverage states and retry transient errors.
"""
from __future__ import annotations
import json, time
from pathlib import Path
import pandas as pd
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u

INPUT=Path("data/batch1000/sample.csv")
OUT=Path("results/batch1000_multi")
CHECK=OUT/"checkpoint.jsonl"
TIMEOUT=45
SURVEYS={
 "GALEX":("II/335/galex_ais",5.0),
 "Pan-STARRS_DR1":("II/349/ps1",5.0),
 "2MASS":("II/246/out",5.0),
 "AllWISE":("II/328/allwise",5.0),
 "NVSS":("VIII/65/nvss",30.0),
 "FIRST":("VIII/92/first14",10.0),
 "Planck_PCCS2":("VIII/100/pcnt",300.0),
 "XMM_4XMM":("IX/65/xmm4dr13s",15.0),
}
def append(rec):
    OUT.mkdir(parents=True,exist_ok=True)
    with CHECK.open("a",encoding="utf-8") as f:f.write(json.dumps(rec)+"\n")
def lookup(coord,catalog,radius,retries=5):
    last=None
    for n in range(retries+1):
        try:
            Vizier.TIMEOUT=TIMEOUT
            t=Vizier(columns=["*","+_r"],row_limit=5).query_region(coord,radius=radius*u.arcsec,catalog=catalog)
            if not t or len(t[0])==0:return {"status":"not_observed","separation_arcsec":None}
            tab=t[0]; j=0
            if "_r" in tab.colnames:
                import numpy as np
                j=int(np.nanargmin(np.asarray(tab["_r"],dtype=float)))
                sep=float(tab["_r"][j])
            else: sep=None
            return {"status":"available","separation_arcsec":sep}
        except Exception as e:
            last=e
            if n<retries:time.sleep(min(30,2**n))
    return {"status":"no_response","error":str(last)}
def main():
    df=pd.read_csv(INPUT,dtype={"objid":str})
    done=set()
    if CHECK.exists():
        for line in CHECK.read_text().splitlines():
            if line.strip():
                x=json.loads(line)
                if x.get("terminal"):done.add((x["objid"],x["survey"]))
    for _,r in df.iterrows():
        coord=SkyCoord(float(r.ra)*u.deg,float(r.dec)*u.deg)
        for survey,(catalog,radius) in SURVEYS.items():
            key=(r.objid,survey)
            if key in done:continue
            ans=lookup(coord,catalog,radius)
            append({"objid":r.objid,"ra":float(r.ra),"dec":float(r.dec),"survey":survey,"radius_arcsec":radius,**ans,"terminal":ans["status"]!="no_response"})
    records=[json.loads(x) for x in CHECK.read_text().splitlines() if x.strip()]
    pd.DataFrame(records).to_csv(OUT/"multisurvey_status.csv",index=False)
    latest={}
    for x in records:latest[(x["objid"],x["survey"])]=x
    pending=[x for x in latest.values() if x["status"]=="no_response"]
    summary={"objects":len(df),"survey_queries_expected":len(df)*len(SURVEYS),"terminal_queries":sum(x["status"]!="no_response" for x in latest.values()),"no_response":len(pending),"complete":len(latest)==len(df)*len(SURVEYS) and not pending}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
    if not summary["complete"]:raise SystemExit(2)
if __name__=="__main__":main()

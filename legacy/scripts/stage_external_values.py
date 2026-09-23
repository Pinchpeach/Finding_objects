"""Stage 4: retrieve actual values for external catalog counterparts with resume."""
from pathlib import Path
import json,time
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.vizier import Vizier

BASE=Path("data/batch1000/sample.csv"); NEED=Path("data/stage03/external_photometry_needed.csv")
OUT=Path("results/stages/04_external_values"); CHECK=OUT/"checkpoint.jsonl"
SPECS={
"GALEX":("II/335/galex_ais",5.0,["FUVmag","NUVmag"]),
"Pan-STARRS_DR1":("II/349/ps1",5.0,["gmag","rmag","imag","zmag","ymag"]),
"2MASS":("II/246/out",5.0,["Jmag","Hmag","Kmag"]),
"AllWISE":("II/328/allwise",5.0,["W1mag","W2mag","W3mag","W4mag"]),
"NVSS":("VIII/65/nvss",30.0,["S1.4"]),
"FIRST":("VIII/92/first14",10.0,["Fpeak","Fint"])}
def scalar(v):
    try:
        if getattr(v,"mask",False): return None
        return v.item() if hasattr(v,"item") else v
    except: return None
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base=pd.read_csv(BASE,dtype={"objid":str}).set_index("objid")
    need=pd.read_csv(NEED,dtype={"objid":str})
    done=set()
    if CHECK.exists():
        for line in CHECK.read_text().splitlines():
            try:
                x=json.loads(line)
                if x.get("terminal"): done.add((x["objid"],x["survey"]))
            except: pass
    v=Vizier(columns=["*","_r"]); v.TIMEOUT=45
    with CHECK.open("a") as f:
      for _,r in need.iterrows():
        key=(str(r.objid),str(r.survey))
        if key in done or r.survey not in SPECS: continue
        cat,rad,cols=SPECS[r.survey]; b=base.loc[key[0]]; rec={"objid":key[0],"survey":key[1],"terminal":False}
        for attempt in range(6):
          try:
            q=v.query_region(SkyCoord(float(b.ra)*u.deg,float(b.dec)*u.deg),radius=rad*u.arcsec,catalog=cat)
            if not q: rec.update(status="no_counterpart",terminal=True); break
            t=q[0]; row=t[0]; rec["status"]="available"; rec["terminal"]=True
            rec["separation_arcsec"]=scalar(row["_r"]) if "_r" in t.colnames else None
            for col in cols:
                rec[col]=scalar(row[col]) if col in t.colnames else None
            break
          except Exception as e:
            rec.update(status="no_response",error=type(e).__name__)
            time.sleep(min(2**attempt,20))
        f.write(json.dumps(rec,default=str)+"\n"); f.flush()
    latest={}
    for line in CHECK.read_text().splitlines():
      x=json.loads(line); latest[(x["objid"],x["survey"])]=x
    pd.DataFrame(latest.values()).to_csv(OUT/"external_values.csv",index=False)
    n=sum(x.get("terminal",False) for x in latest.values())
    summary={"requested_pairs":len(need),"terminal_pairs":n,"remaining":len(need)-n,"complete":n==len(need)}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__":main()

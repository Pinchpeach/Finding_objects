"""Method 2 pilot: build a permanent spectroscopy-first reference dataset from 300 SDSS DR18 spectroscopic objects."""
from pathlib import Path
from io import StringIO
import json, time
import pandas as pd
import requests

OUT=Path("results/method2_300")
SKY="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def sql(q):
    for a in range(6):
        try:
            r=requests.get(SKY,params={"cmd":q,"format":"csv"},timeout=90); r.raise_for_status()
            ls=r.text.lstrip("\ufeff").splitlines(); i=next((i for i,x in enumerate(ls) if "," in x and not x.startswith("#")),None)
            return pd.read_csv(StringIO("\n".join(ls[i:])),dtype=str) if i is not None else pd.DataFrame()
        except Exception:
            if a==5: return pd.DataFrame()
            time.sleep(min(30,2**a))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Deterministic, balanced pilot: 100 GALAXY, 100 QSO, 100 STAR with valid bestobjid and redshift.
    parts=[]
    for cls in ("GALAXY","QSO","STAR"):
        q=f"""SELECT TOP 100 s.bestobjid as objid,s.specobjid,s.ra,s.dec,s.z as redshift,s.zErr,s.class,s.subclass,s.snMedian,s.plate,s.mjd,s.fiberid
        FROM SpecObj s WHERE s.class='{cls}' AND s.bestobjid>0 AND s.zWarning=0 AND s.snMedian>3
        ORDER BY s.specobjid"""
        d=sql(q)
        if len(d): parts.append(d)
    sp=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    sp.to_csv(OUT/"spectroscopic_reference_objects.csv",index=False)

    lines=[]
    ids=sp.objid.astype(str).tolist()
    for st in range(0,len(ids),50):
        ins=",".join(ids[st:st+50])
        q=f"""SELECT s.bestobjid as objid,l.specobjid,l.lineName,l.wave,l.waveErr,l.sigma,l.sigmaErr,l.height,l.heightErr,l.ew,l.ewErr,l.chi2
        FROM SpecObj s JOIN SpecLine l ON s.specobjid=l.specobjid WHERE s.bestobjid IN ({ins})"""
        d=sql(q)
        if len(d): lines.append(d)
    ln=pd.concat(lines,ignore_index=True) if lines else pd.DataFrame()
    ln.to_csv(OUT/"spectral_lines.csv",index=False)

    labels=[]
    if len(ln):
        for oid,g in ln.groupby("objid"):
            names=sorted(set(str(x).strip() for x in g.lineName.dropna() if str(x).strip()))
            labels.append({"objid":str(oid),"line_tags":"|".join(names),"n_line_rows":len(g)})
    lab=pd.DataFrame(labels,columns=["objid","line_tags","n_line_rows"])
    ref=sp.merge(lab,on="objid",how="left")
    ref["reference_status"]="spectroscopy_verified"
    ref["dataset_role"]="permanent_reference"
    ref["counterpart_validation_status"]="pending_multiwavelength_validation"
    ref.to_csv(OUT/"permanent_reference_seed.csv",index=False)
    summary={"requested":300,"retrieved":len(sp),"class_counts":sp["class"].value_counts().to_dict() if len(sp) else {},"objects_with_line_rows":int(lab.objid.nunique()) if len(lab) else 0,"line_rows":len(ln),"counterpart_stage":"pending","reference_policy":"Only spectroscopy-verified objects enter the permanent reference seed; Method-1 predictions are never auto-promoted."}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__": main()

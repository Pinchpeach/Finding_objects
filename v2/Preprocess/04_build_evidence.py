#!/usr/bin/env python3
"""Stage 4: convert extracted features into traceable per-rule evidence.

No final classification is made here. Missing measurements are neutral and
conflicting evidence is preserved for Stage 5.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import pandas as pd

PRIMARY=("STAR","WD","GALAXY","QSO","BINARY")

def num(row,name):
    try:
        v=float(row.get(name))
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):
        return None

def add(ev, cls, rule, score, kind, note=""):
    ev.append({"class":cls,"rule_id":rule,"score":float(max(0,min(1,score))),
               "kind":kind,"note":note})

def evidence_for(row):
    ev=[]
    p,pe=num(row,"parallax"),num(row,"parallax_error")
    if p is not None and pe and pe>0:
        corrected=abs((p+0.017)/pe)
        if corrected<5:
            add(ev,"EXTRAGALACTIC","AST-EXT-001",1-corrected/5,"support")
        snr=abs(p/pe)
        add(ev,"STAR","AST-GAL-001",snr/(snr+5),"support",
            "continuous uncalibrated astrometric evidence")
    pmra,era=num(row,"pmra"),num(row,"pmra_error")
    pmdec,edec=num(row,"pmdec"),num(row,"pmdec_error")
    if None not in (pmra,era,pmdec,edec) and era>0 and edec>0:
        s=math.sqrt((pmra/era)**2+(pmdec/edec)**2)
        if s<5:
            add(ev,"EXTRAGALACTIC","AST-EXT-002",1-s/5,"support",
                "covariance-unavailable approximation")
        add(ev,"STAR","AST-GAL-002",s/(s+5),"support",
            "continuous uncalibrated astrometric evidence")
    spectral=str(row.get("class","")).strip().upper()
    if spectral=="STAR": add(ev,"STAR","SPC-SDSS-001",1,"catalog_label")
    elif spectral=="GALAXY": add(ev,"GALAXY","SPC-SDSS-002",1,"catalog_label")
    elif spectral in {"QSO","QUASAR"}: add(ev,"QSO","SPC-SDSS-003",1,"catalog_label")
    aliases={"QSO":"classprob_dsc_combmod_quasar","GALAXY":"classprob_dsc_combmod_galaxy",
             "STAR":"classprob_dsc_combmod_star","WD":"classprob_dsc_combmod_whitedwarf",
             "BINARY":"classprob_dsc_combmod_binarystar"}
    for cls,name in aliases.items():
        v=num(row,name)
        if v is not None: add(ev,cls,"DSC-001",v,"catalog_probability")
    return ev

def run(features: Path, out: Path) -> Path:
    df=pd.read_csv(features); result=df.copy()
    evidence=[]; conflicts=[]; counts=[]
    for _,row in df.iterrows():
        ev=evidence_for(row); evidence.append(json.dumps(ev,separators=(",",":")))
        strong={e["class"] for e in ev if e["score"]>=0.8 and e["class"] in PRIMARY}
        conflicts.append(int(len(strong)>1)); counts.append(len(ev))
    result["evidence_json"]=evidence
    result["evidence_count"]=counts
    result["evidence_conflict"]=conflicts
    out.parent.mkdir(parents=True,exist_ok=True); result.to_csv(out,index=False)
    print(f"[OK] {len(result)} sources -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--features",type=Path,default=root/"features.csv")
    p.add_argument("--out",type=Path,default=root/"evidence.csv")
    a=p.parse_args(); run(a.features,a.out)
if __name__=="__main__": main()

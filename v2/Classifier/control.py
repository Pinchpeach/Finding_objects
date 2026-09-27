#!/usr/bin/env python3
"""Route coarse Preprocess classes to detailed classifier branches."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
BRANCH={"STAR":"star.py","GALAXY":"galaxy.py","QSO":"qso.py"}

def load(name):
    p=ROOT/"branches"/name
    s=importlib.util.spec_from_file_location("detail_"+name.replace(".py",""),p)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def run(inp:Path,out:Path):
    d=pd.read_csv(inp)
    mods={k:load(v) for k,v in BRANCH.items()}
    payload=[]; labels=[]; conf=[]; stellar_family=[]; spectral_type=[]; variability_class=[]
    for _,row in d.iterrows():
        coarse=str(row.get("primary_class","UNKNOWN"))
        if coarse in mods:
            res=mods[coarse].classify(row.to_dict())
        else:
            res={"detailed_class":"UNRESOLVED","confidence":None,
                 "basis":"coarse class UNKNOWN; detailed classification skipped"}
        payload.append(json.dumps(res,separators=(",",":")))
        labels.append(res.get("detailed_class","UNRESOLVED"))
        conf.append(res.get("confidence"))
        stellar_family.append(res.get("stellar_family"))
        spectral_type.append(res.get("spectral_type"))
        var=res.get("variability") if isinstance(res.get("variability"),dict) else {}
        variability_class.append(var.get("class"))
    d["detailed_class"]=labels
    d["detailed_confidence"]=conf
    d["stellar_family"]=stellar_family
    d["spectral_type"]=spectral_type
    d["variability_class"]=variability_class
    d["detailed_result_json"]=payload
    out.parent.mkdir(parents=True,exist_ok=True); d.to_csv(out,index=False)
    print(f"[OK] detailed routing rows={len(d)} -> {out}")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,default=ROOT/"classified_objects.csv")
    a=p.parse_args(); run(a.input,a.out)
if __name__=="__main__": main()

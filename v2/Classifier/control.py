#!/usr/bin/env python3
"""Main detailed-classifier controller.

Runs legacy coarse-class detail branches for compatibility, then all independent
multi-axis classifiers (physical, variability, compact, extragalactic,
phenomenon). One failed/unsupported scientific branch should abstain rather than
invent a class.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
BRANCH={"STAR":"star.py","GALAXY":"galaxy.py","QSO":"qso.py"}

def load_branch(name):
    p=ROOT/"branches"/name
    s=importlib.util.spec_from_file_location("detail_"+name.replace(".py",""),p)
    if s is None or s.loader is None:
        raise ImportError(f"cannot load classifier branch: {p}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def load_axes_controller():
    p=ROOT/"control_axes.py"
    s=importlib.util.spec_from_file_location("classifier_control_axes",p)
    if s is None or s.loader is None:
        raise ImportError(f"cannot load axis controller: {p}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def annotate_legacy(d:pd.DataFrame,rows=None)->pd.DataFrame:
    mods={k:load_branch(v) for k,v in BRANCH.items()}
    payload=[]; labels=[]; conf=[]; stellar_family=[]; spectral_type=[]; variability_class=[]
    for row in (rows if rows is not None else d.to_dict("records")):
        coarse=str(row.get("primary_class","UNKNOWN"))
        if coarse in mods:
            res=mods[coarse].classify(row)
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
    d=d.copy()
    d["detailed_class"]=labels
    d["detailed_confidence"]=conf
    d["stellar_family"]=stellar_family
    d["spectral_type"]=spectral_type
    d["variability_class_legacy"]=variability_class
    d["detailed_result_json"]=payload
    return d

def load_subclass():
    p=ROOT/"subclass.py"
    s=importlib.util.spec_from_file_location("classifier_subclass",p)
    if s is None or s.loader is None:
        raise ImportError(f"cannot load sub-class classifier: {p}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def run(inp:Path,out:Path):
    d=pd.read_csv(inp)
    if "primary_class" not in d.columns:
        raise KeyError("primary_class is required from v2/Preprocess")
    # One dict conversion shared by the legacy branches and the axes; neither
    # reads the other's output columns.
    rows=d.to_dict("records")
    d=annotate_legacy(d,rows)
    d=load_axes_controller().annotate(d,rows)
    # Second stage: literature sub-class per coarse class (needs the physical axis).
    d=load_subclass().annotate(d,rows)
    out.parent.mkdir(parents=True,exist_ok=True); d.to_csv(out,index=False)
    print(f"[OK] full classifier rows={len(d)} axes=5 -> {out}")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,default=ROOT/"classified_objects.csv")
    a=p.parse_args(); run(a.input,a.out)
if __name__=="__main__": main()

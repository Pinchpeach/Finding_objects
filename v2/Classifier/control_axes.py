#!/usr/bin/env python3
"""Run independent classifier axes, then apply conservative per-axis calibration."""
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent;AXES=("physical","variability","compact","extragalactic","phenomenon")
def load_module(path,name):
 s=importlib.util.spec_from_file_location(name,path)
 if s is None or s.loader is None:raise ImportError(path)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def annotate(df:pd.DataFrame)->pd.DataFrame:
 modules={name:load_module(ROOT/"axes"/f"{name}.py",f"classifier_axis_{name}") for name in AXES};additions={}
 rows=df.to_dict("records")  # plain dicts; per-row pandas Series dominated runtime
 for name,module in modules.items():
  results=[module.classify(row) for row in rows]
  additions[f"{name}_class"]=[r["label"] for r in results];additions[f"{name}_subtype"]=[r.get("subtype") for r in results];additions[f"{name}_confidence"]=[r["confidence"] for r in results];additions[f"{name}_status"]=[r["status"] for r in results];additions[f"{name}_evidence_json"]=[json.dumps(r["evidence"],ensure_ascii=False,separators=(",",":")) for r in results]
 result=pd.concat([df.reset_index(drop=True),pd.DataFrame(additions)],axis=1)
 cal=load_module(ROOT/"calibration"/"per_axis.py","classifier_per_axis_calibration")
 return cal.annotate(result,ROOT/"calibration"/"models.json",AXES)
def run(inp:Path,out:Path):
 result=annotate(pd.read_csv(inp));out.parent.mkdir(parents=True,exist_ok=True);result.to_csv(out,index=False);print(f"[OK] full multi-axis classification rows={len(result)} axes={len(AXES)} -> {out}");return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--input",type=Path,default=ROOT/"classifier_input.csv");p.add_argument("--out",type=Path,default=ROOT/"multi_axis_classification.csv");a=p.parse_args();run(a.input,a.out)
if __name__=="__main__":main()

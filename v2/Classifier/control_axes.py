#!/usr/bin/env python3
"""Run independent classifier axes, then apply conservative per-axis calibration."""
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
import pandas as pd
import importlib.util as _tio_u
_tio_s=_tio_u.spec_from_file_location("v2_table_io",Path(__file__).resolve().parents[1]/"Preprocess"/"table_io.py")
TABLE_IO=_tio_u.module_from_spec(_tio_s);_tio_s.loader.exec_module(TABLE_IO)
ROOT=Path(__file__).resolve().parent;AXES=("physical","variability","compact","extragalactic","phenomenon")
def load_module(path,name):
 s=importlib.util.spec_from_file_location(name,path)
 if s is None or s.loader is None:raise ImportError(path)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def annotate(df:pd.DataFrame,rows=None)->pd.DataFrame:
 modules={name:load_module(ROOT/"axes"/f"{name}.py",f"classifier_axis_{name}") for name in AXES};additions={}
 if rows is None:rows=df.to_dict("records")  # plain dicts; per-row pandas Series dominated runtime
 for name,module in modules.items():
  results=[module.classify(row) for row in rows]
  additions[f"{name}_class"]=[r["label"] for r in results];additions[f"{name}_subtype"]=[r.get("subtype") for r in results];additions[f"{name}_confidence"]=[r["confidence"] for r in results];additions[f"{name}_status"]=[r["status"] for r in results];additions[f"{name}_evidence_json"]=[json.dumps(r["evidence"],ensure_ascii=False,separators=(",",":")) for r in results]
 # Re-annotating an already classified frame must replace, not duplicate, the
 # axis columns: duplicate names made per_axis read a 2-column frame as one
 # column (every named-source blind validation failed since 2026-10-09).
 stale=[c for c in df.columns if any(c.startswith(f"{a}_") for a in AXES) and c.split("_",1)[1] in ("class","subtype","confidence","status","evidence_json","calibrated_probability","calibration_status","calibration_method")]
 result=pd.concat([df.drop(columns=stale).reset_index(drop=True),pd.DataFrame(additions)],axis=1)
 cal=load_module(ROOT/"calibration"/"per_axis.py","classifier_per_axis_calibration")
 return cal.annotate(result,ROOT/"calibration"/"models.json",AXES)
def run(inp:Path,out:Path):
 result=annotate(TABLE_IO.read_table(inp));out.parent.mkdir(parents=True,exist_ok=True);result.to_csv(out,index=False);print(f"[OK] full multi-axis classification rows={len(result)} axes={len(AXES)} -> {out}");return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--input",type=Path,default=ROOT/"classifier_input.csv");p.add_argument("--out",type=Path,default=ROOT/"multi_axis_classification.csv");a=p.parse_args();run(a.input,a.out)
if __name__=="__main__":main()

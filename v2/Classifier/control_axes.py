#!/usr/bin/env python3
"""Run all independent classifier axes and emit a multi-axis dataset."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
AXES=("physical","variability","compact","extragalactic","phenomenon")

def load_axis(name):
    path=ROOT/"axes"/f"{name}.py"
    spec=importlib.util.spec_from_file_location(f"classifier_axis_{name}",path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load classifier axis: {path}")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def annotate(df:pd.DataFrame)->pd.DataFrame:
    modules={name:load_axis(name) for name in AXES}
    additions={}
    for name,module in modules.items():
        results=[module.classify(row) for _,row in df.iterrows()]
        additions[f"{name}_class"]=[r["label"] for r in results]
        additions[f"{name}_confidence"]=[r["confidence"] for r in results]
        additions[f"{name}_status"]=[r["status"] for r in results]
        additions[f"{name}_evidence_json"]=[json.dumps(r["evidence"],ensure_ascii=False,separators=(",",":")) for r in results]
    return pd.concat([df.reset_index(drop=True),pd.DataFrame(additions)],axis=1)

def run(inp:Path,out:Path):
    df=pd.read_csv(inp)
    result=annotate(df)
    out.parent.mkdir(parents=True,exist_ok=True); result.to_csv(out,index=False)
    print(f"[OK] multi-axis classification rows={len(result)} -> {out}")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=ROOT/"classifier_input.csv")
    p.add_argument("--out",type=Path,default=ROOT/"multi_axis_classification.csv")
    a=p.parse_args(); run(a.input,a.out)
if __name__=="__main__": main()

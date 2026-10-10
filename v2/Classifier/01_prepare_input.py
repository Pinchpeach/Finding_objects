#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ALLOWED={"STAR","GALAXY","QSO","UNKNOWN"}

def run(inp:Path,out:Path):
    d=pd.read_csv(inp)
    if "primary_class" not in d:
        raise KeyError("primary_class is required from v2/Preprocess")
    bad=sorted(set(d.primary_class.dropna().astype(str))-ALLOWED)
    if bad:
        raise ValueError(f"unsupported coarse classes: {bad}")
    out.parent.mkdir(parents=True,exist_ok=True)
    d.to_csv(out,index=False)
    print(f"[OK] prepared {len(d)} rows -> {out}")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"classifier_input.csv")
    a=p.parse_args(); run(a.input,a.out)
if __name__=="__main__": main()

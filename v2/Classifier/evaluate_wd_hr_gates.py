#!/usr/bin/env python3
"""Compare Gaia HR WD-locus quality gates on independent spectroscopic truth.

Inputs are Gaia-crossmatched truth tables produced by collect_star_gaia.py.
Each must carry ``star_truth_class`` (WHITE_DWARF or anything else) and may
carry ``origin_class`` (e.g. STAR/GALAXY/QSO) to report contamination by
spectroscopic class.  Uses branches/star.py so the evaluated logic is exactly
the production logic.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent

def load_star():
    s=importlib.util.spec_from_file_location("star_branch",ROOT/"branches"/"star.py")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def evaluate(df:pd.DataFrame,star,gate:str)->dict:
    sig=df.apply(lambda r: star._wd_hr_signal(r,gate),axis=1)
    is_wd=df.star_truth_class.astype(str).eq("WHITE_DWARF")
    flagged=sig.eq(True)
    usable=sig.notna()
    tp=int((flagged&is_wd).sum()); fp=int((flagged&~is_wd).sum())
    res={
      "rows":int(len(df)),"usable":int(usable.sum()),"flagged_wd":int(flagged.sum()),
      "true_wd":int(is_wd.sum()),"tp":tp,"fp":fp,
      "wd_precision":tp/(tp+fp) if tp+fp else None,
      "wd_recall":tp/int(is_wd.sum()) if is_wd.any() else None,
      "usable_fraction":float(usable.mean()) if len(df) else None,
    }
    if "origin_class" in df.columns:
        res["false_wd_by_origin"]={str(k):int(v) for k,v in df.loc[flagged&~is_wd,"origin_class"].value_counts().items()}
        res["rows_by_origin"]={str(k):int(v) for k,v in df.origin_class.value_counts().items()}
    return res

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",type=Path,nargs="+",required=True,help="name=path pairs")
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    star=load_star(); report={}
    for spec in a.features:
        name,path=str(spec).split("=",1)
        df=pd.read_csv(path)
        report[name]={gate:evaluate(df,star,gate) for gate in star.HR_GATES}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    for name,gates in report.items():
        print(f"== {name}")
        for gate,r in gates.items():
            print(f"  {gate:18s} usable={r['usable']:5d} flagged={r['flagged_wd']:5d} tp={r['tp']:5d} fp={r['fp']:4d} "
                  f"P={r['wd_precision']} R={r['wd_recall']} fp_by_origin={r.get('false_wd_by_origin')}")

if __name__=="__main__": main()

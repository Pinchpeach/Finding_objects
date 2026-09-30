#!/usr/bin/env python3
"""Fit one-vs-rest Platt calibrators from independent truth/evaluation rows.

Input columns: axis, truth_class, predicted_class, raw_score.  A class model is
written only when both positive and negative support are adequate.  Rows whose
truth source overlaps the evidence source may be excluded with `leakage=1`.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
MIN_SAMPLES=100;MIN_POSITIVES=20;MIN_NEGATIVES=20

def fit(inp:Path,out:Path):
    from sklearn.linear_model import LogisticRegression
    df=pd.read_csv(inp)
    required={"axis","truth_class","predicted_class","raw_score"}
    if not required.issubset(df.columns):raise KeyError(f"missing columns: {required-set(df.columns)}")
    if "leakage" in df:df=df[~df["leakage"].fillna(False).astype(bool)].copy()
    df["raw_score"]=pd.to_numeric(df["raw_score"],errors="coerce");df=df.dropna(subset=["raw_score"])
    result={"schema_version":1,"policy":{"method":"platt","min_samples":MIN_SAMPLES,"min_positives":MIN_POSITIVES,"min_negatives":MIN_NEGATIVES},"axes":{}}
    for axis,g in df.groupby("axis"):
        classes=sorted(set(g["truth_class"].dropna().astype(str))|set(g["predicted_class"].dropna().astype(str)))
        result["axes"][axis]={}
        for label in classes:
            y=(g["truth_class"].astype(str)==label).astype(int);n=len(g);pos=int(y.sum());neg=n-pos
            meta={"n":n,"positive":pos,"negative":neg,"truth_independent":True}
            if n<MIN_SAMPLES or pos<MIN_POSITIVES or neg<MIN_NEGATIVES:
                result["axes"][axis][label]={**meta,"method":"withheld","reason":"insufficient independent truth support"};continue
            # Score for the candidate class: zero when a different class was predicted.
            x=(g["raw_score"].clip(0,1)*(g["predicted_class"].astype(str)==label).astype(float)).to_numpy().reshape(-1,1)
            m=LogisticRegression(solver="lbfgs").fit(x,y)
            result["axes"][axis][label]={**meta,"method":"platt","coef":float(m.coef_[0,0]),"intercept":float(m.intercept_[0])}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8");return result

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();fit(a.input,a.out)
if __name__=="__main__":main()

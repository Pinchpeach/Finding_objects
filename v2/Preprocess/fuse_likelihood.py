#!/usr/bin/env python3
"""Fuse calibrated/direct evidence into a primary likelihood vector.

v1 intentionally uses conservative weighted log pooling. Uncalibrated physical
rules are down-weighted; catalog probabilities and spectroscopy dominate.
"""
import argparse,json,math
from pathlib import Path
import pandas as pd
CLASSES=("STAR","WD","GALAXY","QSO","BINARY")
WEIGHT={"catalog_probability":1.0,"catalog_label":1.5,"support":0.35}

def fuse(items):
    logp={c:math.log(1/len(CLASSES)) for c in CLASSES}
    for e in items:
        c=e.get("class")
        if c not in CLASSES: continue
        s=min(max(float(e.get("score",0)),1e-6),1-1e-6)
        logp[c]+=WEIGHT.get(e.get("kind"),0.25)*math.log(s/(1-s))
    m=max(logp.values()); p={c:math.exp(v-m) for c,v in logp.items()}
    z=sum(p.values()); return {c:p[c]/z for c in CLASSES}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("input_csv",type=Path)
    ap.add_argument("-o","--output",type=Path,default=Path("likelihood.csv"))
    a=ap.parse_args(); df=pd.read_csv(a.input_csv); vectors=[]; labels=[]; conf=[]
    for raw in df.get("evidence_json",pd.Series(["[]"]*len(df))):
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except json.JSONDecodeError: items=[]
        p=fuse(items); vectors.append(p); labels.append(max(p,key=p.get)); conf.append(max(p.values()))
    for c in CLASSES: df[f"p_{c.lower()}"]=[v[c] for v in vectors]
    df["primary_class"]=labels; df["primary_confidence"]=conf
    a.output.parent.mkdir(parents=True,exist_ok=True); df.to_csv(a.output,index=False)
    print(f"[OK] {len(df)} sources -> {a.output}")
if __name__=="__main__": main()

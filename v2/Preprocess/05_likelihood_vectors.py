#!/usr/bin/env python3
"""Stage 5: fuse Stage-4 evidence into primary likelihood vectors.

The v1 fusion is deliberately conservative. Catalog probabilities/labels carry
more weight than uncalibrated physical support rules.
"""
from __future__ import annotations
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

def run(evidence: Path, out: Path) -> Path:
    df=pd.read_csv(evidence); vectors=[]; labels=[]; confidence=[]
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    for raw in raw_series:
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p=fuse(items); vectors.append(p); labels.append(max(p,key=p.get))
        confidence.append(max(p.values()))
    for c in CLASSES: df[f"p_{c.lower()}"]=[v[c] for v in vectors]
    df["primary_class"]=labels; df["primary_confidence"]=confidence
    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] {len(df)} sources -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=root/"evidence.csv")
    p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv")
    a=p.parse_args(); run(a.evidence,a.out)
if __name__=="__main__": main()

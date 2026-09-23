#!/usr/bin/env python3
"""Stage 5: fuse evidence into likelihood vectors without inventing labels."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd
CLASSES=("STAR","WD","GALAXY","QSO","BINARY")
WEIGHT={"direct_probability":1.0,"catalog_label":1.5,"continuous_score":0.35,"binary_evidence":0.35}
MIN_CONFIDENCE=.50; MIN_MARGIN=.10
def fuse(items):
    logp={c:math.log(1/len(CLASSES)) for c in CLASSES}
    used=0
    for e in items:
        c=e.get("class"); targets=("GALAXY","QSO") if c=="EXTRAGALACTIC" else ((c,) if c in CLASSES else ())
        if not targets: continue
        try: s=min(max(float(e.get("score",0)),.01),.99)
        except (TypeError,ValueError): continue
        delta=WEIGHT.get(e.get("kind"),.25)*math.log(s/(1-s))
        for t in targets: logp[t]+=delta
        used+=1
    m=max(logp.values()); p={c:math.exp(v-m) for c,v in logp.items()}; z=sum(p.values())
    return {c:p[c]/z for c in CLASSES},used
def run(evidence,out):
    df=pd.read_csv(evidence); vectors=[]; labels=[]; confidence=[]; margins=[]; statuses=[]
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    for raw in raw_series:
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p,used=fuse(items); order=sorted(p,key=p.get,reverse=True); conf=p[order[0]]; margin=conf-p[order[1]]
        conflict=bool(items) and len({e.get("class") for e in items if e.get("class") in CLASSES and float(e.get("score",0))>=.8})>1
        if used==0: label="UNKNOWN"; status="NO_EVIDENCE"
        elif conflict: label="UNKNOWN"; status="CONFLICT"
        elif conf<MIN_CONFIDENCE or margin<MIN_MARGIN: label="UNKNOWN"; status="LOW_CONFIDENCE"
        else: label=order[0]; status="CLASSIFIED"
        vectors.append(p); labels.append(label); confidence.append(conf); margins.append(margin); statuses.append(status)
    result_columns={f"p_{c.lower()}":[v[c] for v in vectors] for c in CLASSES}
    result_columns.update({
        "primary_class":labels,
        "primary_confidence":confidence,
        "primary_margin":margins,
        "classification_status":statuses,
    })
    df=pd.concat([df,pd.DataFrame(result_columns,index=df.index)],axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] {len(df)} sources -> {out}"); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=root/"evidence.csv"); p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv")
    a=p.parse_args(); run(a.evidence,a.out)
if __name__=="__main__": main()

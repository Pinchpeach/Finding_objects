#!/usr/bin/env python3
"""Stage 5: fuse coarse evidence into normalized likelihood scores.

The legacy p_star/p_galaxy/p_qso columns are retained for compatibility.  They
are *not* calibrated posterior probabilities; they are normalized evidence
likelihood scores.  Downstream calibrated probabilities live on the independent
Classifier axes and are emitted only when supported by independent truth data.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd
CLASSES=("STAR","GALAXY","QSO")
WEIGHT={"direct_probability":1.0,"catalog_label":1.5,"continuous_score":0.35,"binary_evidence":0.35}
MIN_CONFIDENCE=.50; MIN_MARGIN=.10

def fuse(items):
    logp={c:math.log(1/len(CLASSES)) for c in CLASSES}
    used=0
    for e in items:
        c=e.get("class")
        if c in {"WD","BINARY"}: c="STAR"
        targets=("GALAXY","QSO") if c=="EXTRAGALACTIC" else ((c,) if c in CLASSES else ())
        if not targets: continue
        try: s=min(max(float(e.get("score",0)),.01),.99)
        except (TypeError,ValueError): continue
        delta=WEIGHT.get(e.get("kind"),.25)*math.log(s/(1-s))
        for t in targets: logp[t]+=delta
        used+=1
    m=max(logp.values()); p={c:math.exp(v-m) for c,v in logp.items()}; z=sum(p.values())
    return {c:p[c]/z for c in CLASSES},used

def run(evidence,out):
    df=pd.read_csv(evidence); vectors=[]; labels=[]; confidence=[]; margins=[]; statuses=[]; best_candidates=[]; best_candidate_scores=[]
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    for raw in raw_series:
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p,used=fuse(items); order=sorted(p,key=p.get,reverse=True); conf=p[order[0]]; margin=conf-p[order[1]]
        strong=set()
        for e in items:
            c=e.get("class")
            if c in {"WD","BINARY"}: c="STAR"
            try: s=float(e.get("score",0))
            except (TypeError,ValueError): s=0
            if c in CLASSES and s>=.8: strong.add(c)
        conflict=bool(items) and len(strong)>1
        if used==0: label="UNKNOWN"; status="NO_EVIDENCE"
        elif conflict: label="UNKNOWN"; status="CONFLICT"
        elif conf<MIN_CONFIDENCE or margin<MIN_MARGIN: label="UNKNOWN"; status="LOW_CONFIDENCE"
        else: label=order[0]; status="CLASSIFIED"
        vectors.append(p); labels.append(label); confidence.append(conf); margins.append(margin); statuses.append(status)
        if status=="NO_EVIDENCE": best_candidates.append("UNKNOWN"); best_candidate_scores.append(float("nan"))
        else: best_candidates.append(order[0]); best_candidate_scores.append(conf)
    result_columns={}
    for c in CLASSES:
        vals=[v[c] for v in vectors]
        result_columns[f"likelihood_{c.lower()}"]=vals
        result_columns[f"p_{c.lower()}"]=vals  # legacy alias, explicitly uncalibrated below
    result_columns.update({
        "coarse_probability_calibrated":[False]*len(df),
        "coarse_score_semantics":["normalized evidence likelihood; not a calibrated posterior probability"]*len(df),
        "primary_class":labels,
        "primary_confidence":confidence,
        "primary_margin":margins,
        "classification_status":statuses,
        "best_candidate_class":best_candidates,
        "best_candidate_probability":best_candidate_scores,
    })
    df=pd.concat([df,pd.DataFrame(result_columns,index=df.index)],axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] {len(df)} sources -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=root/"evidence.csv"); p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv")
    a=p.parse_args(); run(a.evidence,a.out)
if __name__=="__main__": main()

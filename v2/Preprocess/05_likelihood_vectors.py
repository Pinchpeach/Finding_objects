#!/usr/bin/env python3
"""Stage 5: fuse coarse evidence into STAR/GALAXY/QSO scores.

Fusion is a linear log-odds model: each evidence item contributes
``w[rule:class][target] * logit(score)`` to every coarse class.  Without a
fitted model the weights are the hand-set priors in ``WEIGHT`` applied to the
item's target group, and the outputs are normalized evidence scores, not
calibrated probabilities.  When ``fusion_weights.json`` exists, weights for
evidence keys with independent training support (benchmark train split) are
replaced by fitted multinomial-logistic coefficients, and the abstention
threshold is the one chosen on the calibration split; keys without support
keep their prior weights.  See v2/benchmark/fit_fusion_weights.py.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd
CLASSES=("STAR","GALAXY","QSO")
WEIGHT={"direct_probability":1.0,"catalog_label":1.5,"continuous_score":0.35,"binary_evidence":0.35}
MIN_CONFIDENCE=.50; MIN_MARGIN=.10
# EXTRAGALACTIC (astrometric null, mid-IR AGN colour) cannot separate
# galaxies from quasars; POINT_SOURCE (unresolved morphology) cannot separate
# stars from quasars. Together they single out QSO.
GROUPS={"EXTRAGALACTIC":("GALAXY","QSO"),"POINT_SOURCE":("STAR","QSO")}
# Inside a large galaxy's D26 ellipse, survey detections are mostly pieces of
# that galaxy (HII regions, arms) rather than independent objects; only a
# Gaia-confirmed foreground star is classified there.
HOST_RADIUS=1.0
MODEL_PATH=Path(__file__).resolve().parent/"fusion_weights.json"

def evidence_features(items):
    """Map evidence items to {"RULE:CLASS": logit(score)} plus their kinds."""
    x={}; kinds={}
    for e in items:
        c=e.get("class")
        if c in {"WD","BINARY"}: c="STAR"
        if c not in GROUPS and c not in CLASSES: continue
        try: s=min(max(float(e.get("score",0)),.01),.99)
        except (TypeError,ValueError): continue
        key=f"{e.get('rule_id')}:{c}"
        x[key]=x.get(key,0.0)+math.log(s/(1-s)); kinds[key]=e.get("kind")
    return x,kinds

def prior_coef(key,kind):
    c=key.rsplit(":",1)[1]; w=WEIGHT.get(kind,.25)
    return {t:(w if t in GROUPS.get(c,(c,)) else 0.0) for t in CLASSES}

def load_model(path=MODEL_PATH):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return None

def fuse(items,model=None):
    x,kinds=evidence_features(items)
    coef=(model or {}).get("coef",{})
    logit={c:float((model or {}).get("intercept",{}).get(c,0.0)) for c in CLASSES}
    for key,v in x.items():
        w=coef.get(key) or prior_coef(key,kinds[key])
        for t in CLASSES: logit[t]+=w.get(t,0.0)*v
    m=max(logit.values()); p={c:math.exp(v-m) for c,v in logit.items()}; z=sum(p.values())
    return {c:p[c]/z for c in CLASSES},len(x)

def _gaia_foreground_star(items):
    """Significant Gaia parallax or proper motion (S/N >= 5; Stage-4 score >= 0.5)."""
    return any(e.get("rule_id") in {"AST-GAL-001","AST-GAL-002"} and float(e.get("raw_score",0))>=0.5 for e in items)

def run(evidence,out,model_path=MODEL_PATH):
    model=load_model(model_path)
    min_conf=float(model.get("min_confidence",MIN_CONFIDENCE)) if model else MIN_CONFIDENCE
    min_margin=float(model.get("min_margin",MIN_MARGIN)) if model else MIN_MARGIN
    df=pd.read_csv(evidence,low_memory=False); vectors=[]; labels=[]; confidence=[]; margins=[]; statuses=[]; best_candidates=[]; best_candidate_scores=[]
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    host_r=pd.to_numeric(df["host_elliptical_radius"],errors="coerce") if "host_elliptical_radius" in df else pd.Series(float("nan"),index=df.index)
    for raw,hr in zip(raw_series,host_r):
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p,used=fuse(items,model); order=sorted(p,key=p.get,reverse=True); conf=p[order[0]]; margin=conf-p[order[1]]
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
        elif conf<min_conf or margin<min_margin: label="UNKNOWN"; status="LOW_CONFIDENCE"
        elif hr<HOST_RADIUS and not _gaia_foreground_star(items): label="UNKNOWN"; status="WITHIN_LARGE_GALAXY"
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
        "coarse_probability_calibrated":[bool(model)]*len(df),
        "coarse_score_semantics":[(model or {}).get("semantics","normalized evidence likelihood; not a calibrated posterior probability")]*len(df),
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

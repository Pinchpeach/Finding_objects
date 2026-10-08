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
import numpy as np
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
# Minimum independent objects (with evidence, outside large-galaxy hosts) needed
# to re-estimate the field's class mix.
FIELD_PRIOR_MIN_OBJECTS=50
MODEL_PATH=Path(__file__).resolve().parent/"fusion_weights.json"

def evidence_features(items):
    """Map evidence items to {"RULE:CLASS": logit(score)} plus their kinds."""
    x={}; kinds={}
    for e in items:
        c=e.get("class")
        if e.get("kind")=="linear_feature":
            # Continuous feature (e.g. a colour): enters the model linearly and
            # carries weight only when a fitted model provides one.
            try: x[f"{e.get('rule_id')}:{c}"]=float(e.get("value")); kinds[f"{e.get('rule_id')}:{c}"]="linear_feature"
            except (TypeError,ValueError): pass
            continue
        if c in {"WD","BINARY"}: c="STAR"
        if c not in GROUPS and c not in CLASSES: continue
        try: s=min(max(float(e.get("score",0)),.01),.99)
        except (TypeError,ValueError): continue
        key=f"{e.get('rule_id')}:{c}"
        x[key]=x.get(key,0.0)+math.log(s/(1-s)); kinds[key]=e.get("kind")
    return x,kinds

def prior_coef(key,kind):
    if kind=="linear_feature": return {t:0.0 for t in CLASSES}
    c=key.rsplit(":",1)[1]; w=WEIGHT.get(kind,.25)
    return {t:(w if t in GROUPS.get(c,(c,)) else 0.0) for t in CLASSES}

def load_model(path=MODEL_PATH):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return None

def fuse(items,model=None):
    x,kinds=evidence_features(items)
    coef=(model or {}).get("coef",{})
    logit={c:float((model or {}).get("intercept",{}).get(c,0.0)) for c in CLASSES}
    used=0
    for key,v in x.items():
        w=coef.get(key) or prior_coef(key,kinds[key])
        for t in CLASSES: logit[t]+=w.get(t,0.0)*v
        # A continuous feature without a fitted weight carries no evidence.
        used+=int(kinds[key]!="linear_feature" or key in coef)
    m=max(logit.values()); p={c:math.exp(v-m) for c,v in logit.items()}; z=sum(p.values())
    return {c:p[c]/z for c in CLASSES},used

def _gaia_foreground_star(items):
    """Significant Gaia parallax or proper motion (S/N >= 5; Stage-4 score >= 0.5)."""
    return any(e.get("rule_id") in {"AST-GAL-001","AST-GAL-002"} and float(e.get("raw_score",0))>=0.5 for e in items)

def estimate_field_prior(P,train_prior,iters=200,tol=1e-7):
    """EM re-estimation of class priors under label shift.

    Saerens, Latinne & Decaestecker (2002, Neural Computation 14, 21): with
    posteriors calibrated under ``train_prior``, iterate
    pi <- mean_i p_i(pi), p_i(pi) ~ p_i * pi / train_prior.
    """
    base=np.asarray(train_prior,dtype=float); pi=base.copy()
    for _ in range(iters):
        Q=P*pi/base; Q/=Q.sum(axis=1,keepdims=True); new=Q.mean(axis=0)
        done=np.abs(new-pi).max()<tol; pi=new
        if done: break
    return pi

def run(evidence,out,model_path=MODEL_PATH,min_confidence=None):
    model=load_model(model_path)
    min_conf=float(model.get("min_confidence",MIN_CONFIDENCE)) if model else MIN_CONFIDENCE
    if min_confidence is not None: min_conf=float(min_confidence)  # caller trades coverage for precision
    min_margin=float(model.get("min_margin",MIN_MARGIN)) if model else MIN_MARGIN
    df=pd.read_csv(evidence,low_memory=False)
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    host_r=pd.to_numeric(df["host_elliptical_radius"],errors="coerce") if "host_elliptical_radius" in df else pd.Series(float("nan"),index=df.index)
    rows=[]
    for raw,hr in zip(raw_series,host_r):
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p,used=fuse(items,model)
        strong=set()
        for e in items:
            c=e.get("class")
            if c in {"WD","BINARY"}: c="STAR"
            try: s=float(e.get("score",0))
            except (TypeError,ValueError): s=0
            if c in CLASSES and s>=.8: strong.add(c)
        conflict=bool(items) and len(strong)>1
        in_host=hr<HOST_RADIUS and not _gaia_foreground_star(items)
        rows.append((np.array([p[c] for c in CLASSES]),used,conflict,in_host))
    P=np.array([r[0] for r in rows]).reshape(len(rows),len(CLASSES))
    # Field-prior adjustment needs calibrated posteriors (fitted model) and
    # enough independent objects in the field to estimate the class mix.
    eligible=np.array([used>0 and not conflict and not in_host for _,used,conflict,in_host in rows],dtype=bool)
    train_prior=[float((model or {}).get("training_prior",{}).get(c,1/len(CLASSES))) for c in CLASSES]
    adjust=bool(model) and int(eligible.sum())>=FIELD_PRIOR_MIN_OBJECTS
    prior=estimate_field_prior(P[eligible],train_prior) if adjust else np.array(train_prior)
    Q=P*prior/np.array(train_prior); Q=Q/Q.sum(axis=1,keepdims=True) if len(Q) else Q
    labels=[]; confidence=[]; margins=[]; statuses=[]; best_candidates=[]; best_candidate_scores=[]
    for q,(_,used,conflict,in_host) in zip(Q,rows):
        order=np.argsort(-q); conf=float(q[order[0]]); margin=conf-float(q[order[1]]); top=CLASSES[order[0]]
        if used==0: label="UNKNOWN"; status="NO_EVIDENCE"
        elif conflict: label="UNKNOWN"; status="CONFLICT"
        elif conf<min_conf or margin<min_margin: label="UNKNOWN"; status="LOW_CONFIDENCE"
        elif in_host: label="UNKNOWN"; status="WITHIN_LARGE_GALAXY"
        else: label=top; status="CLASSIFIED"
        labels.append(label); confidence.append(conf); margins.append(margin); statuses.append(status)
        if status=="NO_EVIDENCE": best_candidates.append("UNKNOWN"); best_candidate_scores.append(float("nan"))
        else: best_candidates.append(top); best_candidate_scores.append(conf)
    result_columns={}
    for i,c in enumerate(CLASSES):
        result_columns[f"likelihood_{c.lower()}"]=Q[:,i] if len(Q) else []
        result_columns[f"p_{c.lower()}"]=Q[:,i] if len(Q) else []  # legacy alias
        result_columns[f"p_{c.lower()}_training_prior"]=P[:,i] if len(P) else []
        result_columns[f"field_prior_{c.lower()}"]=[float(prior[i])]*len(df)
    result_columns.update({
        "coarse_probability_calibrated":[bool(model)]*len(df),
        "coarse_prior_adjusted":[adjust]*len(df),
        "coarse_score_semantics":[(model or {}).get("semantics","normalized evidence likelihood; not a calibrated posterior probability")
                                  +("; class priors re-estimated for this field (Saerens+2002 EM)" if adjust else "")]*len(df),
        "primary_class":labels,
        "primary_confidence":confidence,
        "primary_margin":margins,
        "classification_status":statuses,
        "best_candidate_class":best_candidates,
        "best_candidate_probability":best_candidate_scores,
    })
    df=pd.concat([df,pd.DataFrame(result_columns,index=df.index)],axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] {len(df)} sources -> {out}"+(f"; field prior {dict(zip(CLASSES,(round(float(x),3) for x in prior)))}" if adjust else "")); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=root/"evidence.csv"); p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv")
    p.add_argument("--min-confidence",type=float,help="override the abstention threshold (see COARSE_BENCHMARK_RESULTS.md for coverage/accuracy)")
    a=p.parse_args(); run(a.evidence,a.out,min_confidence=a.min_confidence)
if __name__=="__main__": main()

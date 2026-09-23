#!/usr/bin/env python3
"""Stage 5: hierarchical decision-tree classification with probability-vector fallback.

The tree encodes evidence precedence, not hand-made astrophysical colour boundaries:
  spectroscopy -> curated physical types -> Gaia DSC -> physical astrometry ->
  morphology -> validated colour selections -> probabilistic fusion fallback.

This mirrors the literature lesson that tree classifiers should be trained/validated
on labelled sources, while high-purity independent evidence should gate weaker
photometric evidence.  The existing evidence vector is retained for uncertainty.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import pandas as pd

CLASSES=("STAR","WD","GALAXY","QSO","BINARY")
WEIGHT={"direct_probability":1.0,"catalog_label":1.5,"continuous_score":0.35,
        "binary_evidence":0.35,"literature_reliability":1.0,"selection_evidence":0.6}
MIN_CONFIDENCE=.50
MIN_MARGIN=.10
TREE_VERSION="DT-HIER-001"

def fuse(items):
    logp={c:math.log(1/len(CLASSES)) for c in CLASSES}
    used=0
    for e in items:
        c=e.get("class")
        targets=("GALAXY","QSO") if c=="EXTRAGALACTIC" else ((c,) if c in CLASSES else ())
        if not targets: continue
        try: s=min(max(float(e.get("score",0)),.01),.99)
        except (TypeError,ValueError): continue
        delta=WEIGHT.get(e.get("kind"),.25)*math.log(s/(1-s))
        for t in targets: logp[t]+=delta
        used+=1
    m=max(logp.values()); p={c:math.exp(v-m) for c,v in logp.items()}; z=sum(p.values())
    return {c:p[c]/z for c in CLASSES},used

def top_for(items, rule_ids=None, groups=None, classes=CLASSES):
    cand=[]
    for e in items:
        if rule_ids is not None and e.get("rule_id") not in rule_ids: continue
        if groups is not None and e.get("feature_group") not in groups: continue
        if e.get("class") not in classes: continue
        try: score=float(e.get("score",0))
        except (TypeError,ValueError): continue
        cand.append((score,e))
    return max(cand,key=lambda x:x[0]) if cand else (None,None)

def decide_tree(items,p):
    """Return (label,status,node,score,note).

    A leaf is accepted only when its evidence type has a defensible interpretation.
    Weak/ambiguous leaves fall through to the probability-vector consolidation.
    """
    # Node 1: spectroscopy is the closest thing in this pipeline to a direct label.
    s,e=top_for(items,groups={"spectrum"})
    if e is not None and s>=0.75:
        return e["class"],"CLASSIFIED","DT1_SPECTROSCOPY",s,"spectroscopic class"

    # Node 2: curated literature databases; require agreement or one strong explicit type.
    curated=[e for e in items if e.get("rule_id") in {"NED-TYPE-001","SIMBAD-TYPE-001"} and e.get("class") in CLASSES]
    if curated:
        by={}
        for e in curated: by.setdefault(e["class"],[]).append(float(e.get("score",0)))
        cls,maxscores=max(by.items(),key=lambda kv:(len(kv[1]),max(kv[1])))
        if len(maxscores)>=2 or max(maxscores)>=0.75:
            return cls,"CLASSIFIED","DT2_CURATED_TYPE",max(maxscores),"curated physical type"

    # Node 3: Gaia DSC. Gaia itself uses >0.5 for classlabel_dsc, but published
    # purity of rare extragalactic classes can be modest. Use 0.8 as a conservative
    # PROJECT threshold; preserve lower probabilities for fallback.
    dsc=[e for e in items if e.get("rule_id")=="DSC-001" and e.get("class") in CLASSES]
    if dsc:
        e=max(dsc,key=lambda x:float(x.get("score",0)))
        s=float(e.get("score",0))
        if s>=0.80:
            return e["class"],"CLASSIFIED","DT3_GAIA_DSC",s,"high Gaia DSC probability"

    # Node 4: decisive Galactic astrometry. Two independent astrometric indicators
    # must both support STAR; this avoids making a leaf from one noisy measurement.
    ast=[float(e.get("score",0)) for e in items if e.get("rule_id") in {"AST-GAL-001","AST-GAL-002"} and e.get("class")=="STAR"]
    if len(ast)>=2 and min(ast)>=0.50:
        return "STAR","CLASSIFIED","DT4_GALACTIC_ASTROMETRY",min(ast),"parallax and proper-motion support"

    # Node 5: morphology. Extended morphology can support galaxy; point-like
    # morphology alone never becomes a STAR leaf because QSOs are unresolved.
    morph=[e for e in items if e.get("rule_id") in {"PS1-MORPH-001","SDSS-PHOTO-001"} and e.get("class")=="GALAXY"]
    if morph:
        e=max(morph,key=lambda x:float(x.get("score",0))); s=float(e.get("score",0))
        if s>=0.80:
            return "GALAXY","CLASSIFIED","DT5_EXTENDED_MORPHOLOGY",s,"high-reliability extended morphology"

    # Node 6: validated colour selections. WISE rules identify AGN/extragalactic
    # candidates rather than a unique QSO/GALAXY leaf, so only QSO-specific PS1
    # selection can form a class leaf; WISE remains vector evidence.
    qso=[e for e in items if e.get("rule_id")=="PS1-QSO-Z6-001" and e.get("class")=="QSO"]
    if qso:
        e=max(qso,key=lambda x:float(x.get("score",0))); s=float(e.get("score",0))
        if s>=0.70:
            return "QSO","CLASSIFIED","DT6_COLOR_SELECTION",s,"literature high-z QSO selection"

    # Consolidation leaf: same vector as before, now only after stronger tree nodes.
    order=sorted(p,key=p.get,reverse=True); conf=p[order[0]]; margin=conf-p[order[1]]
    if conf>=MIN_CONFIDENCE and margin>=MIN_MARGIN:
        return order[0],"CLASSIFIED","DT7_VECTOR_FALLBACK",conf,"multi-evidence probability consolidation"
    if any(e.get("class") in CLASSES or e.get("class")=="EXTRAGALACTIC" for e in items):
        return "UNKNOWN","LOW_CONFIDENCE","DT8_UNCERTAIN",conf,"evidence present but no reliable leaf"
    return "UNKNOWN","NO_EVIDENCE","DT9_NO_EVIDENCE",float("nan"),"no usable primary evidence"

def run(evidence,out):
    df=pd.read_csv(evidence); vectors=[]; labels=[]; confidence=[]; margins=[]; statuses=[]
    best_candidates=[]; best_candidate_probs=[]; nodes=[]; tree_scores=[]; notes=[]
    raw_series=df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"]*len(df))
    for raw in raw_series:
        try: items=json.loads(raw) if isinstance(raw,str) else []
        except (json.JSONDecodeError,TypeError): items=[]
        p,used=fuse(items); order=sorted(p,key=p.get,reverse=True)
        conf=p[order[0]]; margin=conf-p[order[1]]
        strong={e.get("class") for e in items if e.get("class") in CLASSES and float(e.get("score",0))>=.8}
        if len(strong)>1:
            label,status,node,tscore,note="UNKNOWN","CONFLICT","DT0_CONFLICT",conf,"strong evidence supports multiple primary classes"
        else:
            label,status,node,tscore,note=decide_tree(items,p)
        vectors.append(p); labels.append(label); statuses.append(status); nodes.append(node); tree_scores.append(tscore); notes.append(note)
        confidence.append(conf if status!="NO_EVIDENCE" else float("nan")); margins.append(margin if status!="NO_EVIDENCE" else float("nan"))
        if used==0:
            best_candidates.append("UNKNOWN"); best_candidate_probs.append(float("nan"))
        else:
            best_candidates.append(order[0]); best_candidate_probs.append(conf)
    result_columns={f"p_{c.lower()}":[v[c] for v in vectors] for c in CLASSES}
    result_columns.update({"primary_class":labels,"primary_confidence":confidence,"primary_margin":margins,
      "classification_status":statuses,"best_candidate_class":best_candidates,
      "best_candidate_probability":best_candidate_probs,"decision_tree_version":[TREE_VERSION]*len(df),
      "decision_node":nodes,"decision_score":tree_scores,"decision_note":notes})
    df=pd.concat([df,pd.DataFrame(result_columns,index=df.index)],axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] {len(df)} sources tree={TREE_VERSION} -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=root/"evidence.csv")
    p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv")
    a=p.parse_args(); run(a.evidence,a.out)
if __name__=="__main__": main()

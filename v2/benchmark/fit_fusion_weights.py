#!/usr/bin/env python3
"""Fit Stage-5 coarse fusion weights on the benchmark train split.

Stage 5 is a linear log-odds model over evidence keys ``RULE:CLASS`` whose
value is ``logit(score)``.  This fits that same model (multinomial logistic
regression, L2) on the deterministic **train** split of the SDSS
spectroscopic benchmark, picks the regularization and the abstention
threshold on the **calibration** split, and reports the untouched **test**
split.  Keys with fewer than ``--min-support`` non-zero train rows are left
out, so Stage 5 keeps their hand-set prior weights (e.g. Gaia DSC, SIMBAD and
NED evidence, which this benchmark does not contain).
"""
from __future__ import annotations
import argparse, importlib.util, json, tempfile
from pathlib import Path
import numpy as np, pandas as pd

V2=Path(__file__).resolve().parents[1]
PRE=V2/"Preprocess"
CLASSES=["STAR","GALAXY","QSO"]

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def evidence_table(truth,catalog_root):
    base=load(Path(__file__).with_name("evaluate_rule_baseline.py"),"rule_baseline")
    base.pre=load(PRE/"02_integrate_objects.py","integrate")
    raw=base.wide(truth,base.read_catalogs(catalog_root))
    s3=load(PRE/"03_extract_features.py","s3"); s4=load(PRE/"04_build_evidence.py","s4")
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); raw.to_csv(td/"o.csv",index=False)
        s3.run(td/"o.csv",PRE/"classification_rules.csv",td/"f.csv")
        s4.run(td/"f.csv",PRE/"classification_rules.csv",td/"e.csv")
        return pd.read_csv(td/"e.csv",usecols=["benchmark_id","evidence_json"])

def design(evidence,s5):
    rows=[]; kinds={}
    for raw in evidence.evidence_json:
        x,k=s5.evidence_features(json.loads(raw) if isinstance(raw,str) else []); rows.append(x); kinds.update(k)
    keys=sorted({k for r in rows for k in r})
    X=np.array([[r.get(k,0.0) for k in keys] for r in rows]); used=np.array([len(r)>0 for r in rows])
    return X,keys,kinds,used

def coverage_curve(p,y,used,grid):
    conf=p.max(axis=1); pred=np.array(CLASSES)[p.argmax(axis=1)]
    out=[]
    for t in grid:
        c=used&(conf>=t)
        out.append({"threshold":float(t),"coverage":float(c.mean()),"accuracy":float((pred[c]==y[c]).mean()) if c.any() else None})
    return out

def ece(p,y,bins=10):
    """Expected calibration error of the top-class probability."""
    conf=p.max(axis=1); hit=(np.array(CLASSES)[p.argmax(axis=1)]==y)
    edges=np.linspace(1/3,1,bins+1); total=0.0
    for lo,hi in zip(edges[:-1],edges[1:]):
        m=(conf>=lo)&((conf<hi)|(hi==1))
        if m.any(): total+=m.mean()*abs(hit[m].mean()-conf[m].mean())
    return float(total)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--truth",type=Path,required=True); ap.add_argument("--catalog-root",type=Path,required=True)
    ap.add_argument("--manifest",type=Path,required=True); ap.add_argument("--out",type=Path,default=PRE/"fusion_weights.json")
    ap.add_argument("--min-support",type=int,default=30)
    ap.add_argument("--target-accuracy",type=float,default=0.95,help="calibration-split accuracy the abstention threshold must reach")
    a=ap.parse_args()
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss
    s5=load(PRE/"05_likelihood_vectors.py","s5")
    truth=pd.read_csv(a.truth); manifest=pd.read_csv(a.manifest)
    ev=evidence_table(truth,a.catalog_root).merge(manifest[["benchmark_id","truth_class","split"]],on="benchmark_id")
    X,keys,kinds,used=design(ev,s5); y=ev.truth_class.to_numpy()
    tr=ev.split.eq("train").to_numpy(); ca=ev.split.eq("calibration").to_numpy(); te=ev.split.eq("test").to_numpy()
    support=(X[tr]!=0).sum(axis=0); keep=support>=a.min_support
    Xk=X[:,keep]; kept=[k for k,m in zip(keys,keep) if m]
    fit_rows=tr&used
    best=None
    for C in (0.01,0.03,0.1,0.3,1.0,3.0):
        m=LogisticRegression(C=C,max_iter=2000).fit(Xk[fit_rows],y[fit_rows])
        ll=log_loss(y[ca&used],m.predict_proba(Xk[ca&used]),labels=list(m.classes_))
        if best is None or ll<best[0]: best=(ll,C,m)
    ll,C,m=best
    order=[list(m.classes_).index(c) for c in CLASSES]
    coef={k:{c:float(m.coef_[order[i],j]) for i,c in enumerate(CLASSES)} for j,k in enumerate(kept)}
    model={"version":1,"classes":CLASSES,
      "intercept":{c:float(m.intercept_[order[i]]) for i,c in enumerate(CLASSES)},
      "coef":coef,"min_margin":0.0,
      "training_prior":{c:float((y[fit_rows]==c).mean()) for c in CLASSES},
      "semantics":"multinomial-logistic probability fitted on a class-balanced SDSS spectroscopic benchmark (equal priors); evidence keys without training support use prior weights",
      "provenance":{"benchmark":str(a.truth.relative_to(V2.parent)) if a.truth.is_absolute() and a.truth.is_relative_to(V2.parent) else str(a.truth),
        "train_rows":int(fit_rows.sum()),"calibration_rows":int((ca&used).sum()),"C":C,"calibration_log_loss":float(ll),
        "min_support":a.min_support,"support":{k:int(s) for k,s in zip(keys,support)},
        "prior_weight_keys":[k for k,mk in zip(keys,keep) if not mk]}}
    # Probabilities exactly as Stage 5 will compute them.
    def probs(mask):
        P=[]
        for raw in ev.evidence_json[mask]:
            p,_=s5.fuse(json.loads(raw) if isinstance(raw,str) else [],model); P.append([p[c] for c in CLASSES])
        return np.array(P)
    grid=np.round(np.arange(0.34,0.991,0.01),2)
    pca=probs(ca); curve=coverage_curve(pca,y[ca],used[ca],grid)
    ok=[r for r in curve if r["accuracy"] is not None and r["accuracy"]>=a.target_accuracy]
    model["min_confidence"]=ok[0]["threshold"] if ok else 0.9
    model["provenance"]["calibration_curve"]=curve
    model["provenance"]["target_calibration_accuracy"]=a.target_accuracy
    pte=probs(te); yte=y[te]; ute=used[te]
    conf=pte.max(axis=1); pred=np.array(CLASSES)[pte.argmax(axis=1)]; cl=ute&(conf>=model["min_confidence"])
    test={"rows":int(te.sum()),"classified":int(cl.sum()),"coverage":float(cl.mean()),
          "accuracy_when_classified":float((pred[cl]==yte[cl]).mean()),
          "accuracy_all_unknown_wrong":float((np.where(cl,pred,"UNKNOWN")==yte).mean()),
          "log_loss_used":float(log_loss(yte[ute],pte[ute][:,np.argsort(CLASSES)],labels=sorted(CLASSES))),
          "expected_calibration_error":ece(pte[ute],yte[ute]),
          "accuracy_by_threshold":coverage_curve(pte,yte,ute,(0.5,0.6,0.7,0.8,0.9,0.95))}
    model["provenance"]["test"]=test
    a.out.write_text(json.dumps(model,indent=1,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"C":C,"kept_keys":len(kept),"prior_keys":model["provenance"]["prior_weight_keys"],
                      "min_confidence":model["min_confidence"],"test":test},indent=1))

if __name__=="__main__": main()

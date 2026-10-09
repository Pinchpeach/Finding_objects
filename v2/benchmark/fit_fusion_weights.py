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
    # Several truth sets may be combined (same order in each list); each keeps
    # its own deterministic train/calibration/test split and is reported apart.
    ap.add_argument("--truth",type=Path,nargs="+",required=True); ap.add_argument("--catalog-root",type=Path,nargs="+",required=True)
    ap.add_argument("--manifest",type=Path,nargs="+",required=True); ap.add_argument("--out",type=Path,default=PRE/"fusion_weights.json")
    ap.add_argument("--drop-keys",nargs="*",default=[],help="evidence-key prefixes to exclude (ablation)")
    ap.add_argument("--augment-drop",nargs="*",default=[],
                    help="augmentation groups, each a comma-separated list of evidence-key prefixes dropped together "
                         "in an extra copy of every train row that has them (e.g. 'LS-MORPH,PS1-MORPH,SDSS-PHOTO' 'LS-'), "
                         "so the remaining weights also learn the case where they are missing")
    ap.add_argument("--target-scope",choices=("pooled","each"),default="pooled",
                    help="'each': the abstention threshold must reach --target-accuracy on every dataset's calibration split")
    ap.add_argument("--augment-weight",type=float,default=1.0,help="sample weight of the augmented copies")
    ap.add_argument("--report-drop",nargs="*",default=None,help="also report test accuracy with these evidence prefixes removed (default: --augment-drop)")
    ap.add_argument("--min-support",type=int,default=30)
    ap.add_argument("--target-accuracy",type=float,default=0.95,help="calibration-split accuracy the abstention threshold must reach")
    a=ap.parse_args()
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss
    s5=load(PRE/"05_likelihood_vectors.py","s5")
    if not len(a.truth)==len(a.catalog_root)==len(a.manifest): ap.error("--truth/--catalog-root/--manifest counts differ")
    parts=[]
    for t,root,man in zip(a.truth,a.catalog_root,a.manifest):
        e=evidence_table(pd.read_csv(t),root).merge(pd.read_csv(man)[["benchmark_id","truth_class","split"]],on="benchmark_id")
        e["dataset"]=t.parent.name; parts.append(e)
    ev=pd.concat(parts,ignore_index=True)
    X,keys,kinds,used=design(ev,s5); y=ev.truth_class.to_numpy()
    if a.drop_keys:
        dropped=np.array([any(k.startswith(p) for p in a.drop_keys) for k in keys])
        X[:,dropped]=0.0
    tr=ev.split.eq("train").to_numpy(); ca=ev.split.eq("calibration").to_numpy(); te=ev.split.eq("test").to_numpy()
    support=(X[tr]!=0).sum(axis=0); keep=support>=a.min_support
    Xk=X[:,keep]; kept=[k for k,m in zip(keys,keep) if m]
    fit_rows=tr&used
    Xfit,yfit=Xk[fit_rows],y[fit_rows]
    Xcal,ycal=Xk[ca&used],y[ca&used]
    if a.augment_drop:
        # Missing-feature augmentation: faint objects in real fields often lack
        # e.g. a resolved-morphology measurement that nearly every benchmark
        # object has.  Without this the colour weights learn only the
        # conditional "given morphology" separation (red point source = star)
        # and send faint red galaxies to STAR.
        # Each argument is one augmentation group: comma-separated prefixes
        # dropped together in one extra copy (e.g. all morphology; or every
        # Legacy Surveys rule, as when that archive is unavailable).
        groups=[[p for p in g.split(",") if p] for g in a.augment_drop]
        def augment(Xs,ys):
            Xo,yo,wo=[Xs],[ys],[np.ones(len(ys))]
            for g in groups:
                aug=np.array([any(k.startswith(p) for p in g) for k in kept])
                has=(Xs[:,aug]!=0).any(axis=1); Xa=Xs[has].copy(); Xa[:,aug]=0.0
                keep_row=(Xa!=0).any(axis=1)
                Xo.append(Xa[keep_row]); yo.append(ys[has][keep_row]); wo.append(np.full(int(keep_row.sum()),a.augment_weight))
            return np.vstack(Xo),np.concatenate(yo),np.concatenate(wo)
        Xfit,yfit,wfit=augment(Xfit,yfit); Xcal,ycal,wcal=augment(Xcal,ycal)
    else:
        wfit=np.ones(len(yfit)); wcal=np.ones(len(ycal))
    best=None
    for C in (0.01,0.03,0.1,0.3,1.0,3.0):
        m=LogisticRegression(C=C,max_iter=2000).fit(Xfit,yfit,sample_weight=wfit)
        ll=log_loss(ycal,m.predict_proba(Xcal),labels=list(m.classes_),sample_weight=wcal)
        if best is None or ll<best[0]: best=(ll,C,m)
    ll,C,m=best
    order=[list(m.classes_).index(c) for c in CLASSES]
    coef={k:{c:float(m.coef_[order[i],j]) for i,c in enumerate(CLASSES)} for j,k in enumerate(kept)}
    model={"version":1,"classes":CLASSES,
      "intercept":{c:float(m.intercept_[order[i]]) for i,c in enumerate(CLASSES)},
      "coef":coef,"min_margin":0.0,
      "training_prior":{c:float((y[fit_rows]==c).mean()) for c in CLASSES},
      "semantics":"multinomial-logistic probability fitted on class-balanced spectroscopic benchmarks (equal priors); evidence keys without training support use prior weights",
      "provenance":{"benchmarks":[str(t) for t in a.truth],"dropped_keys":a.drop_keys,
        "train_rows":int(fit_rows.sum()),"augment_drop":a.augment_drop,"augment_weight":a.augment_weight,"augmented_train_rows":int(len(yfit)),"calibration_rows":int((ca&used).sum()),"C":C,"calibration_log_loss":float(ll),
        "min_support":a.min_support,"support":{k:int(s) for k,s in zip(keys,support)},
        "prior_weight_keys":[k for k,mk in zip(keys,keep) if not mk]}}
    # Probabilities exactly as Stage 5 will compute them.
    def probs(mask,drop=()):
        P=[]
        for raw in ev.evidence_json[mask]:
            items=json.loads(raw) if isinstance(raw,str) else []
            if drop: items=[i for i in items if not str(i.get("rule_id","")).startswith(tuple(drop))]
            p,_=s5.fuse(items,model); P.append([p[c] for c in CLASSES])
        return np.array(P)
    grid=np.round(np.arange(0.34,0.991,0.01),2)
    pca=probs(ca); curve=coverage_curve(pca,y[ca],used[ca],grid)
    if a.target_scope=="each":
        # Faint objects (e.g. DESI) are harder than bright ones (SDSS); a pooled
        # target lets the larger bright set hide the faint set's errors.
        curves=[]
        for name in ev.dataset.unique():
            mk=ca&ev.dataset.eq(name).to_numpy()
            curves.append(coverage_curve(probs(mk),y[mk],used[mk],grid))
        ok=[r for r,*rest in zip(curve,*curves) if all(c["accuracy"] is not None and c["accuracy"]>=a.target_accuracy for c in rest)]
    else:
        ok=[r for r in curve if r["accuracy"] is not None and r["accuracy"]>=a.target_accuracy]
    model["min_confidence"]=ok[0]["threshold"] if ok else 0.9
    model["provenance"]["calibration_curve"]=curve
    model["provenance"]["target_calibration_accuracy"]=a.target_accuracy
    model["provenance"]["target_scope"]=a.target_scope
    test={}
    for name in ev.dataset.unique():
        mask=te&ev.dataset.eq(name).to_numpy()
        pte=probs(mask); yte=y[mask]; ute=used[mask]
        conf=pte.max(axis=1); pred=np.array(CLASSES)[pte.argmax(axis=1)]; cl=ute&(conf>=model["min_confidence"])
        test[name]={"rows":int(mask.sum()),"classified":int(cl.sum()),"coverage":float(cl.mean()),
          "accuracy_when_classified":float((pred[cl]==yte[cl]).mean()),
          "accuracy_all_unknown_wrong":float((np.where(cl,pred,"UNKNOWN")==yte).mean()),
          "recall":{c:float((pred[yte==c]==c).mean()) for c in CLASSES},
          "log_loss_used":float(log_loss(yte[ute],pte[ute][:,np.argsort(CLASSES)],labels=sorted(CLASSES))),
          "expected_calibration_error":ece(pte[ute],yte[ute]),
          "accuracy_by_threshold":coverage_curve(pte,yte,ute,(0.5,0.6,0.7,0.8,0.9,0.95))}
        rdrop=a.augment_drop if a.report_drop is None else a.report_drop
        for g in rdrop:
            # Same test rows with a group of evidence removed: how the model
            # behaves on objects that lack it (e.g. faint, unresolved fits).
            g=[p for p in g.split(",") if p]
            pd_=probs(mask,g); pr=np.array(CLASSES)[pd_.argmax(axis=1)]
            test[name]["without_"+"+".join(g)]={"argmax_accuracy":float((pr==yte).mean()),
              "recall":{c:float((pr[yte==c]==c).mean()) for c in CLASSES}}
    model["provenance"]["test"]=test
    a.out.write_text(json.dumps(model,indent=1,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"C":C,"kept_keys":len(kept),"prior_keys":model["provenance"]["prior_weight_keys"],
                      "min_confidence":model["min_confidence"],"test":test},indent=1))

if __name__=="__main__": main()

import pandas as pd, json, glob, sys
from collections import defaultdict
S=sys.argv[1]
SETS={"EXTRAGALACTIC":{"GALAXY","QSO"},"POINT_SOURCE":{"STAR","QSO"},"STAR":{"STAR"},"GALAXY":{"GALAXY"},"QSO":{"QSO"},"GALACTIC":{"STAR"}}
rows=[]
for name in "AB":
    M=pd.read_csv(f"{S}/match_{name}.csv.gz",low_memory=False)[["field","object_id","t_truth"]]
    root=f"{S}/vd/v2/benchmark/independent_fields" + ("" if name=="A" else "_b")
    for field,g in M.groupby("field"):
        f=f"{root}/{field}/objects_blind_evidence.csv.gz"
        try: e=pd.read_csv(f,usecols=["object_id","evidence_json"])
        except Exception: continue
        e=e.merge(g,on="object_id")
        for oid,ev,t in zip(e.object_id,e.evidence_json,e.t_truth):
            try: L=json.loads(ev)
            except Exception: continue
            best={}
            for x in L:
                r,c,s=x.get("rule_id"),x.get("class"),x.get("score")
                if r is None or c is None or s is None: continue
                if r not in best or s>best[r][1]: best[r]=(c,s)
            for r,(c,s) in best.items():
                rows.append((name,r,c,float(s),t))
d=pd.DataFrame(rows,columns=["set","rule","cls","score","truth"])
d["ok"]=[t in SETS.get(c,{c}) for c,t in zip(d.cls,d.truth)]
d.to_csv(f"{S}/rule_fires.csv.gz",index=False)
out=[]
for r,g in d.groupby("rule"):
    for thr in (0.0,0.5):
        h=g[g.score>=thr] if thr else g
        if thr and h.empty: continue
    hi=g[g.score>=0.5]
    claims=hi.cls.value_counts().head(3).to_dict()
    out.append(dict(rule=r,n=len(g),n_hi=len(hi),prec_all=round(100*g.ok.mean(),2),prec_hi=round(100*hi.ok.mean(),2) if len(hi) else None,
                    wrong_hi=int((~hi.ok).sum()),claims=claims, truth_mix=g.truth.value_counts().to_dict()))
o=pd.DataFrame(out).sort_values("n",ascending=False)
pd.set_option("display.width",250); pd.set_option("display.max_colwidth",60)
print(o.to_string(index=False))
o.to_csv(f"{S}/rule_precision.csv",index=False)

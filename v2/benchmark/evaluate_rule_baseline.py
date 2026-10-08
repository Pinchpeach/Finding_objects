#!/usr/bin/env python3
"""Evaluate the existing rule/evidence/likelihood pipeline on benchmark matches."""
from __future__ import annotations
import argparse, importlib.util, json, tempfile
from pathlib import Path
import numpy as np, pandas as pd

def accuracy_score(y,p):
 y=np.asarray(y); p=np.asarray(p); return float((y==p).mean()) if len(y) else float("nan")

def f1_score(y,p,labels,average="macro",zero_division=0):
 y=np.asarray(y); p=np.asarray(p); out=[]
 for c in labels:
  tp=int(((p==c)&(y==c)).sum()); fp=int(((p==c)&(y!=c)).sum()); fn=int(((p!=c)&(y==c)).sum())
  out.append(2*tp/(2*tp+fp+fn) if (2*tp+fp+fn) else zero_division)
 return float(np.mean(out))

V2=Path(__file__).resolve().parents[1]
PRE=V2/"Preprocess"
DISPLAY={"gaia_dr3":"Gaia DR3","panstarrs1":"Pan-STARRS1","allwise":"AllWISE",
 "twomass":"2MASS PSC","galex":"GALEX AIS","desi_legacy":"DESI Legacy",
 "first":"FIRST","nvss":"NVSS","lotss":"LoTSS DR2","vlass":"VLASS",
 "chandra":"Chandra","xmm":"XMM","erosita":"eROSITA"}
# Full catalog names as emitted by the Get_data collectors; used for the same
# ``<catalog>__<field>`` namespace that Stage 2 writes.
CATALOG_NAME={"gaia_dr3":"Gaia DR3","panstarrs1":"Pan-STARRS1 DR2 MeanObject","allwise":"AllWISE",
 "twomass":"2MASS PSC","galex":"GALEX AIS","desi_legacy":"DESI Legacy Surveys DR10","first":"FIRST",
 "nvss":"NVSS","lotss":"LoTSS DR2","vlass":"VLASS","chandra":"Chandra CSC 2.0","xmm":"XMM 4XMM-DR13",
 "erosita":"eROSITA eRASS1"}
DROP={"truth_class","truth_source","truth_ra","truth_dec","catalog","catalog_object_id",
      "object_name","ra","dec","match_threshold_arcsec","_sep_arcsec","benchmark_id"}

def load_script(name):
 p=PRE/name; s=importlib.util.spec_from_file_location(name.replace(".py",""),p)
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def read_catalogs(root):
 out={}
 for f in sorted([*root.rglob("*_trd.csv"),*root.rglob("*_trd.csv.gz")]):
  cat=f.name.split("_trd.csv")[0]
  d=pd.read_csv(f,low_memory=False)
  if cat not in out or len(d)>len(out[cat]): out[cat]=d
 return out

pre=None
def wide(truth,cats):
 x=truth[["benchmark_id"]].copy(); pres={b:[] for b in x.benchmark_id}
 for cat,d in cats.items():
  if d is None or d.empty: continue
  ids=set(d.benchmark_id.astype(str))
  label=DISPLAY.get(cat,cat)
  for b in pres:
   if str(b) in ids: pres[b].append(label)
  cols=[c for c in d.columns if c not in DROP]
  q=d[["benchmark_id"]+cols].drop_duplicates("benchmark_id").copy()
  # Keep first occurrence of a raw field name; the existing rule engine expects
  # survey-native names such as W1mag and iMeanPSFMag.
  keep=["benchmark_id"]+[c for c in cols if c not in x.columns]
  ns=pre.prefix(CATALOG_NAME.get(cat,cat))
  spaced=q[["benchmark_id"]+cols].rename(columns={c:f"{ns}__{c}" for c in cols})
  x=x.merge(q[keep],on="benchmark_id",how="left").merge(spaced,on="benchmark_id",how="left")
 x["catalogs"]=["|".join(pres[b]) for b in x.benchmark_id]
 return x

def main():
 p=argparse.ArgumentParser(); p.add_argument("--truth",type=Path,required=True)
 p.add_argument("--catalog-root",type=Path,required=True); p.add_argument("--manifest",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 p.add_argument("--split",default="test",help="manifest split to report, or 'all' for an external truth set")
 a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
 truth=pd.read_csv(a.truth); manifest=pd.read_csv(a.manifest); cats=read_catalogs(a.catalog_root)
 global pre
 pre=load_script("02_integrate_objects.py")
 raw=wide(truth,cats)
 s3=load_script("03_extract_features.py"); s4=load_script("04_build_evidence.py"); s5=load_script("05_likelihood_vectors.py")
 with tempfile.TemporaryDirectory() as td:
  td=Path(td); p0=td/"objects.csv"; p3=td/"features.csv"; p4=td/"evidence.csv"; p5=td/"likelihood.csv"
  raw.to_csv(p0,index=False)
  s3.run(p0,PRE/"classification_rules.csv",p3)
  s4.run(p3,PRE/"classification_rules.csv",p4)
  s5.run(p4,p5)
  pred=pd.read_csv(p5)
 data=truth[["benchmark_id","truth_class"]].merge(manifest[["benchmark_id","split"]],on="benchmark_id").merge(
     pred[["benchmark_id","primary_class","classification_status","primary_confidence","primary_margin"]],on="benchmark_id")
 te=(data if a.split=="all" else data[data.split.eq(a.split)]).copy(); classified=te.primary_class.ne("UNKNOWN")
 metrics={"test_rows":len(te),"classified_rows":int(classified.sum()),"abstention_rate":float(1-classified.mean())}
 metrics["accuracy_all_unknown_wrong"]=float((te.primary_class==te.truth_class).mean())
 if classified.any():
  metrics["accuracy_when_classified"]=float(accuracy_score(te.loc[classified,"truth_class"],te.loc[classified,"primary_class"]))
  metrics["macro_f1_when_classified"]=float(f1_score(te.loc[classified,"truth_class"],te.loc[classified,"primary_class"],
                                                    labels=["STAR","GALAXY","QSO"],average="macro",zero_division=0))
 else:
  metrics["accuracy_when_classified"]=None; metrics["macro_f1_when_classified"]=None
 cm=pd.crosstab(te.truth_class,te.primary_class).reindex(index=["STAR","GALAXY","QSO"],columns=["STAR","GALAXY","QSO","UNKNOWN"],fill_value=0)
 metrics["confusion"]={t:{p:int(v) for p,v in row.items()} for t,row in cm.iterrows()}
 metrics["per_class_recall_all"]={t:float(cm.loc[t,t]/cm.loc[t].sum()) if cm.loc[t].sum() else None for t in cm.index}
 metrics["per_class_precision"]={p:float(cm.loc[p,p]/cm[p].sum()) if cm[p].sum() else None for p in ["STAR","GALAXY","QSO"]}
 print(cm.to_string())
 te.to_csv(a.out/"rule_baseline_test_predictions.csv",index=False)
 (a.out/"rule_baseline_metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
 print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()

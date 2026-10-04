#!/usr/bin/env python3
"""Sampled end-to-end cross-validation on independent per-axis truth sets.

Truth catalogues are never passed directly as evidence.  Each truth family uses
an explicitly separate collector set, so this measures independent evidence
coverage as well as classification accuracy.  UNKNOWN is an abstention and is
reported separately from classified-only accuracy.
"""
from __future__ import annotations
import argparse,importlib.util,json,math,sys,tempfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];GET=ROOT/"Get_data";PRE=ROOT/"Preprocess";CLS=ROOT/"Classifier"
if str(GET) not in sys.path:sys.path.insert(0,str(GET))

COLLECTORS={
 ("physical","RGB"):("gaia_dr3_physical_vizier",),
 ("physical","AGB"):("gaia_dr3_physical_vizier","allwise","twomass","agb_suh2021"),
 ("variability","RR_LYRAE"):("gaia_dr3_variability_vizier",),
 ("variability","CEPHEID"):("gaia_dr3_variability_vizier",),
 ("variability","MIRA"):("gaia_dr3_variability_vizier",),
 ("variability","LPV"):("gaia_dr3_variability_vizier",),
 # ATNF is truth here and is deliberately excluded from evidence.
 ("compact","PULSAR"):("gaia_dr3","chandra","xmm","first","nvss"),
 # Acker V/84 is truth; HASH is independent production evidence.
 ("phenomenon","PN"):("hash_pn",),
 # Asiago is truth; ASAS-SN is independent, but only covers a limited epoch.
 ("phenomenon","SN"):("asas_sn_supernova",),
}

def load_module(path,name):
 s=importlib.util.spec_from_file_location(name,path)
 if s is None or s.loader is None:raise ImportError(path)
 m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def run_cmd(args):
 import subprocess
 p=subprocess.run([sys.executable,*map(str,args)],text=True,capture_output=True,check=False)
 if p.returncode!=0:raise RuntimeError("command failed: "+" ".join(map(str,args))+"\n"+p.stderr[-3000:])

def collect(row,raw,radius):
 logs=[];names=COLLECTORS.get((str(row.truth_axis),str(row.truth_class)),())
 for name in names:
  try:
   mod=load_module(GET/f"{name}.py",f"truthval_{name}_{abs(hash(str(row.truth_id)))%1000000}")
   frame=mod.fetch(float(row.ra),float(row.dec),radius);mod.save(frame,raw/f"{name}.csv")
   logs.append({"collector":name,"status":"ok" if len(frame) else "empty","rows":len(frame)})
  except Exception as exc:logs.append({"collector":name,"status":"error","rows":0,"error":repr(exc)})
 return logs

def select(frame,ra,dec,radius,entity=None):
 ras=pd.to_numeric(frame["ra"],errors="coerce");des=pd.to_numeric(frame["dec"],errors="coerce")
 dra=(ras-ra)*math.cos(math.radians(dec));dde=des-dec;sep=3600*(dra*dra+dde*dde)**0.5
 cand=frame.copy();cand["_sep"]=sep;cand=cand[cand._sep<=radius*60]
 if entity and "entity_kind" in cand.columns:
  sub=cand[cand.entity_kind.astype(str)==entity]
  if not sub.empty:cand=sub
 if cand.empty:
  if frame.empty:return None,math.nan
  i=sep.idxmin();return frame.loc[i],float(sep.loc[i])
 cand["_members"]=pd.to_numeric(cand.get("association_members"),errors="coerce").fillna(1);cand=cand.sort_values(["_members","_sep"],ascending=[False,True]);r=cand.iloc[0];return r,float(r._sep)

def evaluate_one(rec,base,radius):
 safe=str(rec.truth_id).replace("/","_").replace(" ","_");work=base/f"{rec.truth_axis}_{rec.truth_class}_{safe}";raw=work/"raw";pre=work/"pre";cls=work/"cls"
 for d in (raw,pre,cls):d.mkdir(parents=True,exist_ok=True)
 logs=collect(rec,raw,radius);usable=sum(x.get("rows",0) for x in logs if x.get("status")=="ok")
 if not usable:return {"truth_id":rec.truth_id,"axis":rec.truth_axis,"truth_class":rec.truth_class,"predicted_class":"UNKNOWN","status":"NO_EVIDENCE","raw_score":math.nan,"match":False,"classified":False,"sep_arcsec":math.nan,"collectors":json.dumps(logs)}
 run_cmd([PRE/"01_source_association.py","--raw-dir",raw,"--out",pre/"source_association.csv"])
 run_cmd([PRE/"02_integrate_objects.py","--associations",pre/"source_association.csv","--raw-dir",raw,"--out",pre/"integrated_objects.csv"])
 run_cmd([PRE/"03_extract_features.py","--objects",pre/"integrated_objects.csv","--rules",PRE/"classification_rules.csv","--out",pre/"features.csv"])
 run_cmd([PRE/"04_build_evidence.py","--features",pre/"features.csv","--rules",PRE/"classification_rules.csv","--out",pre/"evidence.csv"])
 run_cmd([PRE/"05_likelihood_vectors.py","--evidence",pre/"evidence.csv","--out",pre/"likelihood_vectors.csv"])
 run_cmd([CLS/"01_prepare_input.py","--input",pre/"likelihood_vectors.csv","--out",cls/"input.csv"])
 run_cmd([CLS/"control.py","--input",cls/"input.csv","--out",cls/"classified.csv"])
 df=pd.read_csv(cls/"classified.csv");entity="transient_event" if rec.truth_class=="SN" else None;row,sep=select(df,float(rec.ra),float(rec.dec),radius,entity)
 if row is None:return {"truth_id":rec.truth_id,"axis":rec.truth_axis,"truth_class":rec.truth_class,"predicted_class":"UNKNOWN","status":"NO_OBJECT","raw_score":math.nan,"match":False,"classified":False,"sep_arcsec":math.nan,"collectors":json.dumps(logs)}
 axis=str(rec.truth_axis);pred=str(row.get(f"{axis}_class","UNKNOWN"));status=str(row.get(f"{axis}_status",""));score=pd.to_numeric(pd.Series([row.get(f"{axis}_confidence")]),errors="coerce").iloc[0]
 classified=pred not in {"UNKNOWN","nan","ERROR"}
 family_match=(pred==rec.truth_class) or (str(rec.truth_class)=="MIRA" and pred=="LPV")
 return {"truth_id":rec.truth_id,"axis":axis,"truth_class":rec.truth_class,"predicted_class":pred,"status":status,"raw_score":score,"match":pred==rec.truth_class,"family_match":family_match,"classified":classified,"sep_arcsec":sep,"collectors":json.dumps(logs)}

def sample_truth(truth_dir,per_class):
 parts=[]
 for p in sorted(truth_dir.glob("*_truth.csv")):
  try:df=pd.read_csv(p)
  except Exception:continue
  if not {"truth_id","ra","dec","truth_axis","truth_class"}.issubset(df.columns):continue
  for _,g in df.dropna(subset=["ra","dec","truth_class"]).groupby(["truth_axis","truth_class"]):
   n=min(per_class,len(g));parts.append(g.sample(n=n,random_state=42) if len(g)>n else g)
 return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()

def write_report(rows,out):
 out.mkdir(parents=True,exist_ok=True);rows.to_csv(out/"independent_truth_predictions.csv",index=False)
 summary=[]
 if not rows.empty:
  for (axis,label),g in rows.groupby(["axis","truth_class"]):
   classified=g.classified.astype(bool);matches=g.match.astype(bool)
   summary.append({"axis":axis,"truth_class":label,"n":len(g),"classified":int(classified.sum()),"coverage":float(classified.mean()),"exact_accuracy_all":float(matches.mean()),"accuracy_when_classified":float(matches[classified].mean()) if classified.any() else math.nan})
 s=pd.DataFrame(summary);s.to_csv(out/"independent_truth_summary.csv",index=False)
 lines=["# Independent truth-set cross-validation","","Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.","","| axis | class | n | classified | coverage | accuracy all | accuracy classified |","|---|---|---:|---:|---:|---:|---:|"]
 for _,r in s.iterrows():lines.append(f"| {r.axis} | {r.truth_class} | {int(r.n)} | {int(r.classified)} | {r.coverage:.1%} | {r.exact_accuracy_all:.1%} | {r.accuracy_when_classified:.1%} |" if pd.notna(r.accuracy_when_classified) else f"| {r.axis} | {r.truth_class} | {int(r.n)} | {int(r.classified)} | {r.coverage:.1%} | {r.exact_accuracy_all:.1%} | n/a |")
 lines += ["","UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity."]
 (out/"INDEPENDENT_TRUTH_VALIDATION.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
 return s

def main():
 p=argparse.ArgumentParser();p.add_argument("--truth-dir",type=Path,default=CLS/"truth"/"generated");p.add_argument("--out-dir",type=Path,default=CLS/"validation"/"independent_truth");p.add_argument("--per-class",type=int,default=8);p.add_argument("--axis");p.add_argument("--truth-class");p.add_argument("--radius-arcmin",type=float,default=.5);p.add_argument("--max-workers",type=int,default=6);a=p.parse_args();truth=sample_truth(a.truth_dir,a.per_class)
 if a.axis:
  truth=truth[truth.truth_axis.astype(str)==a.axis]
 if a.truth_class:
  truth=truth[truth.truth_class.astype(str)==a.truth_class]
 if truth.empty:raise RuntimeError("no independent truth rows available")
 a.out_dir.mkdir(parents=True,exist_ok=True);checkpoint=a.out_dir/"independent_truth_checkpoint.csv"
 rows=[]
 if checkpoint.exists():
  try:
   prior=pd.read_csv(checkpoint);rows=prior.to_dict("records")
  except Exception:rows=[]
 done={(str(x.get("axis")),str(x.get("truth_class")),str(x.get("truth_id"))) for x in rows}
 pending=[r for _,r in truth.iterrows() if (str(r.truth_axis),str(r.truth_class),str(r.truth_id)) not in done]
 print(f"resume: {len(rows)} completed, {len(pending)} pending of {len(truth)}",flush=True)
 with tempfile.TemporaryDirectory() as tmp:
  base=Path(tmp)
  with ThreadPoolExecutor(max_workers=max(1,min(a.max_workers,len(pending) or 1))) as pool:
   fs={pool.submit(evaluate_one,r,base,a.radius_arcmin):r for r in pending}
   for f in as_completed(fs):
    try:rows.append(f.result())
    except Exception as exc:
     r=fs[f];rows.append({"truth_id":r.truth_id,"axis":r.truth_axis,"truth_class":r.truth_class,"predicted_class":"ERROR","status":repr(exc),"raw_score":math.nan,"match":False,"classified":False,"sep_arcsec":math.nan,"collectors":"[]"})
    pd.DataFrame(rows).to_csv(checkpoint,index=False)
    if len(rows)%10==0:print(f"checkpoint: {len(rows)}/{len(truth)}",flush=True)
 result=pd.DataFrame(rows);write_report(result,a.out_dir);checkpoint.unlink(missing_ok=True);print(result.groupby(["axis","truth_class"])[["classified","match"]].mean())
if __name__=="__main__":main()

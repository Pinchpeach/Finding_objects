"""Replay Stage 5 on the saved truth-matched evidence of sets A and B with evidence edits; score blind."""
import sys, json, importlib.util, tempfile, numpy as np, pandas as pd
from pathlib import Path
S=Path(sys.argv[1]); V2=Path('/home/user/Finding_objects/v2')
spec=importlib.util.spec_from_file_location('s5r',V2/'Preprocess/05_likelihood_vectors.py'); s5=importlib.util.module_from_spec(spec); spec.loader.exec_module(s5)
m=pd.read_csv(S/'final_matches_full.csv',low_memory=False) if (S/'final_matches_full.csv').exists() else None
def load():
    import types; sys.path.insert(0,str(V2/'benchmark')); sys.path.insert(0,str(V2))
    import score_independent_fields as sf, host_groups as hg
    real=pd.read_csv; cache={}
    sf.pd=types.SimpleNamespace(**{n:getattr(pd,n) for n in dir(pd) if not n.startswith('__')}); sf.pd.read_csv=lambda p,*a,**k: cache[str(p)].copy() if str(p) in cache else real(p,*a,**k)
    bench=sf.benchmark_positions(); rows=[]
    for s,root in (('A','independent_fields'),('B','independent_fields_b')):
        for f in sorted((S/'vd/v2/benchmark'/root).iterdir()):
            p=f/'objects_blind.csv.gz'
            if not p.exists() or not (f/'truth').exists(): continue
            o=hg.attach_galaxy_fragments(real(p,low_memory=False)); cache[str(p)]=o
            mm,_=sf.field_matches(f,'blind',bench)
            if not len(mm): continue
            ev=real(f/'objects_blind_evidence.csv.gz')[['object_id','evidence_json']]
            # class of a fragment comes from its parent: replay the object that decides the class
            mm['decider']=mm.parent_object_id.where(mm.parent_object_id.notna(),mm.object_id)
            d=o.set_index('object_id').loc[mm.decider.values].reset_index().rename(columns={'index':'object_id'})
            d=d.merge(ev,on='object_id',how='left')
            d['set']=s; d['field']=f.name; d['t_truth']=mm.t_truth.values; d['saved']=mm.ours.values
            rows.append(d)
    return pd.concat(rows,ignore_index=True)
if m is None:
    m=load(); m.to_csv(S/'final_matches_full.csv',index=False)
OUT_COLS=('primary_class','primary_confidence','primary_margin','classification_status','classification_basis','best_candidate_','p_','likelihood_','field_prior_','coarse_')
def stage5(d):
    d=d[[c for c in d.columns if not c.startswith(OUT_COLS)]]
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'e.csv'; o=Path(td)/'l.csv'; d.to_csv(p,index=False); s5.run(p,o)
        return pd.read_csv(o,usecols=['primary_class','classification_status','primary_confidence'])
def score(tag,d,pred):
    ok=pred.primary_class.values==d.t_truth.values
    out={'tag':tag}
    for s in ('A','B'):
        h=(d.set==s).values; out[f'acc_{s}']=round(100*ok[h].mean(),3)
    sg=d.field.str.contains('sgp').values; out['sgp']=round(100*ok[sg].mean(),2)
    for c in ('STAR','GALAXY','QSO'):
        h=(d.t_truth==c).values; out[c]=int(ok[h].sum())
    print(out,flush=True); return ok

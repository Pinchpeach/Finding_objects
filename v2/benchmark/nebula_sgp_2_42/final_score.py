"""2.42.0: score A/B blind (fragment rule applied everywhere), diff vs 2.41.0 per object, attribute by classification_basis."""
# Usage: python THIS.py DIR -- DIR holds a validation-data worktree at DIR/vd and the 2.41.0 per-object scores at DIR/final_matches.csv (galaxy_yso_2_41/final_score.py output).
import sys, types, pandas as pd
from pathlib import Path
S=Path(sys.argv[1]); sys.path.insert(0,'/home/user/Finding_objects/v2/benchmark'); sys.path.insert(0,'/home/user/Finding_objects/v2')
import score_independent_fields as sf, host_groups as hg
cache={}; real=pd.read_csv
sf.pd=types.SimpleNamespace(**{n:getattr(pd,n) for n in dir(pd) if not n.startswith('__')}); sf.pd.read_csv=lambda p,*a,**k: cache[str(p)].copy() if str(p) in cache else real(p,*a,**k)
bench=sf.benchmark_positions(); rows=[]
for s,root in (('A','independent_fields'),('B','independent_fields_b')):
    for f in sorted((S/'vd/v2/benchmark'/root).iterdir()):
        p=f/'objects_blind.csv.gz'
        if not p.exists() or not (f/'truth').exists(): continue
        cache[str(p)]=hg.attach_galaxy_fragments(real(p,low_memory=False))
        m,_=sf.field_matches(f,'blind',bench)
        if len(m): rows.append(m.assign(set=s,field=f.name))
m=pd.concat(rows); m.to_csv(S/'final242_matches.csv',index=False)
hc=m.high_confidence.fillna(False).astype(bool)
for s in ('A','B'):
    h=m[m.set==s]; hh=hc[m.set==s]
    print(s,'n',len(h),'acc %.2f'%(100*(h.t_truth==h.ours).mean()),{c:'%.1f'%(100*((h.t_truth==c)&(h.ours==c)).sum()/(h.t_truth==c).sum()) for c in ('STAR','GALAXY','QSO')},
          'unknown %.2f'%(100*(h.ours=='UNKNOWN').mean()),'HC n',int(hh.sum()),'HC acc %.2f'%(100*(h.t_truth==h.ours)[hh].mean()))
old=pd.read_csv(S/'final_matches.csv'); k=['set','field','t_ra','t_dec']
j=m.merge(old[k+['ours']],on=k,suffixes=('','_old'))
j['ok']=j.t_truth==j.ours; j['ok_old']=j.t_truth==j.ours_old
j['basis']=j.classification_basis.fillna('evidence') if 'classification_basis' in j else 'evidence'
# a fragment's class comes from its parent; its own basis may still say evidence
print('paired',len(j),'fixed',int((j.ok&~j.ok_old).sum()),'new errors',int((~j.ok&j.ok_old).sum()))
d=j[j.ok!=j.ok_old].copy(); d['kind']=d.field.str.extract(r'^b?([a-z0-9]+)_')[0]
print(pd.crosstab([d.basis,d.t_truth],d.ok).to_string())
print(pd.crosstab([d.kind],d.ok).to_string())
d[~d.ok][['set','field','t_truth','ours_old','ours','basis','classification_status']].to_csv(S/'final242_new_errors.csv',index=False)
m['kind']=m.field.str.extract(r'^b?([a-z0-9]+)_')[0]; old['kind']=old.field.str.extract(r'^b?([a-z0-9]+)_')[0]
t=[]
for kk in sorted(m.kind.unique()):
    a=m[m.kind==kk]; b=old[old.kind==kk]
    t.append((kk,len(a),round(100*(a.t_truth==a.ours).mean(),1),round(100*(b.t_truth==b.ours).mean(),1)))
print(pd.DataFrame(t,columns=['kind','n','new','old']).to_string(index=False))
for f in ('sfr_onc','sfr_ngc2024','sfr_m8','sfr_ngc2264','sfr_carina','sfr_m16'):
    a=j[j.field==f]
    if len(a): print(f,len(a),'%.1f -> %.1f'%(100*a.ok_old.mean(),100*a.ok.mean()))

"""2.41.0 final: apply attach_galaxy_fragments to every field (re-run fields already have it), score blind, diff vs 2.40.0."""
# Usage: python THIS.py DIR [...]  -- DIR holds a validation-data worktree at DIR/vd (v2/benchmark/independent_fields*); final_score.py also needs the 2.40.0 blind scores at DIR/v239b and DIR/vB.
import sys, types, pandas as pd, numpy as np
from pathlib import Path
S=Path(sys.argv[1]); sys.path.insert(0,'/home/user/Finding_objects/v2/benchmark'); sys.path.insert(0,'/home/user/Finding_objects/v2')
import score_independent_fields as sf, host_groups as hg
cache={}; real=pd.read_csv
sf.pd=types.SimpleNamespace(**{n:getattr(pd,n) for n in dir(pd) if not n.startswith('__')}); sf.pd.read_csv=lambda p,*a,**k: cache[str(p)].copy() if str(p) in cache else real(p,*a,**k)
bench=sf.benchmark_positions(); out=[]
for s,root in (('A','independent_fields'),('B','independent_fields_b')):
    for f in sorted((S/'vd/v2/benchmark'/root).iterdir()):
        p=f/'objects_blind.csv.gz'
        if not p.exists() or not (f/'truth').exists(): continue
        cache[str(p)]=hg.attach_galaxy_fragments(real(p,low_memory=False))
        m,_=sf.field_matches(f,'blind',bench)
        if len(m):
            m=m.assign(set=s,field=f.name); out.append(m[['set','field','t_ra','t_dec','t_truth','ours','high_confidence']])
m=pd.concat(out); m.to_csv(S/'final_matches.csv',index=False)
old=pd.concat([pd.read_csv(S/'v239b/blind/matches_blind.csv',low_memory=False).assign(set='A'),pd.read_csv(S/'vB/blind/matches_blind.csv',low_memory=False).assign(set='B')])
for s in ('A','B'):
    h=m[m.set==s]; print(s,'n',len(h),'acc %.2f'%(100*(h.t_truth==h.ours).mean()), {c:'%.1f'%(100*((h.t_truth==c)&(h.ours==c)).sum()/(h.t_truth==c).sum()) for c in ('STAR','GALAXY','QSO')},
          'unknown %.2f'%(100*(h.ours=='UNKNOWN').mean()), 'HC n',int(h.high_confidence.fillna(False).astype(bool).sum()),'HC acc %.2f'%(100*(h.t_truth==h.ours)[h.high_confidence.fillna(False).astype(bool)].mean()))
    o=old[old.set==s]
k=['set','field','t_ra','t_dec']
j=m.merge(old[k+['t_truth','ours']],on=k,suffixes=('','_old'))
j['ok']=j.t_truth==j.ours; j['ok_old']=j.t_truth==j.ours_old
print('paired',len(j),'fixed',int((j.ok&~j.ok_old).sum()),'new errors',int((~j.ok&j.ok_old).sum()))
d=j[j.ok!=j.ok_old]; print(d.groupby([d.field.str.split('_').str[0],'t_truth','ok']).size().to_string())
print(d[~d.ok][['field','t_truth','ours_old','ours']].to_string())

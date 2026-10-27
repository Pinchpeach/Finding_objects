import sys, json, types, time, math, numpy as np, pandas as pd
# Usage: python THIS.py DIR [...]  -- DIR holds a validation-data worktree at DIR/vd (v2/benchmark/independent_fields*); final_score.py also needs the 2.40.0 blind scores at DIR/v239b and DIR/vB.
from pathlib import Path
S=Path(sys.argv[1]); V2=Path('/home/user/Finding_objects/v2'); sys.path.insert(0,str(V2/'benchmark')); sys.path.insert(0,str(V2))
import score_independent_fields as sf, host_groups as hg
ROOTS={'A':S/'vd/v2/benchmark/independent_fields','B':S/'vd/v2/benchmark/independent_fields_b'}
cache={}; real_read=pd.read_csv
def shim_read(p,*a,**k): return cache[str(p)].copy() if str(p) in cache else real_read(p,*a,**k)
sf.pd=types.SimpleNamespace(**{n:getattr(pd,n) for n in dir(pd) if not n.startswith('__')}); sf.pd.read_csv=shim_read
fields=[(s,f,real_read(f/'objects_blind.csv.gz',low_memory=False)) for s,root in ROOTS.items() for f in sorted(root.iterdir()) if (f/'objects_blind.csv.gz').exists()]
bench=sf.benchmark_positions()
def run(K,DM,MINR,kinds):
    hg.FRAG_RADII,hg.FRAG_FAINTER_MAG,hg.FRAG_MIN_ARCSEC,hg.FRAG_KINDS=K,DM,MINR,tuple(kinds.split('+'))
    ms=[]; real=0; ctl=0.0
    for s,f,o in fields:
        g=hg.attach_galaxy_fragments(o); real+=int((g.component_role=='fragment').sum())
        typ=o.desi_legacy_surveys_dr10__type.astype(str).str.upper() if 'desi_legacy_surveys_dr10__type' in o else pd.Series('',index=o.index)
        host=(typ.isin(hg.EXTENDED_TYPES)&o.primary_class.eq('GALAXY')).to_numpy()
        if host.any():
            for dx,dy in ((30,0),(0,30)):
                c=o.copy(); c.loc[~host,'ra']+=dx/3600/math.cos(math.radians(o.dec.median())); c.loc[~host,'dec']+=dy/3600
                ctl+=int((hg.attach_galaxy_fragments(c).component_role=='fragment').sum())/2
        if (f/'truth').exists():
            cache[str(f/'objects_blind.csv.gz')]=g
            m,_=sf.field_matches(f,'blind',bench)
            if len(m): m['set']=s; ms.append(m[['set','t_truth','ours']])
    m=pd.concat(ms); out={'K':K,'DM':DM,'MINR':MINR,'kinds':kinds,'grouped':real,'chance':round(ctl/max(real,1),3),'excess':round(real-ctl)}
    for s in ('A','B'):
        h=m[m.set==s]; out[f'acc_{s}']=round(100*(h.t_truth==h.ours).mean(),3)
        for c in ('STAR','GALAXY'): out[f'{s}_{c}']=int(((h.t_truth==c)&(h.ours==c)).sum())
    print(out,flush=True); return out
grid=[tuple(g) for g in json.loads(sys.argv[2])]
pd.DataFrame([run(*g) for g in grid]).to_csv(sys.argv[3],index=False)

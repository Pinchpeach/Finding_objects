"""Retrieve actual catalog rows/units for counterparts found in the completed status pass."""
from __future__ import annotations
import json,time
from pathlib import Path
import pandas as pd
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u
IN=Path('data/multi/multisurvey_status.csv'); OUT=Path('results/batch1000_photometry'); CP=OUT/'checkpoint.jsonl'
CAT={'GALEX':'II/335/galex_ais','Pan-STARRS_DR1':'II/349/ps1','2MASS':'II/246/out','AllWISE':'II/328/allwise','NVSS':'VIII/65/nvss','FIRST':'VIII/92/first14','Planck_PCCS2':'VIII/100/pcnt','XMM_4XMM':'IX/65/xmm4dr13s'}
def clean(v):
 try:
  if getattr(v,'mask',False): return None
  if hasattr(v,'item'): v=v.item()
  if isinstance(v,bytes): return v.decode(errors='replace')
  if isinstance(v,float) and pd.isna(v): return None
  return v
 except Exception:return str(v)
def query(row,retries=5):
 last=None
 for n in range(retries+1):
  try:
   Vizier.TIMEOUT=60; q=Vizier(columns=['*','+_r'],row_limit=5)
   t=q.query_region(SkyCoord(row.ra*u.deg,row.dec*u.deg),radius=float(row.radius_arcsec)*u.arcsec,catalog=CAT[row.survey])
   if not t or len(t[0])==0:return {'status':'vanished_match'}
   tab=t[0]; j=0
   if '_r' in tab.colnames:
    import numpy as np;j=int(np.nanargmin(np.asarray(tab['_r'],dtype=float)))
   vals={c:clean(tab[c][j]) for c in tab.colnames}
   units={c:(str(getattr(tab[c],'unit',None)) if getattr(tab[c],'unit',None) is not None else None) for c in tab.colnames}
   return {'status':'available','values':vals,'units':units}
  except Exception as e:
   last=e
   if n<retries:time.sleep(min(30,2**n))
 return {'status':'no_response','error':str(last)}
def main():
 d=pd.read_csv(IN,dtype={'objid':str}); d=d[d.status=='available']; OUT.mkdir(parents=True,exist_ok=True)
 done=set()
 if CP.exists():
  for s in CP.read_text().splitlines():
   if s.strip():
    x=json.loads(s)
    if x['status']!='no_response':done.add((x['objid'],x['survey']))
 with CP.open('a',encoding='utf8') as f:
  for r in d.itertuples():
   if (r.objid,r.survey) in done:continue
   x={'objid':r.objid,'survey':r.survey,'ra':float(r.ra),'dec':float(r.dec),**query(r)}
   f.write(json.dumps(x,default=str)+'\n');f.flush()
 rows=[json.loads(x) for x in CP.read_text().splitlines() if x.strip()]; latest={(x['objid'],x['survey']):x for x in rows}
 nr=sum(x['status']=='no_response' for x in latest.values()); expected=len(d)
 (OUT/'summary.json').write_text(json.dumps({'expected_matches':expected,'completed':len(latest),'no_response':nr,'complete':len(latest)==expected and nr==0},indent=2))
 if len(latest)!=expected or nr:raise SystemExit(2)
if __name__=='__main__':main()

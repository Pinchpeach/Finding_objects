"""Small NGC 4522 integration collection test."""
from pathlib import Path
import importlib.util, traceback
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
RA=188.4155
DEC=9.1751
RADIUS_ARCMIN=0.5
ROOT=Path(__file__).resolve().parents[1]
GET=ROOT/"Get_data"; OUT=ROOT/"rawdata"; OUT.mkdir(exist_ok=True)
modules=["gaia_dr3","sdss_dr18","panstarrs1","desi_legacy","galex","twomass","allwise","lotss","first","nvss","vlass","xmm","chandra","erosita","sdss_spectroscopy","desi_spectroscopy","lamost_spectroscopy","simbad","ned"]
summary=[]
for name in modules:
 try:
  spec=importlib.util.spec_from_file_location(name,GET/f"{name}.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  df=m.fetch(RA,DEC,RADIUS_ARCMIN);p=OUT/f"{name}_ngc4522_r0p5arcmin.csv";m.save(df,p)
  from astropy.coordinates import SkyCoord\n  import astropy.units as u\n  maxsep=None\n  if len(df) and {"ra","dec"}.issubset(df.columns):\n   cc=SkyCoord(pd.to_numeric(df["ra"],errors="coerce").to_numpy()*u.deg,pd.to_numeric(df["dec"],errors="coerce").to_numpy()*u.deg);cen=SkyCoord(RA*u.deg,DEC*u.deg);maxsep=float(cen.separation(cc).arcmin.max())\n  status="ok" if maxsep is None or maxsep <= RADIUS_ARCMIN+1e-6 else "radius_error"\n  summary.append({"collector":name,"status":status,"rows":len(df),"max_sep_arcmin":maxsep,"file":str(p.relative_to(ROOT))})
 except Exception as e:
  summary.append({"collector":name,"status":"error","rows":0,"error":repr(e)})
  traceback.print_exc()
pd.DataFrame(summary).to_csv(OUT/"ngc4522_r0p5arcmin_summary.csv",index=False)
print(pd.DataFrame(summary).to_string(index=False))

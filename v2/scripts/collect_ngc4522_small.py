"""Small NGC 4522 integration collection test."""
from pathlib import Path
import importlib.util, traceback
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
  summary.append({"collector":name,"status":"ok","rows":len(df),"file":str(p.relative_to(ROOT))})
 except Exception as e:
  summary.append({"collector":name,"status":"error","rows":0,"error":repr(e)})
  traceback.print_exc()
import pandas as pd
pd.DataFrame(summary).to_csv(OUT/"ngc4522_r0p5arcmin_summary.csv",index=False)
print(pd.DataFrame(summary).to_string(index=False))

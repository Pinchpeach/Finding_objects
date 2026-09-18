"""Normalize retrieved measurements and build conservative SED/candidate outputs."""
import json, math
from pathlib import Path
import pandas as pd
import numpy as np
BASE=Path('data/base/sample.csv'); PHOTO=Path('data/photo/checkpoint.jsonl'); OUT=Path('results/batch1000_analysis')
# effective wavelengths (um); catalog magnitude systems explicitly tracked
BANDS={'SDSS_u':.3551,'SDSS_g':.4686,'SDSS_r':.6165,'SDSS_i':.7481,'SDSS_z':.8931,'GALEX_FUV':.153,'GALEX_NUV':.231,'PS1_g':.481,'PS1_r':.617,'PS1_i':.752,'PS1_z':.866,'PS1_y':.962,'2MASS_J':1.235,'2MASS_H':1.662,'2MASS_Ks':2.159,'WISE_W1':3.4,'WISE_W2':4.6,'WISE_W3':12.,'WISE_W4':22.}
VEGA_JY={'2MASS_J':1594.,'2MASS_H':1024.,'2MASS_Ks':666.7,'WISE_W1':309.540,'WISE_W2':171.787,'WISE_W3':31.674,'WISE_W4':8.363}
def abjy(m): return 3631.*10**(-0.4*float(m))
def vegajy(m,b): return VEGA_JY[b]*10**(-0.4*float(m))
def add(out,obj,survey,band,val,unit,kind,system=None,sep=None):
 try:
  if val is None or not np.isfinite(float(val)): return
  x={'objid':obj,'survey':survey,'band':band,'value':float(val),'unit':unit,'quantity_kind':kind,'mag_system':system,'wavelength_um':BANDS.get(band),'separation_arcsec':sep,'flux_jy':None}
  if kind=='magnitude': x['flux_jy']=abjy(val) if system=='AB' else vegajy(val,band)
  out.append(x)
 except (ValueError,TypeError,KeyError): pass
def first(v,*names):
 for n in names:
  if n in v and v[n] is not None:return v[n]
def main():
 OUT.mkdir(parents=True,exist_ok=True); base=pd.read_csv(BASE,dtype={'objid':str}); rows=[]
 for r in base.itertuples():
  for b in 'ugriz': add(rows,r.objid,'SDSS','SDSS_'+b,getattr(r,b),'mag','magnitude','AB',0.0)
 rec=[json.loads(x) for x in PHOTO.read_text().splitlines() if x.strip()]
 assoc=[]
 for x in rec:
  v=x['values']; u=x['units']; s=x['survey']; obj=x['objid']; sep=first(v,'_r'); assoc.append({'objid':obj,'survey':s,'separation_arcsec':sep,'association':'positional_candidate','association_note':'nearest catalog row within survey-specific search radius; not proof of physical identity'})
  if s=='GALEX':
   for k,b in [('FUVmag','GALEX_FUV'),('NUVmag','GALEX_NUV')]: add(rows,obj,s,b,v.get(k),u.get(k) or 'mag','magnitude','AB',sep)
  elif s=='Pan-STARRS_DR1':
   for key,b in [('gmag','PS1_g'),('rmag','PS1_r'),('imag','PS1_i'),('zmag','PS1_z'),('ymag','PS1_y')]: add(rows,obj,s,b,v.get(key),u.get(key) or 'mag','magnitude','AB',sep)
  elif s=='2MASS':
   for key,b in [('Jmag','2MASS_J'),('Hmag','2MASS_H'),('Kmag','2MASS_Ks')]: add(rows,obj,s,b,v.get(key),u.get(key) or 'mag','magnitude','Vega',sep)
  elif s=='AllWISE':
   for key,b in [('W1mag','WISE_W1'),('W2mag','WISE_W2'),('W3mag','WISE_W3'),('W4mag','WISE_W4')]: add(rows,obj,s,b,v.get(key),u.get(key) or 'mag','magnitude','Vega',sep)
  elif s in ('NVSS','FIRST'):
   for key in ('S1.4','Fint','Fpeak','Speak'):
    if key in v and v[key] is not None: add(rows,obj,s,'RADIO_1.4GHz',v[key],u.get(key),'flux_density',None,sep)
 norm=pd.DataFrame(rows); norm.to_csv(OUT/'normalized_measurements.csv',index=False); pd.DataFrame(assoc).to_csv(OUT/'counterpart_associations.csv',index=False)
 # SED table uses only photometric bands convertible to Jy; no fabricated spectra/lines.
 sed=norm[norm.flux_jy.notna()].copy(); sed.to_csv(OUT/'sed_points.csv',index=False)
 wide=sed.pivot_table(index='objid',columns='band',values='value',aggfunc='first'); candidates=[]
 for obj,r in wide.iterrows():
  tags=[]; evidence=[]; counter=[]
  if pd.notna(r.get('WISE_W1')) and pd.notna(r.get('WISE_W2')) and r['WISE_W1']-r['WISE_W2']>0.8: tags.append('mid-IR-red/AGN-like candidate'); evidence.append('W1-W2 > 0.8 (Vega)'); counter.append('color selection alone is not a secure AGN identification')
  if pd.notna(r.get('SDSS_u')) and pd.notna(r.get('SDSS_g')) and r['SDSS_u']-r['SDSS_g']<0.6: tags.append('blue optical candidate'); evidence.append('u-g < 0.6 AB'); counter.append('blue color is degenerate among stars, QSOs and compact galaxies')
  if not tags: tags=['unclassified photometric source']; counter=['available broad-band data do not meet the limited conservative flags used here']
  candidates.append({'objid':obj,'candidate_labels':' | '.join(tags),'evidence':' | '.join(evidence),'counterevidence_or_uncertainty':' | '.join(counter),'classification_strength':'heuristic_flag_only'})
 cand=pd.DataFrame(candidates); cand.to_csv(OUT/'candidate_assessment.csv',index=False)
 counts=norm.groupby(['survey','quantity_kind']).size().reset_index(name='n').to_dict('records'); summ={'objects':int(base.objid.nunique()),'retrieved_counterparts':len(rec),'normalized_measurements':len(norm),'sed_points':len(sed),'objects_with_sed_points':int(sed.objid.nunique()),'spectrum_line_analysis':'not_performed: retrieved products contain catalog photometry/radio measurements, not spectra','classification_policy':'heuristic candidate flags only; no probabilities and no physical-identity assertion','counts_by_survey_quantity':counts}
 (OUT/'summary.json').write_text(json.dumps(summ,indent=2)); (OUT/'README.txt').write_text('Outputs are evidence-preserving. counterpart_associations are positional candidates only. SED fluxes: AB uses 3631 Jy zero point; 2MASS/WISE Vega conversions use standard catalog zero-point flux densities. No spectral lines are inferred without spectra.\n')
if __name__=='__main__':main()

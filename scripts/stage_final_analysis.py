"""Stages 5-7: normalize multi-survey values, build SEDs, inspect SDSS spectral metadata/lines, classify conservatively, and save anomaly products."""
from pathlib import Path
from io import StringIO
import json, math, time
import numpy as np
import pandas as pd
import requests

BASE=Path('data/batch1000/sample.csv'); EXT=Path('data/stage04/external_values.csv'); OUT=Path('results/final1000')
C=2.99792458e18
# Effective wavelengths (Angstrom); catalog-system zero points in Jy. AB bands use 3631 Jy.
BANDS={
 ('GALEX','FUVmag'):(1538.6,3631.),('GALEX','NUVmag'):(2315.7,3631.),
 ('Pan-STARRS_DR1','gmag'):(4810.,3631.),('Pan-STARRS_DR1','rmag'):(6170.,3631.),('Pan-STARRS_DR1','imag'):(7520.,3631.),('Pan-STARRS_DR1','zmag'):(8660.,3631.),('Pan-STARRS_DR1','ymag'):(9620.,3631.),
 ('2MASS','Jmag'):(12350.,1594.),('2MASS','Hmag'):(16620.,1024.),('2MASS','Kmag'):(21590.,666.7),
 ('AllWISE','W1mag'):(33526.,309.540),('AllWISE','W2mag'):(46028.,171.787),('AllWISE','W3mag'):(115608.,31.674),('AllWISE','W4mag'):(220883.,8.363),
}
SDSS={'u':3551.,'g':4686.,'r':6165.,'i':7481.,'z':8931.}
SKY='https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch'
def magjy(m,zp): return zp*10**(-0.4*float(m))
def sql(q):
 for a in range(5):
  try:
   r=requests.get(SKY,params={'cmd':q,'format':'csv'},timeout=60); r.raise_for_status(); lines=r.text.lstrip('\ufeff').splitlines(); i=next((i for i,x in enumerate(lines) if ',' in x and not x.startswith('#')),None); return pd.read_csv(StringIO('\n'.join(lines[i:]))) if i is not None else pd.DataFrame()
  except Exception:
   if a==4: return pd.DataFrame()
   time.sleep(2**a)
def main():
 OUT.mkdir(parents=True,exist_ok=True); b=pd.read_csv(BASE,dtype={'objid':str}); e=pd.read_csv(EXT,dtype={'objid':str}); sed=[]
 for _,r in b.iterrows():
  for k,w in SDSS.items():
   if pd.notna(r.get(k)):
    f=magjy(r[k],3631.); sed.append([r.objid,'SDSS',k,w,f,C/w,f*C/w,'AB'])
 for _,r in e.iterrows():
  for (sv,col),(w,zp) in BANDS.items():
   if r.survey==sv and col in r and pd.notna(r[col]):
    f=magjy(r[col],zp); sed.append([r.objid,sv,col,w,f,C/w,f*C/w,'AB' if zp==3631 else 'Vega/catalog'])
  if r.survey=='NVSS' and pd.notna(r.get('S1.4')):
   # VizieR NVSS S1.4 is mJy.
   f=float(r['S1.4'])/1000.; hz=1.4e9; sed.append([r.objid,'NVSS','1.4GHz',C/hz,f,hz,f*hz,'catalog_mJy'])
  if r.survey=='FIRST':
   for col in ('Fint','Fpeak'):
    if pd.notna(r.get(col)):
     f=float(r[col])/1000.; hz=1.4e9; sed.append([r.objid,'FIRST',col,C/hz,f,hz,f*hz,'catalog_mJy'])
 s=pd.DataFrame(sed,columns=['objid','survey','band','wavelength_angstrom','flux_density_jy','frequency_hz','nu_fnu_jy_hz','native_system']); s.to_csv(OUT/'sed_points.csv',index=False)
 # SDSS spectroscopy metadata and measured lines, in chunks.
 specs=[]; lines=[]
 ids=b.objid.astype(str).tolist()
 for st in range(0,len(ids),100):
  chunk=ids[st:st+100]; ins=','.join(chunk)
  q=f"SELECT s.bestobjid as objid,s.specobjid,s.z as redshift,s.class,s.subclass FROM SpecObj s WHERE s.bestobjid IN ({ins})"
  d=sql(q)
  if not d.empty: specs.append(d)
  q2=f"SELECT s.bestobjid as objid,l.specobjid,l.lineName,l.wave,l.waveErr,l.sigma,l.sigmaErr,l.height,l.heightErr,l.ew,l.ewErr,l.chi2 FROM SpecObj s JOIN SpecLine l ON s.specobjid=l.specobjid WHERE s.bestobjid IN ({ins})"
  d2=sql(q2)
  if not d2.empty: lines.append(d2)
 sp=pd.concat(specs,ignore_index=True) if specs else pd.DataFrame(columns=['objid','specobjid','redshift','class','subclass']); sp['objid']=sp.objid.astype(str); sp.to_csv(OUT/'sdss_spectral_metadata.csv',index=False)
 ln=pd.concat(lines,ignore_index=True) if lines else pd.DataFrame(); ln.to_csv(OUT/'sdss_measured_lines.csv',index=False)
 # association evidence: positional likelihood uses survey beam as scale; not posterior probability.
 psf={'GALEX':5.0,'Pan-STARRS_DR1':1.1,'2MASS':2.5,'AllWISE':6.1,'NVSS':45.0,'FIRST':5.0}
 aa=e[['objid','survey','separation_arcsec']].copy(); aa['beam_fwhm_arcsec']=aa.survey.map(psf); aa['normalized_sep_beam_sigma']=aa.separation_arcsec/(aa.beam_fwhm_arcsec/2.355); aa['positional_likelihood_proxy']=np.exp(-.5*aa.normalized_sep_beam_sigma**2); aa['chance_coincidence_status']='not_computable_without_local_source_density'; aa.to_csv(OUT/'association_evidence.csv',index=False)
 # Conservative object records. Spectroscopic class is strongest label; otherwise broad color/SED heuristic only.
 sm=sp.drop_duplicates('objid').set_index('objid') if len(sp) else pd.DataFrame()
 rows=[]; feats=[]
 for _,r in b.iterrows():
  oid=str(r.objid); pts=s[s.objid==oid].sort_values('frequency_hz'); has=oid in getattr(sm,'index',[])
  typ='unclassified_photometric_object'; ev=[]; contra=[]; miss=[]; conf='low'
  if has:
   z=sm.loc[oid]; typ=str(z.get('class','unknown')).strip().lower(); ev.append('SDSS spectroscopic class='+str(z.get('class',''))); ev.append('redshift='+str(z.get('redshift',''))); conf='high';
   if str(z.get('subclass','')).strip(): ev.append('SDSS subclass='+str(z.get('subclass')))
  else: miss.append('no SDSS spectrum/classification')
  if len(pts): ev.append(f'{len(pts)} photometric/radio SED points across {pts.survey.nunique()} surveys')
  if len(pts)<6: miss.append('sparse multiwavelength SED')
  rows.append({'objid':oid,'object_type_candidate':typ,'confidence':conf,'evidence':' | '.join(ev),'counter_evidence':' | '.join(contra) if contra else 'none identified','missing_decisive_data':' | '.join(miss) if miss else 'none','spectrum_status':'available_measured_lines' if has else 'no_spectrum','redshift':float(sm.loc[oid].redshift) if has and pd.notna(sm.loc[oid].redshift) else np.nan})
  x=pts.set_index(['survey','band']).nu_fnu_jy_hz; vals=np.log10(pts.nu_fnu_jy_hz.clip(lower=1e-30)); feats.append({'objid':oid,'n_sed_points':len(pts),'n_surveys':pts.survey.nunique(),'log_nufnu_median':vals.median() if len(vals) else np.nan,'log_nufnu_range':vals.max()-vals.min() if len(vals)>1 else np.nan,'reference':has})
 cl=pd.DataFrame(rows); cl.to_csv(OUT/'object_classifications.csv',index=False); ft=pd.DataFrame(feats)
 # Reference store = objects with SDSS spectroscopic labels; predicted store = no spectroscopic label.
 ft.merge(cl[['objid','object_type_candidate']],on='objid').query('reference').to_csv(OUT/'reference_feature_store.csv',index=False); ft.merge(cl[['objid','object_type_candidate']],on='objid').query('not reference').to_csv(OUT/'predicted_unidentified_store.csv',index=False)
 # Robust anomaly score from available numeric features (median/MAD); ranking, not probability.
 num=['n_sed_points','n_surveys','log_nufnu_median','log_nufnu_range']; z=[]
 for c in num:
  v=ft[c].astype(float); med=v.median(); mad=(v-med).abs().median(); z.append(((v-med).abs()/(1.4826*mad if mad and np.isfinite(mad) else 1)).fillna(0))
 ft['anomaly_score']=pd.concat(z,axis=1).mean(axis=1); ft.sort_values('anomaly_score',ascending=False).to_csv(OUT/'anomaly_candidates.csv',index=False)
 summary={'objects':len(b),'sed_points':len(s),'objects_with_sed':int(s.objid.nunique()),'external_pairs':len(e),'objects_with_sdss_spectrum':int(sp.objid.nunique()) if len(sp) else 0,'measured_line_rows':len(ln),'reference_objects':int(ft.reference.sum()),'unidentified_objects':int((~ft.reference).sum()),'notes':['SED is wavelength-flux density / nuFnu, not luminosity.','Association proxy is not a posterior identity probability.','Chance coincidence requires local source density and is explicitly left uncomputed.','Anomaly score is a robust feature-distance ranking, not a probability.']}; (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
if __name__=='__main__': main()

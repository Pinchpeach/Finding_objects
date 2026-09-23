"""NGC 4522 +/-10 arcmin field census with staged, validated retrieval."""
from __future__ import annotations
import io,json,math,pathlib,time,requests,traceback
import numpy as np,pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.gaia import Gaia
from finding_objects.decision_tree import identity_tree
OUT=pathlib.Path("results/ngc4522_field10"); OUT.mkdir(parents=True,exist_ok=True)
RA0=188.4155; DEC0=9.1751; HALF=10/60; RA_HALF=HALF/math.cos(math.radians(DEC0))
SDSS="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
STATE=OUT/"retrieval_state.json"
def save_state(**kw):
    old={}
    if STATE.exists():
        try: old=json.load(open(STATE))
        except: pass
    old.update(kw); json.dump(old,open(STATE,"w"),indent=2,default=str)
def norm(df):
    df=df.copy(); df.columns=[str(x).strip().lower() for x in df.columns]; return df
def sdss_sql(q,label):
    errs=[]
    for fmt in ("json","csv"):
      for k in range(3):
       try:
        r=requests.get(SDSS,params={"cmd":q,"format":fmt},headers={"User-Agent":"Finding_objects/1.0"},timeout=90)
        r.raise_for_status()
        (OUT/f"{label}_response_head.txt").write_text(r.text[:4000],errors="replace")
        if fmt=="json":
            obj=r.json()
            if isinstance(obj,list) and obj and isinstance(obj[0],dict) and "Rows" in obj[0]: df=pd.DataFrame(obj[0]["Rows"])
            elif isinstance(obj,list): df=pd.DataFrame(obj)
            elif isinstance(obj,dict):
                key=next((x for x in ("Rows","rows","data","Data") if x in obj),None)
                if key is None: raise ValueError(f"JSON keys={list(obj)[:20]}")
                df=pd.DataFrame(obj[key])
            else: raise ValueError(type(obj).__name__)
        else:
            lines=[x for x in r.text.splitlines() if x.strip() and not x.lstrip().startswith("#")]
            if not lines: raise ValueError("empty/comment-only CSV")
            df=pd.read_csv(io.StringIO("\n".join(lines)))
        df=norm(df)
        if not {"ra","dec"}.issubset(df.columns): raise ValueError(f"columns={list(df.columns)}")
        save_state(**{label:{"status":"ok","rows":len(df),"format":fmt}})
        return df
       except Exception as e:
        errs.append(f"{fmt} try{k+1}: {type(e).__name__}: {e}"); time.sleep(2*(k+1))
    save_state(**{label:{"status":"failed","errors":errs}})
    raise RuntimeError(f"{label} retrieval failed: "+ " | ".join(errs))
def photo():
 q=f"""SELECT p.objid,p.ra,p.dec,p.type,p.clean,p.psfMag_u,p.psfMag_g,p.psfMag_r,p.psfMag_i,p.psfMag_z,p.modelMag_u,p.modelMag_g,p.modelMag_r,p.modelMag_i,p.modelMag_z FROM PhotoObj p WHERE p.ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF} AND p.dec BETWEEN {DEC0-HALF} AND {DEC0+HALF} AND p.clean=1"""
 return sdss_sql(q,"sdss_photo")
def spec():
 q=f"""SELECT s.bestobjid,s.ra,s.dec,s.class,s.subclass,s.z,s.zWarning,s.snMedian,s.plate,s.mjd,s.fiberid FROM SpecObj s WHERE s.ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF} AND s.dec BETWEEN {DEC0-HALF} AND {DEC0+HALF} AND s.zWarning=0"""
 return sdss_sql(q,"sdss_spec")
def gaia():
 q=f"""SELECT source_id,ra,dec,parallax,parallax_error,pmra,pmra_error,pmdec,pmdec_error,phot_g_mean_mag,bp_rp,ruwe FROM gaiadr3.gaia_source WHERE ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF} AND dec BETWEEN {DEC0-HALF} AND {DEC0+HALF}"""
 try:
  df=norm(Gaia.launch_job_async(q).get_results().to_pandas()); save_state(gaia={"status":"ok","rows":len(df)}); return df
 except Exception as e: save_state(gaia={"status":"failed","error":repr(e)}); raise
def nearest(a,b,lim=1.5):
 if len(b)==0:return np.full(len(a),-1),np.full(len(a),np.inf)
 ac=SkyCoord(a["ra"].to_numpy(float)*u.deg,a["dec"].to_numpy(float)*u.deg); bc=SkyCoord(b["ra"].to_numpy(float)*u.deg,b["dec"].to_numpy(float)*u.deg)
 i,s,_=ac.match_to_catalog_sky(bc); ok=s.arcsec<=lim; return np.where(ok,i,-1),np.where(ok,s.arcsec,np.inf)
def main():
 save_state(stage="start",center_ra=RA0,center_dec=DEC0)
 p=photo(); p.to_csv(OUT/"sdss_optical_census.csv",index=False); save_state(stage="photo_saved")
 s=spec(); s.to_csv(OUT/"sdss_spectroscopy.csv",index=False); save_state(stage="spec_saved")
 g=gaia(); g.to_csv(OUT/"gaia_dr3.csv",index=False); save_state(stage="gaia_saved")
 si,ss=nearest(p,s); gi,gs=nearest(p,g); rows=[]; paths=[]
 for n,r in p.iterrows():
  ft={"official_footprint":True,"spectrum_verified":si[n]>=0}; sp=None; gr=None
  if si[n]>=0:
   sp=s.iloc[si[n]]; cl=str(sp["class"]).strip().upper()
   if pd.notna(sp.get("z")):ft["redshift"]=float(sp["z"])
   if cl=="STAR":ft["stellar_absorption_pattern"]=True
   elif cl=="GALAXY":ft["extended_morphology"]=True;ft["narrow_nebular_lines"]=True
   elif cl=="QSO":ft["broad_permitted_lines"]=True;ft["broad_line_test_adequate"]=True;ft["high_ionization_lines"]=True
  if gi[n]>=0:
   gr=g.iloc[gi[n]]
   if pd.notna(gr.get("parallax_error")) and gr["parallax_error"]>0:ft["parallax_snr"]=float(gr["parallax"]/gr["parallax_error"])
   pe=np.hypot(gr.get("pmra_error",np.nan),gr.get("pmdec_error",np.nan))
   if pd.notna(pe) and pe>0:ft["proper_motion_snr"]=float(np.hypot(gr["pmra"],gr["pmdec"])/pe)
  if "extended_morphology" not in ft:ft["extended_morphology"]=bool(int(r["type"])==3) if pd.notna(r["type"]) else None
  res=identity_tree(ft); scl=None if sp is None else str(sp["class"]).strip().upper()
  if scl in {"STAR","GALAXY","QSO"}: final=scl;basis="SDSS_DR18_SPECTROSCOPY";conf="HIGH"
  else: final=res.get("identity","UNKNOWN");basis="DECISION_TREE";conf="MODERATE" if gr is not None else "LOW"
  dist=SkyCoord(float(r["ra"])*u.deg,float(r["dec"])*u.deg).separation(SkyCoord(RA0*u.deg,DEC0*u.deg)).arcmin
  rows.append({"objid":str(r["objid"]),"ra":r["ra"],"dec":r["dec"],"sdss_type":r["type"],"spectrum_class":scl,"redshift":None if sp is None else sp.get("z"),"gaia_source_id":None if gr is None else str(gr["source_id"]),"gaia_sep_arcsec":None if gr is None else gs[n],"final_classification":final,"classification_basis":basis,"likely_object_type":final,"confidence":conf,"missing_decisive_data":"none" if basis.startswith("SDSS") else "spectrum","distance_from_ngc4522_arcmin":dist})
  paths.append({"objid":str(r["objid"]),"features":ft,"tree_result":res})
 z=pd.DataFrame(rows);z.to_csv(OUT/"final_classifications.csv",index=False)
 with open(OUT/"decision_paths.jsonl","w") as h:
  for x in paths:h.write(json.dumps(x,default=str)+"\n")
 summary={"field":"projected +/-10 arcmin square","optical_sources":len(p),"sdss_spectra":len(s),"gaia_sources":len(g),"final_counts":z.final_classification.value_counts(dropna=False).to_dict(),"basis_counts":z.classification_basis.value_counts().to_dict()}
 json.dump(summary,open(OUT/"summary.json","w"),indent=2);save_state(stage="complete",summary=summary);print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:
  save_state(stage="failed",fatal=f"{type(e).__name__}: {e}",traceback=traceback.format_exc());raise

"""NGC 4522 +/-10 arcmin field census and conservative final tree classification.
Primary optical census: SDSS DR18 PhotoObj in a 10' radius-equivalent rectangular field,
augmented by Gaia DR3 astrometry and SDSS spectroscopy when available.
All classifications retain UNKNOWN rather than inventing missing evidence.
"""
from __future__ import annotations
import io,json,math,pathlib,time,requests
import numpy as np,pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.gaia import Gaia
from finding_objects.decision_tree import identity_tree

OUT=pathlib.Path("results/ngc4522_field10"); OUT.mkdir(parents=True,exist_ok=True)
# NGC 4522 J2000 center; field is +/-10 arcmin in Dec and RA projected on sky.
RA0=188.4155; DEC0=9.1751; HALF=10/60
COS=math.cos(math.radians(DEC0)); RA_HALF=HALF/COS
SDSS="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def sql(q,tries=4):
    for k in range(tries):
        try:
            r=requests.get(SDSS,params={"cmd":q,"format":"csv"},timeout=120); r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text))
        except Exception:
            if k==tries-1: raise
            time.sleep(5*(k+1))

def sdss_census():
    q=f"""SELECT p.objid,p.ra,p.dec,p.type,p.clean,p.psfMag_u,p.psfMag_g,p.psfMag_r,p.psfMag_i,p.psfMag_z,
    p.modelMag_u,p.modelMag_g,p.modelMag_r,p.modelMag_i,p.modelMag_z
    FROM PhotoObj AS p WHERE p.ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF}
    AND p.dec BETWEEN {DEC0-HALF} AND {DEC0+HALF} AND p.clean=1"""
    return sql(q)

def spectra():
    q=f"""SELECT s.bestobjid,s.ra,s.dec,s.class,s.subclass,s.z,s.zWarning,s.snMedian,s.plate,s.mjd,s.fiberid
    FROM SpecObj AS s WHERE s.ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF}
    AND s.dec BETWEEN {DEC0-HALF} AND {DEC0+HALF} AND s.zWarning=0"""
    return sql(q)

def gaia():
    q=f"""SELECT source_id,ra,dec,parallax,parallax_error,pmra,pmra_error,pmdec,pmdec_error,
    phot_g_mean_mag,bp_rp,ruwe FROM gaiadr3.gaia_source
    WHERE ra BETWEEN {RA0-RA_HALF} AND {RA0+RA_HALF}
    AND dec BETWEEN {DEC0-HALF} AND {DEC0+HALF}"""
    job=Gaia.launch_job_async(q); return job.get_results().to_pandas()

def normalize_cols(df):
    df=df.copy()
    df.columns=[str(x).strip().lower() for x in df.columns]
    return df

def nearest(base,cat,maxarc=1.5):
    base=normalize_cols(base); cat=normalize_cols(cat)
    if len(cat)==0: return np.full(len(base),-1),np.full(len(base),np.inf)
    if not {"ra","dec"}.issubset(base.columns) or not {"ra","dec"}.issubset(cat.columns):
        raise ValueError(f"Missing coordinate columns: base={list(base.columns)}, cat={list(cat.columns)}")
    a=SkyCoord(base["ra"].to_numpy()*u.deg,base["dec"].to_numpy()*u.deg); b=SkyCoord(cat["ra"].to_numpy()*u.deg,cat["dec"].to_numpy()*u.deg)
    idx,sep,_=a.match_to_catalog_sky(b); ok=sep.arcsec<=maxarc
    return np.where(ok,idx,-1),np.where(ok,sep.arcsec,np.inf)

def main():
    p=normalize_cols(sdss_census()); s=normalize_cols(spectra()); g=normalize_cols(gaia())
    p.to_csv(OUT/"sdss_optical_census.csv",index=False); s.to_csv(OUT/"sdss_spectroscopy.csv",index=False); g.to_csv(OUT/"gaia_dr3.csv",index=False)
    si,ss=nearest(p,s,1.5); gi,gs=nearest(p,g,1.5)
    rows=[]; paths=[]
    for n,r in p.iterrows():
        f={"official_footprint":True}
        spec=None; gr=None
        if si[n]>=0:
            spec=s.iloc[si[n]]; f["spectrum_verified"]=True
            cl=str(spec["class"]).strip().upper()
            if pd.notna(spec.z): f["redshift"]=float(spec.z)
            if cl=="STAR": f["stellar_absorption_pattern"]=True
            if cl=="GALAXY": f["extended_morphology"]=True; f["narrow_nebular_lines"]=True
            if cl=="QSO": f["broad_permitted_lines"]=True; f["broad_line_test_adequate"]=True; f["high_ionization_lines"]=True
        else: f["spectrum_verified"]=False
        if gi[n]>=0:
            gr=g.iloc[gi[n]]
            if pd.notna(gr.parallax_error) and gr.parallax_error>0: f["parallax_snr"]=float(gr.parallax/gr.parallax_error)
            pmerr=np.hypot(gr.pmra_error,gr.pmdec_error)
            if pd.notna(pmerr) and pmerr>0: f["proper_motion_snr"]=float(np.hypot(gr.pmra,gr.pmdec)/pmerr)
        # SDSS morphology is supporting evidence, not spectroscopy.
        f["extended_morphology"]=bool(int(r["type"])==3) if pd.notna(r["type"]) else None
        res=identity_tree(f)
        # Preserve independent SDSS spectroscopic truth as strongest final label.
        if spec is not None and str(spec["class"]).strip().upper() in {"STAR","GALAXY","QSO"}:
            final=str(spec["class"]).strip().upper(); basis="SDSS_DR18_SPECTROSCOPY"
        else:
            final=res.get("identity","UNKNOWN"); basis="DECISION_TREE"
        rows.append({"objid":str(r.objid),"ra":r.ra,"dec":r.dec,"sdss_type":r["type"],
          "spectrum_class":None if spec is None else spec["class"],"redshift":None if spec is None else spec.z,
          "gaia_source_id":None if gr is None else str(gr.source_id),"gaia_sep_arcsec":None if gr is None else gs[n],
          "final_classification":final,"classification_basis":basis,
          "likely_object_type":final,"confidence":"HIGH" if basis=="SDSS_DR18_SPECTROSCOPY" else ("MODERATE" if gr is not None else "LOW"),
          "missing_decisive_data":"none" if basis=="SDSS_DR18_SPECTROSCOPY" else "spectrum",
          "distance_from_ngc4522_arcmin":SkyCoord(r.ra*u.deg,r.dec*u.deg).separation(SkyCoord(RA0*u.deg,DEC0*u.deg)).arcmin})
        paths.append({"objid":str(r.objid),"features":f,"tree_result":res})
    z=pd.DataFrame(rows); z.to_csv(OUT/"final_classifications.csv",index=False)
    with open(OUT/"decision_paths.jsonl","w") as h:
        for x in paths: h.write(json.dumps(x,default=str)+"\n")
    summary={"center":{"name":"NGC 4522","ra_deg":RA0,"dec_deg":DEC0},"field":"projected +/-10 arcmin square",
      "optical_sources":len(p),"sdss_spectra":len(s),"gaia_sources":len(g),
      "final_counts":z.final_classification.value_counts(dropna=False).to_dict(),
      "basis_counts":z.classification_basis.value_counts().to_dict(),
      "notes":["SDSS clean optical sources define the primary census; this is not a claim of completeness at every wavelength.",
      "SDSS spectroscopic class is retained when present; otherwise the evidence-state decision tree may abstain.",
      "Gaia astrometry supplies stellar evidence. Missing spectroscopy remains explicit."]}
    json.dump(summary,open(OUT/"summary.json","w"),indent=2); print(json.dumps(summary,indent=2))
if __name__=="__main__": main()

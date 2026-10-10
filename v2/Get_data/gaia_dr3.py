"""Gaia DR3 collector with layered TAP retrieval and independent VizieR fallback.

The primary path retrieves gaiadr3.gaia_source first, then optional products by
source_id.  If the Gaia TAP service fails completely, VizieR I/355 + I/358 is
used as a read-only fallback so transient archive outages do not erase base
astrometry or variability classification evidence.
"""
from __future__ import annotations
import time
from pathlib import Path
import pandas as pd

CATALOG="Gaia DR3"
SOURCE=["source_id","designation","ra","dec","ra_error","dec_error","parallax","parallax_error","pmra","pmra_error","pmdec","pmdec_error","ruwe","phot_g_mean_flux","phot_g_mean_flux_error","phot_g_mean_mag","phot_bp_mean_flux","phot_bp_mean_flux_error","phot_bp_mean_mag","phot_rp_mean_flux","phot_rp_mean_flux_error","phot_rp_mean_mag","bp_rp","bp_g","g_rp","phot_bp_rp_excess_factor","radial_velocity","radial_velocity_error","rv_nb_transits"]
AP=["teff_gspphot","logg_gspphot","mh_gspphot","distance_gspphot","ag_gspphot","ebpminrp_gspphot","mass_flame","age_flame","evolstage_flame","flags_flame","classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star","classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar"]
VAR_SUMMARY=["in_vari_classification_result","in_vari_rrlyrae","in_vari_cepheid","in_vari_long_period_variable","in_vari_eclipsing_binary","in_vari_rotation_modulation","in_vari_agn","in_vari_microlensing","in_vari_compact_companion"]

# Wall-clock budgets: a slow Gaia archive previously held a field for ~26 min
# in retries; past the budget the VizieR mirror fallback is used instead.
# From CI runners the ESA TAP rarely answers a cone search within 2 min while
# VizieR answers in seconds, so the base budget is short.
BASE_TAP_BUDGET_S=30.0
OPTIONAL_TAP_BUDGET_S=60.0

def _bounded(fn,budget_s,*args):
    # Daemon thread: an abandoned slow query must not block interpreter exit.
    import threading
    box={}
    def target():
        try:box["value"]=fn(*args)
        except BaseException as exc:box["error"]=exc
    t=threading.Thread(target=target,daemon=True);t.start();t.join(budget_s)
    if t.is_alive():raise TimeoutError(f"Gaia TAP exceeded {budget_s:.0f} s")
    if "error" in box:raise box["error"]
    return box["value"]

def _tap(query:str,retries:int=4)->pd.DataFrame:
    from astroquery.gaia import Gaia
    last=None
    for attempt in range(retries):
        try:return Gaia.launch_job_async(query).get_results().to_pandas()
        except Exception as exc:
            last=exc
            if attempt+1<retries:time.sleep(min(8,2**attempt))
    try:return Gaia.launch_job(query).get_results().to_pandas()
    except Exception as exc:raise RuntimeError(f"Gaia TAP failed after retries; async={last!r}; sync={exc!r}") from exc

def _merge_optional(base:pd.DataFrame,table:str,columns:list[str],status_name:str)->pd.DataFrame:
    if base.empty:base[status_name]=pd.Series(dtype="string");return base
    ids=[str(int(x)) for x in pd.to_numeric(base["source_id"],errors="coerce").dropna().unique()]
    if not ids:base[status_name]="missing_source_id";return base
    pieces=[]
    try:
        for start in range(0,len(ids),500):
            chunk=ids[start:start+500];select="source_id,"+",".join(columns)
            pieces.append(_bounded(_tap,OPTIONAL_TAP_BUDGET_S,f"SELECT {select} FROM {table} WHERE source_id IN ({','.join(chunk)})"))
        opt=pd.concat(pieces,ignore_index=True,sort=False) if pieces else pd.DataFrame()
        if not opt.empty:
            opt["source_id"]=pd.to_numeric(opt["source_id"],errors="coerce").astype("Int64");base["source_id"]=pd.to_numeric(base["source_id"],errors="coerce").astype("Int64")
            base=base.merge(opt.drop_duplicates("source_id"),on="source_id",how="left")
        for col in columns:
            if col not in base.columns:base[col]=pd.NA
        base[status_name]="ok"
    except Exception as exc:
        for col in columns:
            if col not in base.columns:base[col]=pd.NA
        base[status_name]="error:"+type(exc).__name__
    return base

def _pick(df,names):
    low={str(c).lower():c for c in df.columns}
    for n in names:
        if n in df.columns:return n
        if n.lower() in low:return low[n.lower()]
    return None

def _vizier_fallback(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    c=SkyCoord(float(ra)*u.deg,float(dec)*u.deg,frame="icrs")
    tabs=Vizier(columns=["**"],row_limit=-1).query_region(c,radius=float(radius_arcmin)*u.arcmin,catalog="I/355/gaiadr3")
    if not tabs:return pd.DataFrame()
    src=tabs[0].to_pandas()
    if src.empty:return src
    mapping={
        "Source":"source_id","RA_ICRS":"ra","DE_ICRS":"dec","e_RA_ICRS":"ra_error","e_DE_ICRS":"dec_error",
        "Plx":"parallax","e_Plx":"parallax_error","pmRA":"pmra","e_pmRA":"pmra_error","pmDE":"pmdec","e_pmDE":"pmdec_error",
        "RUWE":"ruwe","Gmag":"phot_g_mean_mag","BPmag":"phot_bp_mean_mag","RPmag":"phot_rp_mean_mag","BP-RP":"bp_rp",
        "RV":"radial_velocity","e_RV":"radial_velocity_error","Teff":"teff_gspphot","logg":"logg_gspphot","[Fe/H]":"mh_gspphot","Dist":"distance_gspphot",
        # GSP-Phot extinction (used to deredden colours and absolute magnitudes downstream).
        "AG":"ag_gspphot","E(BP-RP)":"ebpminrp_gspphot",
    }
    low={str(x).lower():x for x in src.columns}; out=pd.DataFrame(index=src.index)
    for old,new in mapping.items():
        col=old if old in src.columns else low.get(old.lower())
        out[new]=src[col] if col is not None else pd.NA
    out["source_id"]=pd.to_numeric(out["source_id"],errors="coerce").astype("Int64")
    out["designation"]="Gaia DR3 "+out["source_id"].astype("string")
    # Gaia DSC-Combmod class probabilities (astrophysical-parameter table).
    try:
        dsc={"PQSO":"classprob_dsc_combmod_quasar","PGal":"classprob_dsc_combmod_galaxy","Pstar":"classprob_dsc_combmod_star",
             "PWD":"classprob_dsc_combmod_whitedwarf","Pbin":"classprob_dsc_combmod_binarystar"}
        pt=Vizier(columns=["Source",*dsc],row_limit=-1).query_region(c,radius=float(radius_arcmin)*u.arcmin,catalog="I/355/paramp")
        ap=pt[0].to_pandas() if pt else pd.DataFrame()
        if not ap.empty and "Source" in ap.columns:
            ap=ap[["Source",*[k for k in dsc if k in ap.columns]]].rename(columns={"Source":"source_id",**dsc})
            ap["source_id"]=pd.to_numeric(ap["source_id"],errors="coerce").astype("Int64")
            out=out.merge(ap.drop_duplicates("source_id"),on="source_id",how="left")
    except Exception:
        pass
    # Independent variability table fallback. A cone query is cheap for named-source validation.
    try:
        vt=Vizier(columns=["**"],row_limit=-1).query_region(c,radius=float(radius_arcmin)*u.arcmin,catalog="I/358/vclassre")
        var=vt[0].to_pandas() if vt else pd.DataFrame()
        if not var.empty:
            sid=_pick(var,["Source","source_id"]);cl=_pick(var,["Class","best_class_name"]);sc=_pick(var,["ClassSc","best_class_score"])
            if sid:
                tmp=pd.DataFrame({"source_id":pd.to_numeric(var[sid],errors="coerce").astype("Int64"),"best_class_name":var[cl] if cl else pd.NA,"best_class_score":pd.to_numeric(var[sc],errors="coerce") if sc else pd.NA}).drop_duplicates("source_id")
                out=out.merge(tmp,on="source_id",how="left")
    except Exception:
        pass
    for col in AP+VAR_SUMMARY+["best_class_name","best_class_score"]:
        if col not in out.columns:out[col]=pd.NA
    out["gaia_base_query_status"]="vizier_fallback";out["gaia_ap_query_status"]="fallback_partial";out["gaia_vari_classifier_query_status"]="vizier_fallback";out["gaia_vari_summary_query_status"]="fallback_unavailable"
    return out

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    select=",".join(SOURCE)
    q=f"""SELECT {select} FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(ra)},{float(dec)},{float(radius_arcmin)/60.0}))"""
    try:
        df=_bounded(_tap,BASE_TAP_BUDGET_S,q);df["gaia_base_query_status"]="tap"
        if not df.empty:
            df=_merge_optional(df,"gaiadr3.astrophysical_parameters",AP,"gaia_ap_query_status")
            df=_merge_optional(df,"gaiadr3.vari_classifier_result",["best_class_name","best_class_score"],"gaia_vari_classifier_query_status")
            df=_merge_optional(df,"gaiadr3.vari_summary",VAR_SUMMARY,"gaia_vari_summary_query_status")
    except Exception:
        df=_vizier_fallback(ra,dec,radius_arcmin)
    if df.empty:return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"]+SOURCE[2:]+AP+["best_class_name","best_class_score"]+VAR_SUMMARY)
    df.insert(0,"catalog",CATALOG)
    sid=pd.to_numeric(df["source_id"],errors="coerce").astype("Int64").astype("string")
    df.insert(1,"catalog_object_id",sid);df.insert(2,"object_name",df.get("designation",pd.Series("Gaia DR3 "+sid,index=df.index)).astype("string"))
    df["query_radius_arcmin"]=float(radius_arcmin);df["ref_epoch"]=2016.0;df["entity_kind"]="persistent_source";df["psf_fwhm_arcsec"]=0.18
    # Native RA/Dec errors are mas; Stage-1 performs the conversion.
    return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):raise ValueError("invalid Gaia output")
    Path(path).parent.mkdir(parents=True,exist_ok=True);df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

"""Gaia DR3 collector with resilient layered retrieval.

The cone's gaia_source rows are acquired first. Astrophysical parameters and
variability products are then joined by source_id in independent TAP queries.
A transient failure in a supplementary Gaia table therefore does not erase the
base astrometry/photometry for the source.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

CATALOG="Gaia DR3"
SOURCE=[
    "source_id","designation","ra","dec","ra_error","dec_error","parallax","parallax_error",
    "pmra","pmra_error","pmdec","pmdec_error","ruwe",
    "phot_g_mean_flux","phot_g_mean_flux_error","phot_g_mean_mag",
    "phot_bp_mean_flux","phot_bp_mean_flux_error","phot_bp_mean_mag",
    "phot_rp_mean_flux","phot_rp_mean_flux_error","phot_rp_mean_mag",
    "bp_rp","bp_g","g_rp","phot_bp_rp_excess_factor",
    "radial_velocity","radial_velocity_error","rv_nb_transits",
]
AP=[
    "teff_gspphot","logg_gspphot","mh_gspphot","distance_gspphot","ag_gspphot","ebpminrp_gspphot",
    "mass_flame","age_flame","evolstage_flame","flags_flame",
    "classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star",
    "classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar",
]
VAR_SUMMARY=[
    "in_vari_classification_result","in_vari_rrlyrae","in_vari_cepheid",
    "in_vari_long_period_variable","in_vari_eclipsing_binary","in_vari_rotation_modulation",
    "in_vari_agn","in_vari_microlensing","in_vari_compact_companion",
]

def _tap(query:str,retries:int=4)->pd.DataFrame:
    from astroquery.gaia import Gaia
    last=None
    for attempt in range(retries):
        try:
            # Async is usually more stable for archive TAP queries.
            return Gaia.launch_job_async(query).get_results().to_pandas()
        except Exception as exc:
            last=exc
            if attempt+1<retries:
                time.sleep(min(8,2**attempt))
    # A synchronous attempt exercises a distinct archive path and has recovered
    # transient async failures in practice.
    try:
        return Gaia.launch_job(query).get_results().to_pandas()
    except Exception as exc:
        raise RuntimeError(f"Gaia TAP failed after retries; async={last!r}; sync={exc!r}") from exc

def _merge_optional(base:pd.DataFrame,table:str,columns:list[str],status_name:str)->pd.DataFrame:
    if base.empty:
        base[status_name]=pd.Series(dtype="string")
        return base
    ids=[str(int(x)) for x in pd.to_numeric(base["source_id"],errors="coerce").dropna().unique()]
    if not ids:
        base[status_name]="missing_source_id"
        return base
    pieces=[]
    try:
        for start in range(0,len(ids),500):
            chunk=ids[start:start+500]
            select="source_id,"+",".join(columns)
            q=f"SELECT {select} FROM {table} WHERE source_id IN ({','.join(chunk)})"
            pieces.append(_tap(q))
        opt=pd.concat(pieces,ignore_index=True,sort=False) if pieces else pd.DataFrame()
        if not opt.empty:
            opt["source_id"]=pd.to_numeric(opt["source_id"],errors="coerce").astype("Int64")
            base["source_id"]=pd.to_numeric(base["source_id"],errors="coerce").astype("Int64")
            base=base.merge(opt.drop_duplicates("source_id"),on="source_id",how="left")
        for col in columns:
            if col not in base.columns:
                base[col]=pd.NA
        base[status_name]="ok"
    except Exception as exc:
        for col in columns:
            if col not in base.columns:
                base[col]=pd.NA
        base[status_name]="error:"+type(exc).__name__
    return base

def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
    select=",".join(SOURCE)
    q=f"""SELECT {select}
    FROM gaiadr3.gaia_source
    WHERE 1=CONTAINS(
      POINT('ICRS',ra,dec),
      CIRCLE('ICRS',{float(ra)},{float(dec)},{float(radius_arcmin)/60.0})
    )"""
    df=_tap(q)
    if df.empty:
        return pd.DataFrame(columns=["catalog","catalog_object_id","object_name","ra","dec"]+SOURCE[2:]+AP+["best_class_name","best_class_score"]+VAR_SUMMARY)

    df=_merge_optional(df,"gaiadr3.astrophysical_parameters",AP,"gaia_ap_query_status")
    df=_merge_optional(df,"gaiadr3.vari_classifier_result",["best_class_name","best_class_score"],"gaia_vari_classifier_query_status")
    df=_merge_optional(df,"gaiadr3.vari_summary",VAR_SUMMARY,"gaia_vari_summary_query_status")

    df.insert(0,"catalog",CATALOG)
    sid=pd.to_numeric(df["source_id"],errors="coerce").astype("Int64").astype("string")
    df.insert(1,"catalog_object_id",sid)
    df.insert(2,"object_name",df["designation"].astype("string"))
    return df.drop_duplicates("catalog_object_id",keep="last").reset_index(drop=True)

def save(df:pd.DataFrame,path:str|Path)->None:
    required={"catalog","catalog_object_id","object_name","ra","dec"}
    if not required.issubset(df.columns):
        raise ValueError("invalid Gaia output")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    df.drop_duplicates("catalog_object_id",keep="last").to_csv(path,index=False)

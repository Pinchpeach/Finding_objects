"""Gaia DR3 independent collector. Get_data only; no cross-match/classification."""
from pathlib import Path
import pandas as pd
CATALOG="Gaia DR3"; TABLE="gaiadr3.gaia_source"
COLUMNS=["source_id","designation","ra","dec","ra_error","dec_error","parallax","parallax_error","pmra","pmra_error","pmdec","pmdec_error","ruwe","phot_g_mean_flux","phot_g_mean_flux_error","phot_g_mean_mag","phot_bp_mean_flux","phot_bp_mean_flux_error","phot_bp_mean_mag","phot_rp_mean_flux","phot_rp_mean_flux_error","phot_rp_mean_mag","bp_rp","bp_g","g_rp","phot_bp_rp_excess_factor","radial_velocity","radial_velocity_error","rv_nb_transits","teff_gspphot","logg_gspphot","mh_gspphot","distance_gspphot","ag_gspphot","ebpminrp_gspphot"]
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.gaia import Gaia
 q=f"SELECT {','.join(COLUMNS)} FROM {TABLE} WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(ra)},{float(dec)},{radius_arcmin/60.0}))"
 df=Gaia.launch_job_async(q).get_results().to_pandas()
 df.insert(0,"catalog",CATALOG); df.insert(1,"catalog_object_id",df["source_id"].astype("Int64").astype(str)); df.insert(2,"object_name",df["designation"].astype(str))
 return df
def save(df:pd.DataFrame,path:str|Path)->None:
 required={"catalog","catalog_object_id","object_name","ra","dec"}
 if not required.issubset(df.columns): raise ValueError("invalid Gaia output")
 if df["catalog_object_id"].duplicated().any(): raise ValueError("duplicate Gaia source_id")
 Path(path).parent.mkdir(parents=True,exist_ok=True); df.to_csv(path,index=False)

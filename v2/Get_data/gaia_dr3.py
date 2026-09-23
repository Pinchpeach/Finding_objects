"""Gaia DR3 collector with source, DSC classification, and variability evidence."""
from pathlib import Path
import pandas as pd
CATALOG="Gaia DR3"
BASE=["source_id","designation","ra","dec","ra_error","dec_error","parallax","parallax_error","pmra","pmra_error","pmdec","pmdec_error","ruwe","phot_g_mean_flux","phot_g_mean_flux_error","phot_g_mean_mag","phot_bp_mean_flux","phot_bp_mean_flux_error","phot_bp_mean_mag","phot_rp_mean_flux","phot_rp_mean_flux_error","phot_rp_mean_mag","bp_rp","bp_g","g_rp","phot_bp_rp_excess_factor","radial_velocity","radial_velocity_error","rv_nb_transits","teff_gspphot","logg_gspphot","mh_gspphot","distance_gspphot","ag_gspphot","ebpminrp_gspphot"]
DSC=["classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star","classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar"]
def fetch(ra:float,dec:float,radius_arcmin:float)->pd.DataFrame:
 from astroquery.gaia import Gaia
 select=[f"g.{c}" for c in BASE]+[f"ap.{c}" for c in DSC]+["vc.best_class_name","vc.best_class_score"]
 q=f"""SELECT {','.join(select)}
 FROM gaiadr3.gaia_source AS g
 LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap ON g.source_id=ap.source_id
 LEFT OUTER JOIN gaiadr3.vari_classifier_result AS vc ON g.source_id=vc.source_id
 WHERE 1=CONTAINS(POINT('ICRS',g.ra,g.dec),CIRCLE('ICRS',{float(ra)},{float(dec)},{radius_arcmin/60.0}))"""
 df=Gaia.launch_job_async(q).get_results().to_pandas()
 df.insert(0,"catalog",CATALOG); df.insert(1,"catalog_object_id",df["source_id"].astype("Int64").astype(str)); df.insert(2,"object_name",df["designation"].astype(str))
 return df
def save(df:pd.DataFrame,path:str|Path)->None:
 required={"catalog","catalog_object_id","object_name","ra","dec"}
 if not required.issubset(df.columns): raise ValueError("invalid Gaia output")
 if df["catalog_object_id"].duplicated().any(): raise ValueError("duplicate Gaia source_id")
 Path(path).parent.mkdir(parents=True,exist_ok=True); df.to_csv(path,index=False)

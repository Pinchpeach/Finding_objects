from __future__ import annotations
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];PRE=ROOT/"Preprocess";CLS=ROOT/"Classifier"
if str(PRE) not in sys.path:sys.path.insert(0,str(PRE))

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
ASSOC=load(PRE/"association_model.py","assoc_model_test")
PHEN=load(CLS/"axes"/"phenomenon.py","phenomenon_test")
CAL=load(CLS/"calibration"/"per_axis.py","calibration_test")
VALIDATOR=load(CLS/"validate_independent_truth_sets.py","independent_truth_validator_test")

class ScienceCrossmatchTests(unittest.TestCase):
 def test_high_pm_epoch_propagation(self):
  gaia={"catalog":"Gaia DR3","ra":291.3656402942,"dec":42.7834887926,"ref_epoch":2016.0,"pmra":-109.6,"pmdec":-195.85,"pmra_error":0.1,"pmdec_error":0.1,"poserr_arcsec":0.03,"psf_fwhm_arcsec":0.18,"max_radius_arcsec":5.0}
  old_ra,old_dec=ASSOC.propagate_linear(gaia["ra"],gaia["dec"],gaia["pmra"],gaia["pmdec"],2016.0,2000.0)
  tm={"catalog":"2MASS PSC","ra":old_ra+0.05/3600.0,"dec":old_dec,"ref_epoch":2000.0,"poserr_arcsec":0.2,"psf_fwhm_arcsec":2.5,"max_radius_arcsec":6.0}
  r=ASSOC.assess_pair(gaia,tm)
  self.assertTrue(r["accepted"]);self.assertTrue(r["proper_motion_propagated"]);self.assertLess(r["separation_arcsec"],0.1)

 def test_cross_catalog_alias_namespaced(self):
  a=ASSOC.canonical_aliases("AllWISE",{},"J021920.40-025843.0")
  b=ASSOC.canonical_aliases("Suh 2021 AGB Catalog",{"WISEA":"J021920.40-025843.0"},"row1")
  self.assertTrue(a & b)

 def test_iras_agb_uncertainty_not_global_radius(self):
  gaia={"catalog":"Gaia DR3","ra":34.83665,"dec":-2.97870,"ref_epoch":2016.0,"pmra":10.0,"pmdec":-20.0,"pmra_error":1.0,"pmdec_error":1.0,"poserr_arcsec":0.1,"psf_fwhm_arcsec":0.18,"max_radius_arcsec":5.0}
  agb={"catalog":"Suh 2021 AGB Catalog","agb_subclass":"OAGB_IRAS","ra":34.8393,"dec":-2.9787,"ref_epoch":1983.5,"poserr_arcsec":12.0,"psf_fwhm_arcsec":30.0,"max_radius_arcsec":45.0}
  r=ASSOC.assess_pair(gaia,agb)
  self.assertTrue(r["accepted"]);self.assertGreater(r["match_radius_arcsec"],10.0);self.assertTrue(r["proper_motion_propagated"])

 def test_transient_and_pn_routes(self):
  sn=PHEN.classify(pd.Series({"catalogs":"Asiago Supernova Catalog","association_confidence__asiago_supernova_catalog":0.8,"event_mjd":55800,"sn_subtype":"Ia"}))
  self.assertEqual(sn["label"],"SN");self.assertEqual(sn["status"],"ASIAGO_SUPERNOVA_EVENT_MATCH")
  pn=PHEN.classify(pd.Series({"catalogs":"Acker PN Spectroscopy","association_confidence__acker_pn_spectroscopy":0.7,"pn_oiii_5007":400.0,"pn_halpha":100.0,"pn_nii_6584":20.0}))
  self.assertEqual(pn["label"],"PN");self.assertEqual(pn["status"],"PN_SPECTROSCOPY_EVIDENCE")

 def test_calibration_abstains_without_model(self):
  frame=pd.DataFrame({"physical_class":["WD"],"physical_confidence":[0.9]})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"models.json";p.write_text('{"axes":{}}')
   out=CAL.annotate(frame,p,axes=("physical",))
   self.assertTrue(pd.isna(out.loc[0,"physical_calibrated_probability"]));self.assertEqual(out.loc[0,"physical_calibration_status"],"UNCALIBRATED_NO_MODEL")

 def test_hierarchical_mira_metric_never_overwrites_exact_metric(self):
  rows=pd.DataFrame([{
   "truth_id":"mira-1","axis":"variability","truth_class":"MIRA",
   "predicted_class":"LPV","match":False,"family_match":True,
   "classified":True,"raw_score":0.9,
  }])
  with tempfile.TemporaryDirectory() as d:
   summary=VALIDATOR.write_report(rows,Path(d))
   r=summary.iloc[0]
   self.assertEqual(r.exact_accuracy_all,0.0)
   self.assertEqual(r.family_accuracy_all,1.0)
   report=(Path(d)/"INDEPENDENT_TRUTH_VALIDATION.md").read_text()
   self.assertIn("family",report.lower())

if __name__=="__main__":unittest.main()

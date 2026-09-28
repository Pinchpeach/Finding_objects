# Real-sample multi-axis validation

SIMBAD supplies only the validation coordinates and external reference type; no SIMBAD row is passed into the blind pipeline.
Catalog-assisted results are reported separately and are not independent validation.

- requested samples: **9**
- successfully executed samples: **9/9**
- blind exact-axis matches among executed: **6/9 (66.7%)**

| sample | SIMBAD ref | axis | expected | blind | status | sep_arcsec | assisted |
|---|---|---|---|---|---|---:|---|
| GD 71 | WD* | physical | WD | WD | CLASSIFIED_WD | 2.518 | WD |
| RR Lyr | RR* | variability | RR_LYRAE | RR_LYRAE | GAIA_DR3_VARIABLE_CANDIDATE | 3.591 | RR_LYRAE |
| delta Cep | cC* | variability | CEPHEID | CEPHEID | GAIA_DR3_VARIABLE_CANDIDATE | 0.239 | CEPHEID |
| Mira | Mi* | physical | AGB | OTHER_STELLAR | STELLAR_UNREFINED | 3.838 | OTHER_STELLAR |
| PSR B0531+21 | Psr | compact | PULSAR | PULSAR | ATNF_CATALOG_MATCH | 0.197 | PULSAR |
| M 57 | PN | phenomenon | PN | PN | HASH_PN_CATALOG_MATCH | 0.291 | PN |
| SN 2018fhw | SN* | phenomenon | SN | UNKNOWN | NO_BLIND_CATALOG_EVIDENCE |  | UNKNOWN |
| SN 2011fe | SN* | phenomenon | SN | UNKNOWN | NO_BLIND_CATALOG_EVIDENCE |  | UNKNOWN |
| 3C 273 | BLL | extragalactic | AGN | AGN | GAIA_DR3_AGN_CANDIDATE | 0.019 | AGN |

## Scientific measurements

### GD 71

- coordinates: RA=88.11508275 deg, Dec=15.88700802 deg
- reference spectral type: None
- measured fields: {"ra": 88.11537345153243, "dec": 15.886366757616456, "parallax": 19.5638180302216, "parallax_error": 0.055117156, "pmra": 76.72806594267264, "pmdec": -172.95960304595332, "ruwe": 0.9704604, "phot_g_mean_mag": 12.999769, "phot_bp_mean_mag": 12.853095, "phot_rp_mean_mag": 13.305408, "bp_rp": -0.45231247}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}]
- candidate objects: [{"object_id": "OBJ000002", "sep_arcsec": 0.5283495401351165, "catalogs": "2MASS PSC", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000001", "sep_arcsec": 2.5184558157160004, "catalogs": "AllWISE|Gaia DR3", "association_members": 2.0, "primary_class": "UNKNOWN", "physical_class": "WD", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### RR Lyr

- coordinates: RA=291.36630400 deg, Dec=42.78435924 deg
- reference spectral type: None
- measured fields: {"ra": 291.36564029422567, "dec": 42.78348879261871, "parallax": 3.984858178256173, "parallax_error": 0.026521722, "pmra": -109.5987273087364, "pmdec": -195.85073064533083, "ruwe": 1.0359073, "phot_g_mean_mag": 7.6188045, "phot_bp_mean_mag": 7.831135, "phot_rp_mean_mag": 7.257368, "bp_rp": 0.5737667, "teff_gspphot": 6163.496, "logg_gspphot": 3.2207, "mh_gspphot": -0.6117, "mass_flame": 2.3781524, "age_flame": 0.696964, "evolstage_flame": 407.0, "best_class_name": "RR", "best_class_score": 0.5515927, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 4, "error": ""}]
- candidate objects: [{"object_id": "OBJ000004", "sep_arcsec": 3.590894097291803, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "RR_LYRAE", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000001", "sep_arcsec": 8.54723328206258, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000002", "sep_arcsec": 9.464542033795865, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000003", "sep_arcsec": 11.586037302108563, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### delta Cep

- coordinates: RA=337.29276110 deg, Dec=58.41519378 deg
- reference spectral type: None
- measured fields: {"ra": 337.2928846512036, "dec": 58.41520817273959, "parallax": 3.555064233456948, "parallax_error": 0.14753917, "pmra": 14.55964275332636, "pmdec": 3.2375195232330003, "ruwe": 2.7130983, "phot_g_mean_mag": 3.8505998, "phot_bp_mean_mag": 4.2316995, "phot_rp_mean_mag": 3.2610846, "bp_rp": 0.9706149, "teff_gspphot": 6355.6323, "logg_gspphot": 1.7987, "mh_gspphot": -0.129, "mass_flame": 5.560175, "evolstage_flame": 763.0, "best_class_name": "CEP", "best_class_score": 0.16061565, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 2, "error": ""}]
- candidate objects: [{"object_id": "OBJ000001", "sep_arcsec": 0.23865132652179857, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "CEPHEID", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000002", "sep_arcsec": 14.450252163412847, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### Mira

- coordinates: RA=34.83663376 deg, Dec=-2.97763767 deg
- reference spectral type: None
- measured fields: {"ra": 34.83664886460604, "dec": -2.9787036389443307, "phot_g_mean_mag": 3.5681472, "phot_bp_mean_mag": 7.9742136, "phot_rp_mean_mag": 2.3836334, "bp_rp": 5.59058, "best_class_name": "LPV", "best_class_score": 0.6456832, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 2, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}, {"collector": "agb_suh2021", "status": "ok", "rows": 1, "error": ""}]
- candidate objects: [{"object_id": "OBJ000005", "sep_arcsec": 0.3670064990614962, "catalogs": "2MASS PSC", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000003", "sep_arcsec": 1.885014188440437, "catalogs": "AllWISE", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000004", "sep_arcsec": 3.8378614551378942, "catalogs": "Gaia DR3", "association_members": 1.0, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "LPV", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000002", "sep_arcsec": 6.2681857039196185, "catalogs": "AllWISE", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000001", "sep_arcsec": 13.40177073881771, "catalogs": "Suh 2021 AGB Catalog", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "AGB", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### PSR B0531+21

- coordinates: RA=83.63311446 deg, Dec=22.01448714 deg
- reference spectral type: None
- measured fields: {"ra": 83.63305654, "dec": 22.01449797, "parallax": 0.53, "parallax_error": 0.06, "period": 0.0333924123, "period_error": 1.2e-09, "ref_period": "ljg+15", "period_dot": 4.20972e-13, "period_dot_error": 3e-18, "ref_period_dot": "ljg+15", "period_epoch": 48442.5, "corr_period_dot": 4.21e-13}
- collectors: [{"collector": "atnf_pulsar", "status": "ok", "rows": 1, "error": ""}]
- candidate objects: [{"object_id": "OBJ000001", "sep_arcsec": 0.1971900943914123, "catalogs": "ATNF Pulsar Catalog", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### M 57

- coordinates: RA=283.39623652 deg, Dec=33.02913425 deg
- reference spectral type: None
- measured fields: {"ra": 283.39615, "dec": 33.02917}
- collectors: [{"collector": "hash_pn", "status": "ok", "rows": 1, "error": ""}]
- candidate objects: [{"object_id": "OBJ000001", "sep_arcsec": 0.29114645898176594, "catalogs": "HASH PN Catalog", "association_members": 1.0, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "PN"}]

### SN 2018fhw

- coordinates: RA=64.52610833 deg, Dec=-63.61506944 deg
- reference spectral type: None
- measured fields: {}
- collectors: [{"collector": "asas_sn_supernova", "status": "empty", "rows": 0, "error": ""}]
- candidate objects: []

### SN 2011fe

- coordinates: RA=210.77379583 deg, Dec=54.27367222 deg
- reference spectral type: None
- measured fields: {}
- collectors: []
- candidate objects: []

### 3C 273

- coordinates: RA=187.27791594 deg, Dec=2.05238823 deg
- reference spectral type: None
- measured fields: {"ra": 187.27791126935688, "dec": 2.0523908340929307, "parallax": -0.0159502908342347, "parallax_error": 0.020795885, "pmra": -0.0228856724950605, "pmdec": 0.0984679790892176, "ruwe": 1.1057829, "phot_g_mean_mag": 12.8440895, "phot_bp_mean_mag": 12.989387, "phot_rp_mean_mag": 12.495527, "bp_rp": 0.4938593, "teff_gspphot": 9879.593, "logg_gspphot": 2.7659, "mh_gspphot": -2.3554, "best_class_name": "AGN", "best_class_score": 0.18568185, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "sdss_dr18", "status": "ok", "rows": 6, "error": ""}, {"collector": "sdss_spectroscopy", "status": "empty", "rows": 0, "error": ""}]
- candidate objects: [{"object_id": "OBJ000001", "sep_arcsec": 0.0192423064569663, "catalogs": "AllWISE|Gaia DR3", "association_members": 2.0, "primary_class": "QSO", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

## Interpretation

- Blind success means the expected axis class was recovered without SIMBAD otype.
- UNKNOWN is treated as abstention, not as a false scientific claim.
- PN/SN catalog-assisted matches demonstrate routing only; they are not independent physical validation.
- A catalog query failure is retained explicitly instead of being interpreted as an astrophysical non-detection.

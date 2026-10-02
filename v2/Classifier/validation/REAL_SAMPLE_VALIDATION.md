# Real-sample multi-axis validation

SIMBAD supplies only validation coordinates/reference type; no SIMBAD row enters the blind pipeline.
Transient event rows are associated in a separate entity layer from persistent hosts.

- requested samples: **9**
- successfully executed: **9/9**
- blind exact-axis matches: **9/9 (100.0%)**

| sample | axis | expected | blind | status | sep_arcsec |
|---|---|---|---|---|---:|
| GD 71 | physical | WD | WD | CLASSIFIED_WD | 3.027 |
| RR Lyr | variability | RR_LYRAE | RR_LYRAE | GAIA_DR3_VARIABLE_CANDIDATE | 3.591 |
| delta Cep | variability | CEPHEID | CEPHEID | GAIA_DR3_VARIABLE_CANDIDATE | 0.239 |
| Mira | physical | AGB | AGB | SUH2021_AGB_CATALOG_MATCH | 1.885 |
| PSR B0531+21 | compact | PULSAR | PULSAR | ATNF_CATALOG_MATCH | 0.197 |
| M 57 | phenomenon | PN | PN | HASH_PN_CATALOG_MATCH | 0.291 |
| SN 2018fhw | phenomenon | SN | SN | ASASSN_SUPERNOVA_EVENT_MATCH | 2.531 |
| SN 2011fe | phenomenon | SN | SN | ASIAGO_SUPERNOVA_EVENT_MATCH | 0.886 |
| 3C 273 | extragalactic | AGN | AGN | GAIA_DR3_AGN_CANDIDATE | 0.002 |

## Scientific measurements and association diagnostics

### GD 71

- measured fields: {"ra": 88.11543730306488, "dec": 15.886239315232912, "ref_epoch": 2016.0, "anchor_catalog": "Gaia DR3", "entity_kind": "persistent_source", "parallax": 19.5638180302216, "parallax_error": 0.055117156, "pmra": 76.72806594267264, "pmdec": -172.95960304595332, "ruwe": 0.9704604, "phot_g_mean_mag": 12.999769, "phot_bp_mean_mag": 12.853095, "phot_rp_mean_mag": 13.305408, "bp_rp": -0.45231247}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 3.0274349925388497, "catalogs": "2MASS PSC|AllWISE|Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 3.0, "association_confidence_mean": 0.8162229920689614, "proper_motion_propagated_any": true, "primary_class": "STAR", "physical_class": "WD", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### RR Lyr

- measured fields: {"ra": 291.36564029422567, "dec": 42.78348879261871, "ref_epoch": 2016.0, "anchor_catalog": "Gaia DR3", "entity_kind": "persistent_source", "parallax": 3.984858178256173, "parallax_error": 0.026521722, "pmra": -109.5987273087364, "pmdec": -195.85073064533083, "ruwe": 1.0359073, "phot_g_mean_mag": 7.6188045, "phot_bp_mean_mag": 7.831135, "phot_rp_mean_mag": 7.257368, "bp_rp": 0.5737667, "teff_gspphot": 6163.496, "logg_gspphot": 3.2207, "mh_gspphot": -0.6117, "mass_flame": 2.3781524, "age_flame": 0.696964, "evolstage_flame": 407.0, "best_class_name": "RR", "best_class_score": 0.5515927, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 4, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 3.590894097291803, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "RR_LYRAE", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000004", "sep_arcsec": 8.54723328206258, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000002", "sep_arcsec": 9.464542033795865, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000003", "sep_arcsec": 11.586037302108563, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### delta Cep

- measured fields: {"ra": 337.2928846512036, "dec": 58.41520817273959, "ref_epoch": 2016.0, "anchor_catalog": "Gaia DR3", "entity_kind": "persistent_source", "parallax": 3.555064233456948, "parallax_error": 0.14753917, "pmra": 14.55964275332636, "pmdec": 3.2375195232330003, "ruwe": 2.7130983, "phot_g_mean_mag": 3.8505998, "phot_bp_mean_mag": 4.2316995, "phot_rp_mean_mag": 3.2610846, "bp_rp": 0.9706149, "teff_gspphot": 6355.6323, "logg_gspphot": 1.7987, "mh_gspphot": -0.129, "mass_flame": 5.560175, "evolstage_flame": 763.0, "best_class_name": "CEP", "best_class_score": 0.16061565, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 2, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 0.23865132652179857, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "CEPHEID", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000002", "sep_arcsec": 14.450252163412847, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### Mira

- measured fields: {"ra": 34.836525, "dec": -2.9781499, "ref_epoch": 2010.5, "anchor_catalog": "AllWISE", "entity_kind": "persistent_source", "agb_subclass": "OAGB_IRAS", "position_basis": "IRAS"}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 2, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}, {"collector": "agb_suh2021", "status": "ok", "rows": 1, "error": ""}]
- candidates: [{"object_id": "OBJ000002", "sep_arcsec": 0.3670064990614962, "catalogs": "2MASS PSC", "entity_kind": "persistent_source", "anchor_catalog": "2MASS PSC", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000004", "sep_arcsec": 1.885014188440437, "catalogs": "AllWISE|Suh 2021 AGB Catalog", "entity_kind": "persistent_source", "anchor_catalog": "AllWISE", "association_members": 2.0, "association_confidence_mean": 0.5766755124123528, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "AGB", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000001", "sep_arcsec": 3.8378614551378942, "catalogs": "Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "STAR", "physical_class": "OTHER_STELLAR", "variability_class": "LPV", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}, {"object_id": "OBJ000003", "sep_arcsec": 6.2681857039196185, "catalogs": "AllWISE", "entity_kind": "persistent_source", "anchor_catalog": "AllWISE", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

### PSR B0531+21

- measured fields: {"ra": 83.63305654, "dec": 22.01449797, "anchor_catalog": "ATNF Pulsar Catalog", "entity_kind": "persistent_source", "parallax": 0.53, "parallax_error": 0.06, "period": 0.0333924123, "period_error": 1.2e-09, "ref_period": "ljg+15", "period_dot": 4.20972e-13, "period_dot_error": 3e-18, "ref_period_dot": "ljg+15", "period_epoch": 48442.5, "corr_period_dot": 4.21e-13}
- collectors: [{"collector": "atnf_pulsar", "status": "ok", "rows": 1, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 0.1971900943914123, "catalogs": "ATNF Pulsar Catalog", "entity_kind": "persistent_source", "anchor_catalog": "ATNF Pulsar Catalog", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "PULSAR", "phenomenon_class": "UNKNOWN"}]

### M 57

- measured fields: {"ra": 283.39615, "dec": 33.02917, "ref_epoch": 2000.0, "anchor_catalog": "HASH PN Catalog", "entity_kind": "persistent_source"}
- collectors: [{"collector": "hash_pn", "status": "ok", "rows": 1, "error": ""}, {"collector": "pn_spectroscopy", "status": "error", "rows": 0, "error": "KeyError(\"coordinate columns missing; got ['_r', 'recno', 'PNG', 'RAB1950', 'DEB1950', 'fp', 'r_Pos', 'Name', 'PK', 'IRAS', 'Disc', 'Idents', '_RA.icrs', '_DE.icrs']\")"}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 0.29114645898176594, "catalogs": "HASH PN Catalog", "entity_kind": "persistent_source", "anchor_catalog": "HASH PN Catalog", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "PN"}]

### SN 2018fhw

- measured fields: {"ra": 64.52562499999999, "dec": -63.61573888888889, "ref_epoch": 2000.0, "anchor_catalog": "ASAS-SN Supernova Catalog", "entity_kind": "transient_event", "event_time_raw": "2018-08-21.31", "sn_subtype": "Ia"}
- collectors: [{"collector": "asas_sn_supernova", "status": "ok", "rows": 1, "error": ""}, {"collector": "asiago_supernova", "status": "empty", "rows": 0, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 2.53101238937489, "catalogs": "ASAS-SN Supernova Catalog", "entity_kind": "transient_event", "anchor_catalog": "ASAS-SN Supernova Catalog", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "SN"}]

### SN 2011fe

- measured fields: {"ra": 210.7742083333333, "dec": 54.27372222222222, "ref_epoch": 2000.0, "anchor_catalog": "Asiago Supernova Catalog", "entity_kind": "transient_event", "sn_subtype": "Ia"}
- collectors: [{"collector": "asiago_supernova", "status": "ok", "rows": 1, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 0.8855983936604986, "catalogs": "Asiago Supernova Catalog", "entity_kind": "transient_event", "anchor_catalog": "Asiago Supernova Catalog", "association_members": 1.0, "association_confidence_mean": 1.0, "proper_motion_propagated_any": false, "primary_class": "UNKNOWN", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "SN"}]

### 3C 273

- measured fields: {"ra": 187.2779158387138, "dec": 2.052388668185861, "ref_epoch": 2016.0, "anchor_catalog": "Gaia DR3", "entity_kind": "persistent_source", "parallax": -0.0159502908342347, "parallax_error": 0.020795885, "pmra": -0.0228856724950605, "pmdec": 0.0984679790892176, "ruwe": 1.1057829, "phot_g_mean_mag": 12.8440895, "phot_bp_mean_mag": 12.989387, "phot_rp_mean_mag": 12.495527, "bp_rp": 0.4938593, "teff_gspphot": 9879.593, "logg_gspphot": 2.7659, "mh_gspphot": -2.3554, "best_class_name": "AGN", "best_class_score": 0.18568185, "in_vari_long_period_variable": false}
- collectors: [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "sdss_dr18", "status": "ok", "rows": 6, "error": ""}, {"collector": "sdss_spectroscopy", "status": "empty", "rows": 0, "error": ""}]
- candidates: [{"object_id": "OBJ000001", "sep_arcsec": 0.0016174790698616447, "catalogs": "AllWISE|Gaia DR3", "entity_kind": "persistent_source", "anchor_catalog": "Gaia DR3", "association_members": 2.0, "association_confidence_mean": 0.9996739506419948, "proper_motion_propagated_any": true, "primary_class": "QSO", "physical_class": "UNKNOWN", "variability_class": "UNKNOWN", "compact_class": "UNKNOWN", "phenomenon_class": "UNKNOWN"}]

## Interpretation

- UNKNOWN remains abstention, not negative evidence.
- Association scores and Gaia catalog scores are raw evidence; calibrated probabilities are emitted only when an independent calibration model passes support gates.
- Event catalog identity is kept separate from host-galaxy detections and event time is preserved when available.

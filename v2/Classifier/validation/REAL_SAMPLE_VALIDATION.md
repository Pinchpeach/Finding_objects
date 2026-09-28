# Real-sample multi-axis validation

SIMBAD supplies coordinates and an external reference type. Its otype is masked in the blind pipeline.
Catalog-assisted results are reported separately and are not independent validation.

- requested samples: **8**
- successfully executed samples: **8/8**
- blind exact-axis matches among executed: **1/8 (12.5%)**

| sample | SIMBAD ref | axis | expected | blind | status | sep_arcsec | assisted |
|---|---|---|---|---|---|---:|---|
| GD 71 | WD* | physical | WD | UNKNOWN | NOT_STELLAR_ROUTE | 0.264 | physical_class    UNKNOWN
physical_class    UNKNOWN
Name: 0, dtype: object |
| RR Lyr | RR* | variability | RR_LYRAE | UNKNOWN | NO_VARIABILITY_EVIDENCE | 0.000 | variability_class     UNKNOWN
variability_class    RR_LYRAE
Name: 0, dtype: object |
| delta Cep | cC* | variability | CEPHEID | UNKNOWN | NO_VARIABILITY_EVIDENCE | 0.000 | variability_class    UNKNOWN
variability_class    UNKNOWN
Name: 0, dtype: object |
| Mira | Mi* | physical | AGB | UNKNOWN | NOT_STELLAR_ROUTE | 0.184 | physical_class    UNKNOWN
physical_class    UNKNOWN
Name: 0, dtype: object |
| PSR B0531+21 | Psr | compact | PULSAR | PULSAR | ATNF_CATALOG_MATCH | 0.099 | compact_class    PULSAR
compact_class    PULSAR
Name: 0, dtype: object |
| M 57 | PN | phenomenon | PN | UNKNOWN | NO_VALIDATED_PHENOMENON_EVIDENCE | 0.000 | phenomenon_class    UNKNOWN
phenomenon_class         PN
Name: 0, dtype: object |
| SN 2011fe | SN* | phenomenon | SN | UNKNOWN | NO_VALIDATED_PHENOMENON_EVIDENCE | 0.000 | phenomenon_class    UNKNOWN
phenomenon_class         SN
Name: 0, dtype: object |
| 3C 273 | BLL | extragalactic | QSO | UNKNOWN | NO_EXTRAGALACTIC_EVIDENCE | 0.019 | extragalactic_class    UNKNOWN
extragalactic_class    UNKNOWN
Name: 0, dtype: object |

## Scientific measurements

### GD 71

- coordinates: RA=88.11508275 deg, Dec=15.88700802 deg
- reference spectral type: None
- measured fields: {"ra": 88.115070873295, "dec": 15.887080512145, "pmra": 76.728, "pmdec": -172.96}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 1, "error": ""}, {"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "SystemError('Error 200:\\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\\n')"}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}]

### RR Lyr

- coordinates: RA=291.36630400 deg, Dec=42.78435924 deg
- reference spectral type: None
- measured fields: {"ra": 291.36630400221, "dec": 42.78435923839001, "pmra": -109.599, "pmdec": -195.851}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 1, "error": ""}, {"collector": "gaia_dr3", "status": "ok", "rows": 4, "error": ""}]

### delta Cep

- coordinates: RA=337.29276110 deg, Dec=58.41519378 deg
- reference spectral type: None
- measured fields: {"ra": 337.29276110013086, "dec": 58.41519378156944, "pmra": 14.56, "pmdec": 3.238}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 1, "error": ""}, {"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "HTTPError('Error 500:\\nnull')"}]

### Mira

- coordinates: RA=34.83663376 deg, Dec=-2.97763767 deg
- reference spectral type: None
- measured fields: {"ra": 34.836679878799984, "dec": -2.977615836536458, "pmra": 9.33, "pmdec": -237.36}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 2, "error": ""}, {"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "HTTPError('Error 500:\\nnull')"}, {"collector": "allwise", "status": "ok", "rows": 2, "error": ""}, {"collector": "twomass", "status": "ok", "rows": 1, "error": ""}, {"collector": "agb_suh2021", "status": "ok", "rows": 1, "error": ""}]

### PSR B0531+21

- coordinates: RA=83.63311446 deg, Dec=22.01448714 deg
- reference spectral type: None
- measured fields: {"ra": 83.633085498045, "dec": 22.01449255417, "parallax": 0.53, "parallax_error": 0.06, "pmra": -11.513, "pmdec": 2.302, "period": 0.0333924123, "period_error": 1.2e-09, "ref_period": "ljg+15", "period_dot": 4.20972e-13, "period_dot_error": 3e-18, "ref_period_dot": "ljg+15", "period_epoch": 48442.5, "corr_period_dot": 4.21e-13}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 6, "error": ""}, {"collector": "atnf_pulsar", "status": "ok", "rows": 1, "error": ""}]

### M 57

- coordinates: RA=283.39623652 deg, Dec=33.02913425 deg
- reference spectral type: None
- measured fields: {"ra": 283.39623652463, "dec": 33.02913424654, "pmra": 1.645, "pmdec": 2.472}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 1, "error": ""}]

### SN 2011fe

- coordinates: RA=210.77379583 deg, Dec=54.27367222 deg
- reference spectral type: None
- measured fields: {"ra": 210.7737958333333, "dec": 54.27367222222222}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 2, "error": ""}]

### 3C 273

- coordinates: RA=187.27791594 deg, Dec=2.05238823 deg
- reference spectral type: None
- measured fields: {"ra": 187.27791132024493, "dec": 2.052390615275, "pmra": -0.023, "pmdec": 0.098}
- collectors: [{"collector": "simbad_masked", "status": "ok", "rows": 5, "error": ""}, {"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "HTTPError('Error 500:\\nnull')"}, {"collector": "allwise", "status": "ok", "rows": 1, "error": ""}, {"collector": "sdss_dr18", "status": "ok", "rows": 6, "error": ""}, {"collector": "sdss_spectroscopy", "status": "empty", "rows": 0, "error": ""}]

## Interpretation

- Blind success means the expected axis class was recovered without SIMBAD otype.
- UNKNOWN is treated as abstention, not as a false scientific claim.
- PN/SN catalog-assisted matches demonstrate routing only; they are not independent physical validation.
- A catalog query failure is retained explicitly instead of being interpreted as an astrophysical non-detection.

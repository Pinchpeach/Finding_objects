# Real-sample multi-axis validation

SIMBAD supplies only validation coordinates/reference type; no SIMBAD row enters the blind pipeline.
Transient event rows are associated in a separate entity layer from persistent hosts.

- requested samples: **9**
- successfully executed: **0/9**
- blind exact-axis matches: **0/0 (0.0%)**

| sample | axis | expected | blind | status | sep_arcsec |
|---|---|---|---|---|---:|
| GD 71 | physical | WD | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?GD%2071: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?GD%2071: Request took longer than the allowed 10.0 seconds') |  |
| RR Lyr | variability | RR_LYRAE | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?RR%20Lyr: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?RR%20Lyr: Bad Gateway') |  |
| delta Cep | variability | CEPHEID | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?delta%20Cep: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?delta%20Cep: Request took longer than the allowed 10.0 seconds') |  |
| Mira | physical | AGB | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?Mira: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?Mira: Request took longer than the allowed 10.0 seconds') |  |
| PSR B0531+21 | compact | PULSAR | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?PSR%20B0531%2B21: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?PSR%20B0531%2B21: Request took longer than the allowed 10.0 seconds') |  |
| M 57 | phenomenon | PN | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?M%2057: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?M%2057: Request took longer than the allowed 10.0 seconds') |  |
| SN 2018fhw | phenomenon | SN | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?SN%202018fhw: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?SN%202018fhw: Request took longer than the allowed 10.0 seconds') |  |
| SN 2011fe | phenomenon | SN | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?SN%202011fe: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?SN%202011fe: Request took longer than the allowed 10.0 seconds') |  |
| 3C 273 | extragalactic | AGN | ERROR | NameResolveError('All Sesame queries failed. Unable to retrieve coordinates. See errors per URL below: \n https://cds.unistra.fr/cgi-bin/nph-sesame/SNV?3C%20273: timed out\nhttp://vizier.cfa.harvard.edu/viz-bin/nph-sesame/SNV?3C%20273: Request took longer than the allowed 10.0 seconds') |  |

## Scientific measurements and association diagnostics

### GD 71

- measured fields: {}
- collectors: []
- candidates: []

### RR Lyr

- measured fields: {}
- collectors: []
- candidates: []

### delta Cep

- measured fields: {}
- collectors: []
- candidates: []

### Mira

- measured fields: {}
- collectors: []
- candidates: []

### PSR B0531+21

- measured fields: {}
- collectors: []
- candidates: []

### M 57

- measured fields: {}
- collectors: []
- candidates: []

### SN 2018fhw

- measured fields: {}
- collectors: []
- candidates: []

### SN 2011fe

- measured fields: {}
- collectors: []
- candidates: []

### 3C 273

- measured fields: {}
- collectors: []
- candidates: []

## Interpretation

- UNKNOWN remains abstention, not negative evidence.
- Association scores and Gaia catalog scores are raw evidence; calibrated probabilities are emitted only when an independent calibration model passes support gates.
- Event catalog identity is kept separate from host-galaxy detections and event time is preserved when available.

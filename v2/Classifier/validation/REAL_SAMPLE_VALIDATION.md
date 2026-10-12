# Real-sample multi-axis validation

SIMBAD supplies only validation coordinates/reference type; no SIMBAD row enters the blind pipeline.
Transient event rows are associated in a separate entity layer from persistent hosts.

- requested samples: **9**
- successfully executed: **0/9**
- blind exact-axis matches: **0/0 (0.0%)**

| sample | axis | expected | blind | status | sep_arcsec |
|---|---|---|---|---|---:|
| GD 71 | physical | WD | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| RR Lyr | variability | RR_LYRAE | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| delta Cep | variability | CEPHEID | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| Mira | physical | AGB | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| PSR B0531+21 | compact | PULSAR | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| M 57 | phenomenon | PN | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| SN 2018fhw | phenomenon | SN | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| SN 2011fe | phenomenon | SN | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |
| 3C 273 | extragalactic | AGN | ERROR | ValueError('Length of values (2) does not match length of index (1)') |  |

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

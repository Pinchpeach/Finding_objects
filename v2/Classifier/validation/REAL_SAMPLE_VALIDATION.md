# Real-sample multi-axis validation

SIMBAD supplies only validation coordinates/reference type; no SIMBAD row enters the blind pipeline.
Transient event rows are associated in a separate entity layer from persistent hosts.

- requested samples: **9**
- successfully executed: **0/9**
- blind exact-axis matches: **0/0 (0.0%)**

| sample | axis | expected | blind | status | sep_arcsec |
|---|---|---|---|---|---:|
| GD 71 | physical | WD | ERROR | DALFormatError: ConnectionError: HTTPSConnectionPool(host='simbad.cds.unistra.fr', port=443): Max retries exceeded with url: /simbad/sim-tap/sync (Caused by NewConnectionError("HTTPSConnection(host='simbad.cds.unistra.fr', port=443): Failed to establish a new connection: [Errno 111] Connection refused")) |  |
| RR Lyr | variability | RR_LYRAE | ERROR | DALFormatError: ConnectionError: HTTPSConnectionPool(host='simbad.cds.unistra.fr', port=443): Max retries exceeded with url: /simbad/sim-tap/sync (Caused by NewConnectionError("HTTPSConnection(host='simbad.cds.unistra.fr', port=443): Failed to establish a new connection: [Errno 111] Connection refused")) |  |
| delta Cep | variability | CEPHEID | ERROR | DALFormatError: ConnectionError: HTTPSConnectionPool(host='simbad.cds.unistra.fr', port=443): Max retries exceeded with url: /simbad/sim-tap/sync (Caused by NewConnectionError("HTTPSConnection(host='simbad.cds.unistra.fr', port=443): Failed to establish a new connection: [Errno 111] Connection refused")) |  |
| Mira | physical | AGB | ERROR | DALFormatError: ConnectionError: HTTPSConnectionPool(host='simbad.cds.unistra.fr', port=443): Max retries exceeded with url: /simbad/sim-tap/sync (Caused by NewConnectionError("HTTPSConnection(host='simbad.cds.unistra.fr', port=443): Failed to establish a new connection: [Errno 111] Connection refused")) |  |
| PSR B0531+21 | compact | PULSAR | ERROR | DALServiceError: Unable to access the capabilities endpoint at:
- https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: Connection failed (Possible causes: incorrect URL, DNS issue, or service is down)

This could mean:
1. The service URL is incorrect
2. The service is temporarily unavailable
3. The service doesn't support this protocol
4. If a 503 was encountered, retry after the suggested delay.
 |  |
| M 57 | phenomenon | PN | ERROR | DALServiceError: Unable to access the capabilities endpoint at:
- https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: Connection failed (Possible causes: incorrect URL, DNS issue, or service is down)

This could mean:
1. The service URL is incorrect
2. The service is temporarily unavailable
3. The service doesn't support this protocol
4. If a 503 was encountered, retry after the suggested delay.
 |  |
| SN 2018fhw | phenomenon | SN | ERROR | DALServiceError: Unable to access the capabilities endpoint at:
- https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: Connection failed (Possible causes: incorrect URL, DNS issue, or service is down)

This could mean:
1. The service URL is incorrect
2. The service is temporarily unavailable
3. The service doesn't support this protocol
4. If a 503 was encountered, retry after the suggested delay.
 |  |
| SN 2011fe | phenomenon | SN | ERROR | DALServiceError: Unable to access the capabilities endpoint at:
- https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: Connection failed (Possible causes: incorrect URL, DNS issue, or service is down)

This could mean:
1. The service URL is incorrect
2. The service is temporarily unavailable
3. The service doesn't support this protocol
4. If a 503 was encountered, retry after the suggested delay.
 |  |
| 3C 273 | extragalactic | AGN | ERROR | DALServiceError: Unable to access the capabilities endpoint at:
- https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: Connection failed (Possible causes: incorrect URL, DNS issue, or service is down)

This could mean:
1. The service URL is incorrect
2. The service is temporarily unavailable
3. The service doesn't support this protocol
4. If a 503 was encountered, retry after the suggested delay.
 |  |

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

# Classifier target structure

```
Classifier/
├── 01_prepare_input.py
├── control.py                 # production entry point: legacy detail + all axes
├── control_axes.py            # reusable multi-axis annotator
├── architecture/
│   └── README.md
├── axes/
│   ├── physical.py            # WD / RGB / AGB / ...
│   ├── variability.py         # RR Lyrae / Cepheid / LPV / eclipsing / ...
│   ├── compact.py             # compact-companion evidence; NS/pulsar needs stronger evidence
│   ├── extragalactic.py       # galaxy / AGN / QSO
│   └── phenomenon.py          # SN / microlensing; PN/nova need dedicated evidence
└── existing WD training, validation and Gaia-XP files
```

## Implemented production routes

- WD: existing validated Gaia DSC + HR-locus routing, with gated Gaia-XP DA/DB subtype.
- RGB: Gaia DR3 FLAME `evolstage_flame` from RGB base (490) through RGB tip (1290),
  only when giant-quality guardrails are satisfied (`logg < 3.5`, `mass < 2 Msun`,
  `age > 1 Gyr`). No calibrated probability is fabricated.
- Variables: Gaia DR3 `vari_classifier_result` classes are mapped into project classes
  (RR Lyrae, Cepheid, LPV, eclipsing, rotational, pulsating, eruptive, other).
  `best_class_score` is retained as catalog evidence but is not treated as a calibrated
  probability.
- SN / microlensing: Gaia DR3 variability candidates are routed to the phenomenon axis.
- Compact companion: Gaia DR3 `vari_summary.in_vari_compact_companion` produces only
  `COMPACT_COMPANION_CANDIDATE`; it is never promoted to NS/PULSAR/XRB.
- Extragalactic: Preprocess GALAXY/QSO routing is retained, and Gaia DR3 AGN candidate
  evidence can refine the axis to AGN.

## Explicit abstention boundaries

- AGB: Gaia FLAME's published evolutionary-stage convention ends at the RGB tip and does
  not by itself identify AGB. LPV is not automatically converted to AGB or Mira.
- A generic stellar-family result is not emitted as an `OTHER_STELLAR` physical
  class. Without WD, RGB, AGB, or other validated physical evidence, the
  physical axis returns `UNKNOWN` while preserving the stellar-family evidence.
- NS/Pulsar/XRB: radio/X-ray detection alone is insufficient. The existing radio/X-ray
  benchmark is validated for STAR/GALAXY/QSO, not for compact-object identity.
- PN/Nova: no dedicated spectral-line or transient model is yet available in the current
  integrated feature contract.

Unsupported detailed labels remain `UNKNOWN` / unresolved rather than receiving
placeholder probabilities.

## Production execution

```bash
python v2/Classifier/control.py --input classifier_input.csv --out classified_objects.csv
```

The output preserves the previous detailed STAR/GALAXY/QSO branch columns and appends
per-axis fields:

```
physical_class / physical_status / physical_evidence_json
variability_class / variability_status / variability_evidence_json
compact_class / compact_status / compact_evidence_json
extragalactic_class / extragalactic_status / extragalactic_evidence_json
phenomenon_class / phenomenon_status / phenomenon_evidence_json
```

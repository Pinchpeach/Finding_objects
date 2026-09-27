# Classifier work checkpoint

Purpose: recover implementation state if chat/context is reset. Treat the repository,
tests, workflow results, and this file as the source of truth.

## Current architecture

Production entry point:
- `v2/Classifier/control.py`

Independent axes:
- `axes/physical.py`
- `axes/variability.py`
- `axes/compact.py`
- `axes/extragalactic.py`
- `axes/phenomenon.py`

Existing validated WD code is preserved in `branches/star.py` and Gaia-XP WD subtype files.

## Implemented

- WD routing through physical axis.
- DA/DB subtype output only behind existing validated Gaia-XP confidence gate.
- RGB routing from Gaia DR3 FLAME evolutionary stage with conservative giant guardrails.
- Gaia DR3 variable-class routing: RR Lyrae, Cepheid, LPV, eclipsing, rotational,
  pulsating, eruptive, and other variable.
- Gaia DR3 SN and microlensing candidates routed to phenomenon axis.
- Gaia DR3 compact-companion flag routed only to
  `COMPACT_COMPANION_CANDIDATE`; never promoted directly to NS/PULSAR/XRB.
- GALAXY/QSO coarse routes retained in extragalactic axis; Gaia AGN evidence can refine to AGN.
- Legacy detailed-output columns preserved alongside new multi-axis columns.

## Explicitly not yet implemented

Do not invent production labels for:
- AGB
- NS / pulsar / XRB identity
- PN
- nova

These require dedicated truth sets / literature-backed evidence and external validation.

## Validation state

Known successful workflows:
- physical-axis smoke: run 36313171175
- multi-axis smoke: run 36315859281
- legacy routing regression after compatibility fix: run 36316030533

Latest validation work queued/started at checkpoint creation:
- extended multi-axis route validation after compact/extragalactic additions
- NGC4522 raw -> Preprocess stages -> Classifier end-to-end workflow
- Gaia collector rerun with FLAME and vari_summary fields

## Important implementation commits

- `1f12aa53e0298c06d5675cc3ad5b21e112218179`: physical WD routing smoke
- `4ca0851d50ab3bd065c65d426196b580f597ab88`: Gaia-backed RGB/variable/transient implementation start
- `be68a423fddf13fa214e3cc819708915eb577fc6`: backward-compatible routing regression expectations
- `2204ebd3c2e29cfe3b7022ef2a1c22e002357686`: Gaia vari_summary / compact evidence fields
- `2c87464f9231815e0d706cbdd54aebe10bda2a45`: extended multi-axis route tests
- `9db88ea2ed91481d771e89daecee10eae2bc32ec`: NGC4522 E2E validation workflow

## Next work order

1. Finish/check latest CI and NGC4522 E2E results; fix any failures.
2. Build AGB evidence/truth model without converting LPV directly into AGB.
3. Build NS/pulsar/XRB truth/evidence path independent of the existing STAR/GALAXY/QSO
   radio-X-ray benchmark.
4. Build PN/nova phenomenon evidence, preferably spectroscopy + validated catalogs while
   keeping truth labels separate from production evidence.
5. Re-run regression + multi-axis + end-to-end validation.
6. Update this checkpoint after each meaningful milestone.

## Recovery rule

After any context reset:
1. Read this file.
2. Inspect recent commits on `main`.
3. Inspect current GitHub Actions runs and failures.
4. Resume from the first incomplete item in **Next work order**.

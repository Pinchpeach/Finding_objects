# Finding Missing & previous Objects from sky
## Intro
- Find & sort astronomical objects from the target sky
- Discuss probability 'bout object's class (from harsh ones to smooth)

## What to construct
### Get dataset from Surveys
- get data from various surveys that covers almost every wavelength

### Find & merge data which duplicates
- With dataset loaded by previous, we merge datasets which has same obj_id
- Also, look for it coordinates and other features to merge datasets which has different obj_id(from another survey)

### Classification 'bout objects
- Object classification based on documents (see documents from v2/ )
- After classify bigger category(Stars, Galaxy, QSO), we'll classify them into smaller ones(AGN, AGBs, Variables, etc.)


## Goals
- Fully automated astronomical object detectors
- Find out my objects and its counterparts for my research area

## Run the v2 pipeline
```bash
# collect all surveys around a position, then classify (needs network access to the archives)
python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 0.5 --work runs/ngc4522
# or classify already-collected raw catalogs
python v2/pipeline.py --raw-dir v2/rawdata --work runs/ngc4522
```
Outputs (one CSV per stage, plus `pipeline_summary.csv` with per-stage time) go to `--work`.
Benchmarks and current accuracy: `v2/Preprocess/COARSE_BENCHMARK_RESULTS.md`; change log: `v2/WORK_LOG_2026-10-08.md`.

# Finding Objects

Finds every astronomical object in a patch of sky and classifies it, using catalogues from radio to X-rays.

- **Primary class:** `STAR`, `GALAXY`, `QSO`, or `UNKNOWN`
- **Detailed class:** spectral type, white dwarf, hot subdwarf, ultracool dwarf, red giant / AGB, variable stars (Mira, Cepheid, RR Lyrae, young stellar object, …), pulsar, AGN, blazar, planetary nebula, and more
- **Abstains when unsure:** an object without enough evidence stays `UNKNOWN`, with the reason recorded
- **Literature-based:** every threshold and rule cites its source (`v2/**/LITERATURE*.md`)

## How it works

```
(RA, Dec, radius)
  │
  ├─ Collect     query 27 archives in parallel (Gaia, SDSS, Pan-STARRS, Legacy Surveys, WISE,
  │              2MASS, GALEX, 5 radio, 3 X-ray, 4 spectroscopic, ZTF, ATNF, BZCAT, SIMBAD, NED)
  ├─ Associate   group detections of the same object (position, epoch, errors, proper motion)
  ├─ Integrate   one row per object, harmonised units (AB mag, mJy, z)
  ├─ Evidence    25 rules each give evidence for STAR / GALAXY / QSO
  ├─ Classify    fitted fusion (boosted trees + logistic) → STAR / GALAXY / QSO / UNKNOWN
  └─ Refine      sub-class + five independent axes
                 (physical state, variability, compact object, extragalactic, phenomenon)
  ↓
classified_objects.csv
```

- **Collect:** results are cached locally, so re-running the same or a smaller area needs no network.
- **Associate:** counterparts are chosen by likelihood ratio, not just the nearest neighbour.
- **Evidence:** a catalogue's own label is never taken as final; each measurement becomes weighted evidence that is combined with the rest.
- **Refine:** runs only after the primary class is known (e.g. `STAR` → K5 dwarf, Mira, carbon-rich AGB; `GALAXY` → star-forming, AGN).

The full description is in [`v2/ALGORITHM.md`](v2/ALGORITHM.md).

## Accuracy

| Test | Result |
|---|---|
| Primary class vs SDSS spectra | 98.09 % |
| Primary class vs DESI spectra (faint objects) | 93.04 % |
| Mira / Cepheid / RR Lyrae | 94.8 / 93.2 / 82.4 % |
| Planetary nebulae | 89.2 % |
| Blind test on unseen objects | 9 / 9 |

Spectroscopic classes are used only as ground truth, never as evidence in these tests. Per-version results are in [`v2/CHANGELOG.md`](v2/CHANGELOG.md).

## Usage

### Desktop app

Download the zip for your OS from [Releases](https://github.com/Pinchpeach/Finding_objects/releases), unzip it, and run `FindingObjects` (`FindingObjects.exe` on Windows). No Python installation is needed.

To run from source:

```bash
pip install -r v2/app/requirements.txt
python v2/app/qt_app.py
```

| Feature | How |
|---|---|
| Search area | object name or coordinates, plus a radius |
| Results | sortable, filterable table; object details; sky map |
| Bookmarks | `Ctrl+D` to bookmark the selected object; **Bookmarks** tab (`Ctrl+B`) to add notes, search, reopen an object or start a new search there |
| Log | one log file per user, shown with View > Log (`Ctrl+L`) |

### Command line

```bash
# Collect every survey around a position and classify (needs archive access)
python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 0.5 --work runs/ngc4522

# Classify catalogues collected earlier
python v2/pipeline.py --raw-dir v2/rawdata --work runs/ngc4522
```

Each stage writes a CSV to `--work`; `pipeline_summary.csv` records the time each stage took.

## Development

```bash
cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests   # tests
black v2                                                                     # formatting (pyproject.toml)
```

| Folder | Contents |
|---|---|
| `v2/Get_data/` | archive collectors |
| `v2/Preprocess/` | association, integration, features, evidence, primary class |
| `v2/Classifier/` | sub-classes and the independent axes |
| `v2/app/` | desktop app (Qt) |
| `v2/benchmark/` | truth sets and benchmarks |

## License

- Code: MIT License — see [`LICENSE`](LICENSE).
- Third-party components bundled with the app (Qt / PySide6 under LGPLv3, among others) and data-use terms: see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- When publishing results, follow the citation and acknowledgement requirements of each survey used.

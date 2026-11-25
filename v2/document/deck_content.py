"""Text of the 12-slide "pipeline and tech stack" deck (``PIPELINE_STACK_v<PROGRAM_VERSION>.pptx`` / ``.pdf``).

    python v2/document/build_deck.py        # writes the PPTX, the PDF and the preview PNG

All deck-only wording lives in this file; ``build_deck.py`` only draws.  The deck is the short form of the overview
(``overview_content.py``), so:

* tables that the overview already has are **read from it** (data sources, rule groups, ablation counts, timing),
  not typed again (``overview_table``);
* every percentage and every large count written here must also occur in the overview text
  (``Preprocess/tests/test_deck.py`` checks it), so a figure changed there cannot stay stale here;
* limits are stated next to the results, as in the README: the coarse class is decided by optical colour and
  morphology, WISE mid-infrared and Gaia astrometry / DSC, and the deck must not read as an all-wavelength classifier.

Inline markup: ``**bold**`` and ```code```.  English only (decision of 2026-11-24).
"""

from __future__ import annotations

import overview_content as C

PROGRAM_VERSION = C.PROGRAM_VERSION
DATE = "2026-11-25"
FOOTER = f"Finding Objects · program version {PROGRAM_VERSION}"
N_SLIDES = 12


def overview_table(section_prefix: str, head0: str) -> dict:
    """The table of the overview whose section title starts with ``section_prefix`` and whose first header is ``head0``."""
    for s in C.SECTIONS:
        if s["title"].startswith(section_prefix):
            for b in s["blocks"]:
                if b["kind"] == "table" and b["head"][0] == head0:
                    return b
    raise KeyError((section_prefix, head0))


# ------------------------------------------------------------------------------------------------------ 1 title
TITLE = {
    "kicker": f"Pipeline and tech stack · program version {PROGRAM_VERSION} · {DATE}",
    "title": "Finding Objects",
    "subtitle": "A field-level multi-catalogue integration and annotation tool for sources on the sky",
    "card": (
        "Give it a position and a radius. It asks **30 public archives**, cross-matches the detections into "
        "**one row per object**, and reports a class, the evidence and **where each decision came from**."
    ),
    "bands_title": "Data collected, radio to X-ray",
    # (label, detail, decides the coarse class?)
    "bands": [
        ("Radio", "LoTSS · FIRST · NVSS · TGSS · VLASS", False),
        ("Mid-infrared", "AllWISE", True),
        ("Optical", "Pan-STARRS1 · Legacy Surveys · SDSS", True),
        ("Astrometry", "Gaia DR3 parallax, proper motion, DSC", True),
        ("UV", "GALEX", False),
        ("X-ray", "4XMM · Chandra · eROSITA", False),
    ],
    "legend_yes": "decides the coarse class",
    "legend_no": "collected for tags and sub-types",
    "bands_note": "The column shows what is collected, not what decides the class: it is not an all-wavelength classifier.",
}

# -------------------------------------------------------------------------------------------------- 2 at a glance
GLANCE = {
    "section": "Overview",
    "title": "At a glance",
    "lede": "Position + radius → cross-matched objects with class, evidence and provenance.",
    "tiles": [
        ("30", "public archives", "asked for every catalogued source in the field"),
        ("35", "evidence rules", "each with a literature basis, in one rule table"),
        ("4", "coarse answers", "STAR · GALAXY · QSO · UNKNOWN (it abstains and says why)"),
        ("29", "columns to read first", "`objects_summary.csv`, one row per detected object"),
    ],
    "is_title": "What it is",
    "is_items": [
        "**Input:** an object name or RA, Dec plus a radius; or a folder of catalogue files collected before.",
        "**Output:** one row per object with coarse class, sub-class where one can be given, the evidence list "
        "and the provenance of every decision.",
        "**Use:** desktop app for Windows, macOS and Linux (no Python needed) or the command line `v2/pipeline.py`.",
        "**Contribution:** the integration, the provenance, the validation design and the measured limits.",
    ],
    "not_title": "What is not claimed",
    "not_items": [
        "**No novelty over Gaia DSC on the bright sky:** 99.8 % against 99.5 % for DSC alone on the same locked-set objects.",
        "**Not an all-wavelength classifier:** X-ray and radio contribute nothing measurable to the coarse class.",
        "**No calibrated QSO probabilities at the faint end;** at r ≥ 24 quasars are not recovered (0 of 33 type-1 AGN).",
        "**Not a bulk tool, not a replacement for a spectrum:** sub-classes are mostly catalogue look-ups; own "
        "sub-type recovery is 45.8 % on the 520-object check.",
        "**Not validated** for dense low-latitude fields at r > 20 (no truth there).",
    ],
}

# ------------------------------------------------------------------------------------------------------ 3 pipeline
PIPELINE = {
    "section": "Pipeline",
    "title": "Processing flow",
    "lede": "`v2/pipeline.py` runs every stage in order; each stage writes its own CSV so intermediate products can be inspected.",
    # (number, name, module, text, highlighted)
    "stages": [
        (
            "0",
            "Collect",
            "Get_data/controller.py",
            "30 collectors, 6 workers, a time budget per archive; cache, mirrors, fallbacks, footprint checks",
            False,
        ),
        (
            "1",
            "Associate",
            "01_source_association",
            "Positional likelihood ratio with each catalogue's error model; proper motion; chance coincidence",
            False,
        ),
        (
            "2",
            "Integrate",
            "02_integrate_objects",
            "One row per object, all original columns kept; AB magnitudes, mJy, redshift",
            False,
        ),
        ("3", "Features", "03_extract_features", "Colours, morphology, signal-to-noise, quality flags", False),
        (
            "4",
            "Evidence",
            "04_build_evidence",
            "35 literature-based rules turn measurements into STAR / GALAXY / QSO evidence",
            False,
        ),
        (
            "5",
            "Coarse class",
            "05_likelihood_vectors",
            "Trained fusion, deterministic motion rule, one prior layer, abstention",
            True,
        ),
        (
            "6–7",
            "Sub-classes",
            "Classifier/control.py",
            "Sub-classifiers and five independent axes, each with the measured precision of its rule",
            False,
        ),
        (
            "+",
            "Post-processing",
            "host_groups · high_confidence …",
            "Galaxy fragments, duplicates, halos, unconfirmed detections, “QSO?” flag, archive warnings",
            False,
        ),
    ],
    "highlight_label": "the coarse decision",
    "outputs": (
        "**Output:** `objects_summary.csv` (read first) · `classified_objects.csv` (full record) · "
        "`literature_only_entries.csv` · `catalog_coverage.json` · `pipeline_summary.csv` (time of each stage)"
    ),
}

# ---------------------------------------------------------------------------------------------------- 4 sources
SOURCES = {
    "section": "Pipeline",
    "title": "Data sources: 30 collectors",
    "lede": "Given a position and a radius, every collector asks its archive for the same field.",
    "table": overview_table("3.", "Kind"),
    "note": (
        "If a key archive (Gaia, Pan-STARRS1, Legacy Surveys, AllWISE) cannot be queried, a warning is shown above "
        "the result table and the photometry-only high-confidence path is switched off."
    ),
}

# ------------------------------------------------------------------------------------------------- 5 what decides
_ABL = overview_table("4.", "Switched off")
DECIDES = {
    "section": "Coarse class",
    "title": "What decides the class",
    "lede": "Rule ablation (2.51.0): the same raw data classified with one rule group switched off.",
    "head": [
        "Rule group switched off",
        "Bright fields (3,428 objects)",
        "COSMOS deep fields (28,194 objects)",
        "Reading",
    ],
    # (group, bright "right / wrong", cosmos "right / wrong") straight from the overview table
    "rows": [(r[0], r[1], r[2]) for r in _ABL["rows"]],
    # short readings, one per row of the overview table (same order)
    "readings": [
        "the backbone of the classification",
        "matters at the faint end",
        "contributes; QSO recall 96 to 92 % without it",
        "few labels change here; decisive when significant",
        "no effect when Legacy Surveys is present",
        "small",
        "**no contribution to the coarse class**",
    ],
    "legend_wrong": "labels that become wrong without the group (it was helping)",
    "legend_right": "labels that become right without it",
    "scale_note": "Numbers are right / wrong. Bar length is scaled within each column (the two samples differ in size).",
    "takeaway": (
        "**Optical colour and morphology, WISE mid-infrared and Gaia astrometry / DSC decide the class.** "
        "X-ray, radio and UV are used for tags and sub-types."
    ),
}

# ------------------------------------------------------------------------------------------------------ 6 fusion
_RULES = overview_table("4.", "Group")
FUSION = {
    "section": "Coarse class",
    "title": "From evidence to a class",
    "lede": "35 rows of `v2/Preprocess/classification_rules.csv`, combined by a trained fusion and one prior layer.",
    "rules_head": ["Rule group", "Rows"],
    "rules_rows": [(r[0], r[1]) for r in _RULES["rows"]],
    "rules_note": (
        "Spectroscopic rules are excluded in validation, where spectra are the truth. LS-GBM: gradient boosting "
        "trained on 149,769 DESI spectra, 95.6 % test accuracy."
    ),
    "steps": [
        (
            "Fusion",
            "Gradient-boosted trees and a sign-constrained multinomial logistic model, combined as a geometric "
            "mean. Trained on the train split of the SDSS and DESI spectroscopic benchmarks; the test split is "
            "for reporting only.",
        ),
        (
            "Deterministic motion",
            "Parallax or proper motion at 10σ or more with good quality means STAR, even against other evidence "
            "(extragalactic objects do not move).",
        ),
        (
            "One prior layer",
            "The real-sky class mix is applied once, before the decision (Saerens et al. 2002): local "
            "Gaia-density position prior, magnitude prior for QSOs, faint star:galaxy ratio from COSMOS2020 "
            "(4 % stars at r = 24).",
        ),
        (
            "Abstention",
            "`UNKNOWN` with a reason when the top probability is below 0.50 or strong evidence conflicts "
            "(Chow 1970 reject option).",
        ),
    ],
    "classes": ["STAR", "GALAXY", "QSO", "UNKNOWN"],
}

# -------------------------------------------------------------------------------------------------- 7 provenance
PROVENANCE = {
    "section": "Results",
    "title": "Provenance of every decision",
    "lede": "The accuracy of a look-up is the accuracy of the catalogue it came from, so every decision says where it came from.",
    "kinds": [
        ("CATALOG", "Copied from a literature or spectroscopic list."),
        (
            "EXTERNAL_CLASSIFIER",
            "Another survey's classifier: Gaia variability, ESP and DSC candidates, ZTF periodic list, Galaxy Zoo DESI.",
        ),
        ("INFERRED", "Measured and inferred by this program. Its own performance is measured on these decisions."),
        ("NONE", "No decision: the axis or sub-class has no basis and says so."),
    ],
    "rule": (
        "The coarse class is `CATALOG` only if removing the catalogue tags would change or remove the decision; "
        "if measurements alone give the same class it is `INFERRED`. **Most sub-classes are catalogue look-ups.**"
    ),
    "cards": [
        (
            "Literature-only entries",
            "If the only basis is a NED or SIMBAD type, the type is shown with status `LITERATURE_LABEL` and no "
            "probability, and listed in `literature_only_entries.csv`. COSMOS 2′ field: 2,361 of 3,621 objects.",
        ),
        (
            "Unconfirmed detections",
            "`UNCONFIRMED`: seen only twice in PS1 and absent from the deeper Legacy Surveys, or a "
            "Legacy-Surveys-only z-band detection without an r detection.",
        ),
        (
            "Run status on every row",
            "`run_archives_status` and `run_archives_missing`: only `complete` is a complete run, so a CSV passed "
            "on without the app still says it was degraded.",
        ),
    ],
}

# -------------------------------------------------------------------------------------------------- 8 validation
VALIDATION = {
    "section": "Validation",
    "title": "How it is validated",
    "lede": "Truth that cannot leak, a test set that is looked at once, and baselines next to every number.",
    "cards": [
        (
            "Blind independent fields",
            "Truth from spectroscopic surveys not used for training (LAMOST, 2QZ, 2dFGRS, 6dFGS, WiggleZ, APOGEE "
            "and others). Spectroscopic and literature catalogues are removed from the evidence. Sets A and B "
            "are now development sets.",
        ),
        (
            "Locked test set C",
            "60 regions at least 3.5° from sets A, B and COSMOS. The list is locked by SHA-256; scored once "
            "per release, aggregate only, with no tuning on its number.",
        ),
        (
            "Sky-cell split benchmark",
            "SDSS spectra spread over 768 equal-area sky cells, split into train, calibration and test by cell; "
            "objects used for tuning removed.",
        ),
        (
            "COSMOS deep fields",
            "HST/ACS truth and Chandra COSMOS Legacy AGN. Odd-numbered fields calibrate, even-numbered test "
            "(rule fixed before results); 17 added fields are confirmation only.",
        ),
        (
            "Statistics",
            "Bootstrap over fields or sky cells for the intervals, Wilson intervals for proportions, exact "
            "McNemar test for paired changes, balanced accuracy, ECE and NLL.",
        ),
        (
            "Baselines always reported",
            "The majority class, Gaia DSC alone, a single gradient-boosted classifier (it won on spectroscopic "
            "targets but lost on real-sky COSMOS by 2.6 points, so it is not the default).",
        ),
    ],
    "gate": (
        "**Archive-health gate:** scoring stops when the key archives are down, so the single look at a release "
        "is not spent on a degraded run."
    ),
}

# ------------------------------------------------------------------------------------------------- 9 performance
PERFORMANCE = {
    "section": "Validation",
    "title": "Performance of the coarse classifier",
    "lede": "Each row names its sample, because the samples differ a lot. An abstention counts as wrong.",
    "head": ["Test", "Result", "Sample and caveat"],
    "rows": [
        [
            "**Locked test set C**\n60 regions, 12′ radius (2.52.0)",
            "**99.65 %** (99.40–99.86)\n3,170 objects",
            "About 95 % of the truth are stars: always answering STAR scores 95.24 %. Where Gaia DSC has a class, "
            "DSC alone scores 99.52 % and the pipeline 99.81 %. Little information on galaxies and QSOs.",
        ],
        [
            "**Sky-spread SDSS spectroscopic benchmark**\n768 sky cells (2.51.3)",
            "**93.79 %** (93.24–94.30)\n9,999 objects",
            "3,333 per class, so the class mix is artificial. Recall STAR / GALAXY / QSO 98.7 / 98.5 / 84.1 %. "
            "**r > 21: 87.99 %**, QSO recall 71.6 %, star precision 69.9 %.",
        ],
        [
            "**COSMOS deep fields**\nHST/ACS truth, nine fields (2.51.0)",
            "**94.31 %** against 91.09 % for always answering GALAXY\n28,194 objects",
            "Faint objects, the hard end; no QSOs in this truth. After the 2.52.0 prior layer the test fields "
            "read 96.36 % (was 94.48 %), ECE 0.37 %.",
        ],
        [
            "**COSMOS, 17 new fields**\nconfirmation only (2.60.1 code)",
            "**96.68 %** and **96.75 %**\ntwo halves, 16,057 and 16,757 objects",
            "Nothing was tuned on them. The always-GALAXY baseline was not recomputed for these fields.",
        ],
        [
            "Blind fields, sets A and B\n200 regions each (2.46.0)",
            "99.30 % and 99.33 %\n24,663 objects together",
            "**Development sets:** about 15 releases were built while looking at them. Not unbiased.",
        ],
        [
            "Old SDSS / DESI benchmarks\ntest split (2.52.0)",
            "97.99 % / 90.33 %\nn = 1,991 / 962",
            "**Not representative:** class-balanced, concentrated in 142 SDSS plates, about 4 points higher than "
            "the sky-spread benchmark.",
        ],
    ],
    "widths": [0.26, 0.24, 0.50],
    "note": "Intervals are 95 % intervals from a bootstrap over regions or sky cells, not over objects.",
}

# ------------------------------------------------------------------------------------------------------ 10 faint
FAINT = {
    "section": "Limits",
    "title": "Limits at the faint end",
    "lede": "Bright sky is stable. At r > 21 and for quasars the classifier is weak; these are the measured limits.",
    "chart_title": "Share of X-ray-selected type-1 AGN that receive the QSO label, by r magnitude",
    "chart_source": "Chandra COSMOS Legacy type-1 AGN, nine deep COSMOS fields (2.56.0, reproduced in 2.58.0).",
    # (bin label, bar height in %, value label)
    "bars": [
        ("r < 21", 96.0, "96 %"),
        ("21–22", 76.0, "76 %"),
        ("22–23", 19.0, "19 %"),
        ("23–24", 6.5, "6–7 %"),
        ("r ≥ 24", 0.0, "0 of 33"),
    ],
    "flag_title": "The “QSO?” candidate flag",
    "flag_def": "22 ≤ r < 24, not labelled QSO, `p_qso` ≥ 0.1. The primary label is untouched.",
    "flag_stats": [
        ("24 %", "purity", "29/119\nWilson 18–33 %"),
        ("48 %", "recall", "47/97\nWilson 39–58 %"),
    ],
    "flag_note": (
        "Measured on the 21 deep COSMOS fields not used to choose the threshold. Three of four candidates are "
        "something else: a lead that needs a spectrum or X-ray / variability data."
    ),
    "items": [
        "**r > 22 high-confidence GALAXY** holds its purity (0.983) but stars are only 5 % of the truth at "
        "r > 23: it is little more than the base rate.",
        "**Faint stars are uncertain:** at r > 23 in COSMOS, star recall 65 % and precision 64 %.",
        "`p_qso` **is under-confident** at 22 ≤ r < 24; the calibration (ECE 0.37 %) does not cover it.",
    ],
}

# -------------------------------------------------------------------------------------------------- 11 operation
_TIME = overview_table("10.", "Code")
OPERATION = {
    "section": "Operation",
    "title": "Speed, archives and failures",
    "lede": "The program is only as available as the archives it queries; a degraded run is marked, not hidden.",
    "time_title": "First search of a new field, cold cache (measured 2026-11-24, three 1–2′ fields)",
    "time_table": _TIME,
    "time_items": [
        "Every request waits 3–5 s first, so run time is set mainly by the number of requests.",
        "Classification adds 4–39 s; searching the same field again uses the cache (11–46 s, measured at 2.54.0).",
        "**Bulk use is limited:** about 2–4 minutes per field.",
    ],
    "fallback_title": "Fallback routes",
    "fallback_head": ["Archive", "Fallback"],
    "fallback_rows": [
        ["VizieR (CDS)", "official mirrors in order; dead mirrors are remembered"],
        ["SIMBAD", "Harvard mirror if Strasbourg fails"],
        ["Gaia (ESA)", "VizieR copy; missing columns are named in the warning"],
        ["Pan-STARRS1 (MAST)", "VizieR DR2 copy"],
        ["Legacy Surveys (Data Lab)", "viewer catalogue when Data Lab is slow (30 s) or fails"],
        ["ATNF pulsars (HEASARC)", "VizieR copy after 30 s"],
    ],
    "marks": [
        (
            "Marking a degraded run",
            "Warning band in the app, `catalog_coverage.json`, and `run_archives_status` / `run_archives_missing` "
            "on every result row.",
        ),
        (
            "Asking again",
            "`python v2/pipeline.py --work DIR --retry-failed` asks only the key archives that failed and "
            "classifies again.",
        ),
        (
            "Footprints",
            "Archives that do not cover the field are not asked (for example NVSS and VLASS south of −40°).",
        ),
    ],
}

# ------------------------------------------------------------------------------------------------------ 12 stack
STACK = {
    "section": "Tech stack",
    "title": "Tech stack and code map",
    "lede": "All Python. The app ships no machine-learning library: the trained trees are evaluated directly in NumPy.",
    "layers": [
        (
            "App",
            "PySide6 (Qt) · PyInstaller",
            "One-folder builds for Windows, macOS and Linux, tested offline per release",
        ),
        (
            "Models",
            "NumPy-only tree inference",
            "Trees stored as `.npz`; scikit-learn only for training, excluded from the build",
        ),
        ("Data", "pandas · NumPy · SciPy · Astropy", "Tables, neighbour search, coordinates and units"),
        (
            "Archive access",
            "astroquery · PyVO (TAP) · Requests",
            "VizieR, ESA Gaia, NOIRLab Data Lab, MAST, SIMBAD, NED",
        ),
        (
            "Operations and QA",
            "GitHub Actions · pytest",
            "Data collection, validation and app builds as workflows; 307 tests at 2.60.2",
        ),
    ],
    "map_title": "Code map",
    "map_rows": [
        ("v2/Get_data/", "the 30 collectors, parallel execution, cache, mirrors, footprints"),
        ("v2/Preprocess/", "stages 1–5, rule table, fusion weights, literature notes"),
        ("v2/Classifier/", "sub-classification, the five axes, per-axis calibration"),
        ("v2/*.py", "`pipeline.py` and the post-processing modules"),
        ("v2/app/", "PySide6 app and PyInstaller packaging"),
        ("v2/benchmark/", "truth sets, preserved features, evaluation and training scripts"),
        (".github/workflows/", "data collection and validation (manual runs), app build and release"),
    ],
    "rules": (
        "**Working rules:** literature first · accuracy and speed measured together · a version and a changelog "
        "row for every merge."
    ),
}


def all_text() -> str:
    """Every string of the deck (for the tests: language, stale figures, figures present in the overview)."""
    out: list[str] = [FOOTER, DATE]

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    for block in (
        TITLE,
        GLANCE,
        PIPELINE,
        SOURCES,
        DECIDES,
        FUSION,
        PROVENANCE,
        VALIDATION,
        PERFORMANCE,
        FAINT,
        OPERATION,
        STACK,
    ):
        walk(block)
    return "\n".join(out)

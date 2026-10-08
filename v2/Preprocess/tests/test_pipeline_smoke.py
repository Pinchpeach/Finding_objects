"""End-to-end Preprocess smoke test on the committed NGC 4522 raw data."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT.parent / "rawdata"
RULES = ROOT / "classification_rules.csv"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"pre_{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_pipeline(tmp_path: Path) -> pd.DataFrame:
    import sys
    sys.path.insert(0, str(ROOT))
    a, i, f, e, l = (tmp_path / n for n in ("a.csv", "i.csv", "f.csv", "e.csv", "l.csv"))
    _load("01_source_association").run(RAW, a)
    _load("02_integrate_objects").run(a, RAW, i)
    _load("03_extract_features").run(i, RULES, f)
    _load("04_build_evidence").run(f, RULES, e)
    _load("05_likelihood_vectors").run(e, l)
    return pd.read_csv(l, low_memory=False)


def test_pipeline_runs_and_emits_valid_vectors(tmp_path):
    out = _run_pipeline(tmp_path)
    assert len(out) > 0
    total = out[["likelihood_star", "likelihood_galaxy", "likelihood_qso"]].sum(axis=1)
    assert ((total - 1.0).abs() < 1e-9).all()
    assert set(out.primary_class) <= {"STAR", "GALAXY", "QSO", "UNKNOWN"}
    # The SDSS spectrum of NGC 4522 itself is a spectroscopic galaxy.
    spec = out[out.catalogs.fillna("").str.contains("SDSS DR18 spectroscopy", regex=False)]
    assert (spec.primary_class == "GALAXY").all()


def test_evidence_applies_each_reliability_once(tmp_path):
    out = _run_pipeline(tmp_path)
    for raw in out.evidence_json:
        for ev in json.loads(raw):
            expected = ev["raw_score"] * ev["reliability"] * ev["association_reliability"]
            assert math.isclose(ev["score"], expected, rel_tol=1e-9)
            assert ev["reliability"] <= 1.0 and ev["association_reliability"] <= 1.0


def test_emit_does_not_square_association_reliability():
    mod = _load("04_build_evidence")
    rule = {"rule_id": "X", "likelihood_method": "k", "threshold_origin": "o", "feature_group": "g"}
    out = []
    mod.emit(out, rule, "GALAXY", 0.9, reliability=1.0, association_reliability=0.5)
    assert math.isclose(out[0]["score"], 0.45)


def test_proper_motion_star_rule_is_quality_gated():
    mod = _load("04_build_evidence")
    rules = pd.read_csv(RULES, keep_default_na=False)
    rule = rules[rules.rule_id == "AST-GAL-002"].iloc[0]
    row = pd.Series({
        "pmra": 50.0, "pmra_error": 1.0, "pmdec": 0.0, "pmdec_error": 1.0,
        "catalog_confidence_gaia_astrometry": 0.5,
        "association_confidence__gaia_dr3": 0.5,
    })
    (ev,) = mod.evaluate(rule, row)
    assert math.isclose(ev["score"], ev["raw_score"] * 0.25)

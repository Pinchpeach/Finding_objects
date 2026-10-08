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


def test_same_named_fields_do_not_cross_catalogs(tmp_path):
    """DESI Legacy and SDSS PhotoObj both publish ``type``; rules must read SDSS's."""
    import sys
    sys.path.insert(0, str(ROOT))
    raw = tmp_path / "raw"
    raw.mkdir()
    base = {"ra": 150.0, "dec": 2.0}
    pd.DataFrame([{**base, "catalog": "DESI Legacy Surveys DR10", "catalog_object_id": "ls1",
                   "object_name": "ls1", "type": "PSF"}]).to_csv(raw / "desi_legacy_t.csv", index=False)
    pd.DataFrame([{**base, "catalog": "SDSS DR18 PhotoObj", "catalog_object_id": "1237", "object_name": "s1",
                   "type": 3, "clean": 1}]).to_csv(raw / "sdss_dr18_t.csv", index=False)
    a, i, f, e = (tmp_path / n for n in ("a.csv", "i.csv", "f.csv", "e.csv"))
    _load("01_source_association").run(raw, a)
    _load("02_integrate_objects").run(a, raw, i)
    integrated = pd.read_csv(i)
    assert len(integrated) == 1 and integrated.loc[0, "type"] == "PSF"  # legacy bare name: first wins
    _load("03_extract_features").run(i, RULES, f)
    _load("04_build_evidence").run(f, RULES, e)
    ev = json.loads(pd.read_csv(e).loc[0, "evidence_json"])
    assert any(x["rule_id"] == "SDSS-PHOTO-001" and x["class"] == "GALAXY" for x in ev)


def test_64bit_identifiers_survive_association(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    # A missing ID in the column would make pandas parse the rest as float64.
    pd.DataFrame([
        {"catalog": "Gaia DR3", "catalog_object_id": "3796442680948579328", "object_name": "a", "ra": 10.0, "dec": 1.0},
        {"catalog": "Gaia DR3", "catalog_object_id": "3796442680948579329", "object_name": "b", "ra": 11.0, "dec": 1.0},
        {"catalog": "Gaia DR3", "catalog_object_id": None, "object_name": "c", "ra": 12.0, "dec": 1.0},
    ]).to_csv(raw / "gaia_t.csv", index=False)
    a = tmp_path / "a.csv"
    _load("01_source_association").run(raw, a)
    ids = set(pd.read_csv(a, dtype={"catalog_object_id": str}).catalog_object_id)
    assert {"3796442680948579328", "3796442680948579329"} <= ids
    assert "nan" not in ids

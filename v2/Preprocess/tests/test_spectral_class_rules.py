"""DESI DR1 / LAMOST DR5 pipeline spectral classes as evidence (2.36.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES = pd.read_csv(ROOT / "classification_rules.csv", keep_default_na=False)


def _load(name):
    spec = importlib.util.spec_from_file_location(f"spc_{name}", ROOT / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S4 = _load("04_build_evidence")
NS = frozenset({"desi_dr1_spectroscopy", "lamost_dr_catalog"})


def _ev(rid, row):
    return S4.evaluate(RULES[RULES.rule_id == rid].iloc[0], pd.Series(row), NS)


def test_desi_class_scored_by_spectrum_quality():
    row = {"desi_dr1_spectroscopy__OType": "QSO", "catalog_confidence_desi_spectroscopy": 1.0,
           "association_confidence__desi_dr1_spectroscopy": 1.0}
    (ev,) = _ev("SPC-DESI-003", row)
    assert ev["class"] == "QSO" and ev["score"] == 1.0
    assert _ev("SPC-DESI-001", row) == []  # STAR rule does not fire on a QSO spectrum
    row["catalog_confidence_desi_spectroscopy"] = 0.5
    assert _ev("SPC-DESI-003", row)[0]["score"] == 0.5


def test_lamost_unknown_is_no_evidence():
    row = {"lamost_dr_catalog__Class": "Unknown", "catalog_confidence_lamost_spectroscopy": 1.0}
    assert all(_ev(f"SPC-LAMOST-00{i}", row) == [] for i in (1, 2, 3))
    row["lamost_dr_catalog__Class"] = "STAR"
    assert _ev("SPC-LAMOST-001", row)[0]["class"] == "STAR"


def test_spectrum_rules_are_wired():
    for rid in [f"SPC-{s}-00{i}" for s in ("DESI", "LAMOST") for i in (1, 2, 3)]:
        assert rid in set(RULES.rule_id) and rid in S4.RELMAP and rid in S4.ASSOC_PREFIX
    assert {"OType", "ZWARN", "delChi2", "Prog", "Class", "snrg", "snri"} <= S4.RAW_FIELDS

"""A refit is a deterministic function of the predictions and records what it was fitted on (2.61.9)."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CLS = Path(__file__).resolve().parents[1]


def _fit_module():
    spec = importlib.util.spec_from_file_location("fit_axis_calibration_test", CLS / "calibration" / "fit_axis_calibration.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fit_axis_calibration_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _predictions(n=240, seed=3):
    rng = np.random.default_rng(seed)
    truth = rng.choice(["RR_LYRAE", "LPV"], n)
    pred = np.where(rng.uniform(size=n) < 0.8, truth, "UNKNOWN")
    return pd.DataFrame({"axis": "variability", "truth_class": truth, "predicted_class": pred, "raw_score": rng.uniform(0.3, 1.0, n), "status": "S", "family_match": truth == pred})


def test_the_same_predictions_give_the_same_coefficients_in_any_row_order(tmp_path):
    F = _fit_module()
    p = _predictions()
    p.to_csv(tmp_path / "p1.csv", index=False)
    p.sample(frac=1.0, random_state=9).to_csv(tmp_path / "p2.csv", index=False)
    a = F.fit(tmp_path / "p1.csv", tmp_path / "m1.json")
    b = F.fit(tmp_path / "p2.csv", tmp_path / "m2.json")
    for cls in ("RR_LYRAE", "LPV"):
        ea, eb = a["axes"]["variability"][cls], b["axes"]["variability"][cls]
        assert ea["method"] == "platt" and abs(ea["coef"] - eb["coef"]) < 1e-9 and abs(ea["intercept"] - eb["intercept"]) < 1e-9


def test_fitted_on_is_stored_and_rules_of_other_jobs_survive_a_refit(tmp_path):
    F = _fit_module()
    _predictions().to_csv(tmp_path / "p.csv", index=False)
    out = tmp_path / "models.json"
    out.write_text(json.dumps({"rules": {"physical": {"X|HOT": {"method": "rule_precision", "external_source": "benchmark", "precision": 0.9, "n": 100, "correct": 90}}}}))
    stamp = {"truth_list_sha256": "ab" * 32, "predictions_sha256": "cd" * 32, "run_status": "OK"}
    r = F.fit(tmp_path / "p.csv", out, stamp)
    assert r["fitted_on"] == stamp and json.loads(out.read_text())["fitted_on"] == stamp
    assert r["rules"]["physical"]["X|HOT"]["precision"] == 0.9
    assert "fitted_on" not in F.fit(tmp_path / "p.csv", tmp_path / "other.json")

"""Tractor fit-quality, stellar-locus and WISE colour features (2.44.0)."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
PRE = V2 / "Preprocess"
sys.path.insert(0, str(PRE))
import ls_gbm  # noqa: E402

P = "desi_legacy_surveys_dr10__"


def _load(name, file):
    s = importlib.util.spec_from_file_location(name, PRE / file)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _objects():
    # a star (PSF fit, no size) and a galaxy (REX gains 50 % over PSF, r_e at 20 sigma)
    flux = {"g": (10.0, 3.0), "r": (20.0, 6.0), "z": (30.0, 12.0), "w1": (20.0, 30.0), "w2": (12.0, 20.0)}
    d = {"object_id": ["star", "gal"], "ra": [150.0, 150.01], "dec": [2.0, 2.01], "catalogs": ["DESI Legacy Surveys DR10|AllWISE"] * 2}
    for b, v in flux.items():
        d[P + f"flux_{b}"] = list(v)
        d[P + f"flux_ivar_{b}"] = [100.0, 100.0]
        d[P + f"mw_transmission_{b}"] = [1.0, 1.0]
    d[P + "type"] = ["PSF", "REX"]
    d[P + "dchisq_1"] = [1000.0, 1000.0]
    d[P + "dchisq_2"] = [1000.5, 1500.0]
    d[P + "shape_r"] = [0.0, 1.0]
    d[P + "shape_r_ivar"] = [0.0, 400.0]
    d["allwise__W1mag"] = [14.0, 14.5]
    d["allwise__W2mag"] = [14.0, 14.0]
    d["allwise__W3mag"] = [12.0, 10.5]
    d["allwise__snr3"] = [2.0, 8.0]
    return pd.DataFrame(d)


def test_ls_gbm_features_by_name():
    X = ls_gbm.features(_objects(), names=ls_gbm.FIT_FEATURES)
    rel, size, exc = X.T
    assert rel[0] < -2.5 and abs(rel[1] - np.log10(0.5 + 1e-4)) < 1e-9  # PSF ~ REX; REX 50 % better
    assert size[0] == 0 and abs(size[1] - np.log10(21.0)) < 1e-9
    r, z, w1 = (22.5 - 2.5 * np.log10(f) for f in (6.0, 12.0, 30.0))
    assert abs(exc[1] - ((z - w1) - (0.8 * (r - z) - 0.6))) < 1e-9
    # older models keep their own columns: FEATURES are unchanged and first
    assert ls_gbm.ALL_FEATURES[: len(ls_gbm.FEATURES)] == ls_gbm.FEATURES


def test_stage3_and_stage4_emit_the_features(tmp_path):
    s3, s4 = _load("s3f", "03_extract_features.py"), _load("s4f", "04_build_evidence.py")
    o = tmp_path / "o.csv"
    _objects().to_csv(o, index=False)
    f, e = tmp_path / "f.csv", tmp_path / "e.csv"
    s3.run(o, PRE / "classification_rules.csv", f)
    s4.run(f, PRE / "classification_rules.csv", e)
    ev = [json.loads(x) for x in pd.read_csv(e).evidence_json]
    feats = [{x["class"]: x["value"] for x in items if x.get("kind") == "linear_feature"} for items in ev]
    for k in ("zw1_excess", "dchisq_rex_rel_log", "size_sig_log"):
        assert f"FEATURE:{k}" in feats[1] and feats[1][f"FEATURE:{k}_present"] == 1.0
    assert feats[1]["FEATURE:wise_w2_w3"] == 3.5 and feats[1]["FEATURE:wise_w1_w2"] == 0.5
    assert "FEATURE:wise_w2_w3" not in feats[0]  # W3 below S/N 3
    assert feats[0]["FEATURE:size_sig_log"] == 0.0

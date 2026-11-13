import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

P = Path(__file__).resolve().parents[1]
_s = importlib.util.spec_from_file_location("v2_class_prior_t", P / "class_prior.py")
CP = importlib.util.module_from_spec(_s)
_s.loader.exec_module(CP)
C = ["STAR", "GALAXY", "QSO"]


def test_faint_split_moves_mass_only_between_star_and_galaxy():
    Q = np.array([[0.6, 0.3, 0.1], [0.2, 0.2, 0.6], [0.5, 0.5, 0.0]])
    F = np.array([[0.3, 2.4], [0.3, 2.4], [np.nan, np.nan]])
    out = CP.faint_split(Q, F)
    assert np.allclose(out.sum(1), 1)
    assert np.allclose(out[:, 2], Q[:, 2])  # QSO share unchanged
    # odds(G:S) multiplied by F_G / F_S = 8
    assert np.isclose(out[0, 1] / out[0, 0], (0.3 / 0.6) * 8)
    assert np.allclose(out[2], Q[2])  # no factor: unchanged


def test_layer_switch(monkeypatch):
    monkeypatch.delenv("V2_PRIOR_LAYER", raising=False)
    assert CP.layer() == "unified"  # default since 2.52.0
    monkeypatch.setenv("V2_PRIOR_LAYER", "legacy")
    assert CP.layer() == "legacy"
    monkeypatch.setenv("V2_PRIOR_LAYER", "other")
    try:
        CP.layer()
    except ValueError:
        pass
    else:
        raise AssertionError("unknown layer accepted")


def test_reported_probabilities_agree_with_rule_labels():
    Pc = np.array([[0.7, 0.2, 0.1], [0.7, 0.2, 0.1], [0.7, 0.2, 0.1]])
    out = CP.consistent(Pc, ["STAR", "GALAXY", "UNKNOWN"], [0.7, 0.9, np.nan], C)
    assert np.allclose(out[0], Pc[0])  # evidence decision: unchanged
    assert np.isclose(out[1, 1], 0.9) and out[1].argmax() == 1 and np.isclose(out[1].sum(), 1)
    assert np.isclose(out[1, 0] / out[1, 2], 7.0)  # rest shared in proportion
    assert np.allclose(out[2], Pc[2])  # UNKNOWN: unchanged


def test_cosmos_faint_counts_lean_to_galaxy_at_the_faint_end():
    _f = importlib.util.spec_from_file_location("v2_faint_t", P / "faint_class_prior.py")
    F = importlib.util.module_from_spec(_f)
    _f.loader.exec_module(F)
    df = pd.DataFrame({"std_mag__ls_r": [19.0, 20.1, 24.2, 30.0, np.nan], "ra": 150.1, "dec": 2.2})
    f = F.star_galaxy_factors(df, which="cosmos")
    assert np.isnan(f[0]).all() and np.isnan(f[4]).all()  # r < 20, no r: not applied
    assert np.allclose(f[1:4].sum(1), 3.0)  # STAR + GALAXY fractions x 3
    assert f[2, 0] / f[2, 1] < 0.1  # r = 24: < 10 % stars in COSMOS2020
    assert f[1, 0] > f[2, 0]  # stars thin out to r = 24


def test_stage5_unified_layer_puts_the_faint_prior_into_p(tmp_path, monkeypatch):
    """A faint source with weak star evidence at high latitude (r = 24.2): the
    legacy layer abstains (p_star 0.38; its faint prior acts only after a
    STAR/GALAXY decision); the unified layer moves the probability before the
    decision, so it is classified and p_* agree with the label."""
    import json

    spec = importlib.util.spec_from_file_location("s5_unified", P / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    ev = [{"rule_id": "LS-MORPH-001", "class": "STAR", "score": 0.7, "raw_score": 0.7, "kind": "morphology"}]
    d = pd.DataFrame({"object_id": ["F1"], "ra": [150.1], "dec": [2.2], "std_mag__ls_r": [24.2],
                      "catalogs": ["DESI Legacy Surveys DR10"], "evidence_json": [json.dumps(ev)]})
    src = tmp_path / "e.csv"
    d.to_csv(src, index=False)
    out = {}
    for lay in ("legacy", "unified"):
        monkeypatch.setenv("V2_PRIOR_LAYER", lay)
        monkeypatch.setenv("V2_FAINT_PRIOR", "cosmos")
        s5.run(src, tmp_path / f"{lay}.csv")
        out[lay] = pd.read_csv(tmp_path / f"{lay}.csv").iloc[0]
    u = out["unified"]
    if u.primary_class in C:
        assert max(C, key=lambda c: u[f"p_{c.lower()}"]) == u.primary_class
        assert np.isclose(u[f"p_{u.primary_class.lower()}"], u.primary_confidence)
    assert u.prior_layer == "unified" and out["legacy"].prior_layer == "legacy"
    assert u.p_galaxy > out["legacy"].p_galaxy  # the faint counts entered p_*
    assert np.isclose(u.p_qso, out["legacy"].p_qso)  # QSO share unchanged

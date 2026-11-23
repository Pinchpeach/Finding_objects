"""Faint quasar candidates and the COSMOS QSO share (2.57.0)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qso_options_faint", ROOT / "qso_options.py")
Q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Q)


def _frame(r, extra=None):
    return pd.DataFrame({"std_mag__ls_r": r, **(extra or {})})


def test_candidate_flag_is_off_unless_a_threshold_is_set(monkeypatch):
    monkeypatch.delenv("V2_FAINT_QSO_CANDIDATE", raising=False)
    monkeypatch.setattr(Q, "CANDIDATE_P", None)
    assert Q.candidate_threshold() is None
    df = _frame([22.5])
    assert Q.faint_candidates(df, ["GALAXY"], [0.9], [""], [""]) == ([""], [""])  # unchanged
    monkeypatch.setenv("V2_FAINT_QSO_CANDIDATE", "0")  # 0 / none / false are "off", not a threshold of zero
    assert Q.candidate_threshold() is None
    for bad in ("1.5", "-0.1", "1"):
        monkeypatch.setenv("V2_FAINT_QSO_CANDIDATE", bad)
        with pytest.raises(ValueError):
            Q.candidate_threshold()


def test_candidate_flag_rules(monkeypatch):
    monkeypatch.setenv("V2_FAINT_QSO_CANDIDATE", "0.1")
    df = _frame([21.9, 22.0, 23.9, 24.0, 22.5, 22.5, 22.5, np.nan, 22.5])
    labels = ["GALAXY", "GALAXY", "UNKNOWN", "GALAXY", "QSO", "GALAXY", "GALAXY", "GALAXY", "STAR"]
    p = [0.9, 0.1, 0.5, 0.9, 0.9, 0.0999, 0.3, 0.9, np.nan]
    sec = ["", "", "", "", "", "", "QSO", "", ""]
    why = ["", "", "", "", "", "", "GALAXY_WISE_AGN", "", ""]
    s2, w2 = Q.faint_candidates(df, labels, p, sec, why)
    flagged = [i for i, x in enumerate(w2) if x == Q.CANDIDATE_REASON]
    # r in [22, 24) only (22.0 in, 24.0 out), a label that is not QSO, p >= 0.1 (the boundary counts), a finite r and p
    assert flagged == [1, 2]
    assert s2[1] == "QSO" and s2[2] == "QSO"
    assert w2[6] == "GALAXY_WISE_AGN"  # an existing reading is kept
    assert sec == ["", "", "", "", "", "", "QSO", "", ""]  # the inputs are not modified


def test_share_factor_is_off_by_default_and_tempered_by_mode(monkeypatch):
    monkeypatch.delenv("V2_FAINT_QSO_SHARE", raising=False)
    df = _frame([21.5, 22.2, 23.4, 24.2, np.nan])
    assert np.isnan(Q.faint_share_factor(df)).all()
    table = pd.DataFrame({"r_lo": [22.0, 23.0], "r_hi": [23.0, 24.0], "n_type1": [20, 10], "n_other": [1980, 3990]})
    half = Q.faint_share_factor(df, table, "half")
    full = Q.faint_share_factor(df, table, "full")
    assert np.isnan(half[[0, 3, 4]]).all()  # outside 22 <= r < 24 and no r: the default prior applies
    pi = (20 + 0.5) / (2000 + 1)
    odds = (pi / (1 - pi)) / 0.5  # training prior 1/3: odds 1/2
    assert full[1] == pytest.approx(odds) and half[1] == pytest.approx(np.sqrt(odds))
    assert half[2] < half[1] < 1  # fewer quasars per object in the fainter bin
    monkeypatch.setenv("V2_FAINT_QSO_SHARE", "x")
    with pytest.raises(ValueError):
        Q.share_mode()

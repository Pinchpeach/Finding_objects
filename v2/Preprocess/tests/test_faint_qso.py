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


def _bench(name):
    import sys

    bench = ROOT.parent / "benchmark"
    sys.path.insert(0, str(bench))
    s = importlib.util.spec_from_file_location(f"{name}_t", bench / f"{name}.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_union_table_with_an_empty_split_does_not_divide_by_zero():
    """PR #74 review: with --fields of one split only, the other split has no type 1 objects."""
    pytest.importorskip("astropy")
    F = _bench("faint_qso_candidates")
    m = pd.DataFrame(
        {
            "split": ["cal", "cal", "cal"],
            "truth": ["TYPE1", "GALAXY", "GALAXY"],
            "o_std_mag__ls_r": [22.5, 22.6, 23.1],
            "o_primary_class": ["GALAXY", "GALAXY", "GALAXY"],
            "o_p_qso": [0.3, 0.2, 0.01],
        }
    )
    t = F.union_table(m, thresholds=(0.1,))
    test = t[t.split == "test"].iloc[0]
    assert test.n_type1 == 0 and np.isnan(test.recall) and test.recall_wilson95 is None
    cal = t[t.split == "cal"].iloc[0]
    assert cal.type1_claimed == 1 and cal.claims == 2 and cal.recall == 1.0


def test_reference_scores_do_not_count_a_faint_candidate_as_the_other_reading():
    """PR #74 review: validate_reference_objects counted secondary QSO (coarse_either, type tokens) also when it
    was only a FAINT_QSO_CANDIDATE."""
    V = _bench("validate_reference_objects")
    assert "secondary_class_reason" in V.KEEP and "secondary_class_reason" not in V.LABEL_COLS
    cand = {"primary_class": "GALAXY", "secondary_class": "QSO", "secondary_class_reason": "FAINT_QSO_CANDIDATE"}
    dual = {"primary_class": "GALAXY", "secondary_class": "QSO", "secondary_class_reason": "GALAXY_WISE_AGN"}
    assert "QSO" not in V.tokens(V.drop_candidate(cand))
    assert "QSO" in V.tokens(V.drop_candidate(dual))


def test_without_legacy_surveys_no_other_survey_r_stands_in_for_the_candidate_range(monkeypatch):
    """2.59.0 check: outside the Legacy Surveys footprint (the Galactic plane fields) only PS1 / SDSS / Gaia r exist.
    The candidate range 22 <= r < 24 and the 0.1 threshold were measured on LS r, so another survey's r is not used."""
    monkeypatch.setenv("V2_FAINT_QSO_CANDIDATE", "0.1")
    df = pd.DataFrame(
        {
            "std_mag__ps1_r": [23.0, 23.0],
            "std_mag__sdss_r": [23.0, np.nan],
            "gaia_dr3__phot_g_mean_mag": [20.5, 20.5],
        }
    )
    sec, why = Q.faint_candidates(df, ["GALAXY", "GALAXY"], [0.9, 0.9], ["", ""], ["", ""])
    assert sec == ["", ""] and why == ["", ""]
    df["std_mag__ls_r"] = [23.0, 23.0]  # the same rows with a Legacy Surveys r are flagged
    assert Q.faint_candidates(df, ["GALAXY", "GALAXY"], [0.9, 0.9], ["", ""], ["", ""])[0] == ["QSO", "QSO"]


# ---------------------------------------------------- the second set of deep COSMOS fields (2.59.0 preparation)
BENCH = ROOT.parent / "benchmark"


def _bench(name):
    import sys

    sys.path.insert(0, str(BENCH))
    s = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_new_field_list_follows_its_rule():
    sel = _bench("select_deep_cosmos_2")
    c = sel.candidates()
    assert len(c) >= 10
    # no new field touches an existing one or another new one (6' radius: centres >= 12.6' apart)
    for r in c.itertuples():
        assert r.gap_to_existing_deg >= sel.GRID_STEP_DEG - 1e-6 and r.n_chandra >= c.attrs["floor"]
    for i, a in c.iterrows():
        for _, b in c.iloc[i + 1 :].iterrows():
            assert sel.sep_deg(a.ra, a.dec, b.ra, b.dec) >= sel.GRID_STEP_DEG - 1e-3
    assert list(c.distance_deg) == sorted(c.distance_deg)  # ordered by distance from the anchor


def test_the_committed_field_list_is_the_rule_output():
    """The file is locked by its SHA-256 (DEEP_COSMOS_EXPANSION.md): rows keep the names, centres and the parity split."""
    sel = _bench("select_deep_cosmos_2")
    if not sel.OUT.exists():
        pytest.skip("field list not written yet")
    t = pd.read_csv(sel.OUT)
    assert list(t.name) == [f"deep_cosmos_{sel.FIRST_NUMBER + k}" for k in range(len(t))]
    assert (t.r == 6.0).all()
    assert all(s == ("cal" if int(n.rsplit("_", 1)[1]) % 2 else "test") for n, s in zip(t.name, t.split))
    offline = sel.candidates().set_index(["ra", "dec"])
    assert all((r.ra, r.dec) in offline.index for r in t.itertuples())  # the archive checks only drop, never add


def test_gaia_source_of_a_collection(tmp_path):
    col = _bench("collect_deep_cosmos")
    assert col.gaia_source(tmp_path) == "none"
    pd.DataFrame({"gaia_base_query_status": ["tap"]}).to_csv(tmp_path / "gaia_dr3_ra1_dec2_r6arcmin.csv", index=False)
    assert col.gaia_source(tmp_path) == "tap"
    pd.DataFrame({"gaia_base_query_status": ["vizier_fallback"]}).to_csv(tmp_path / "gaia_dr3_ra1_dec2_r6arcmin.csv", index=False)
    assert col.gaia_source(tmp_path) == "vizier_fallback"


def test_the_field_list_is_locked_by_the_hash_in_its_document():
    """The workflow v2_deep_cosmos.yml refuses a list whose SHA-256 differs from the one in DEEP_COSMOS_EXPANSION.md."""
    import hashlib
    import re

    sel = _bench("select_deep_cosmos_2")
    if not sel.OUT.exists():
        pytest.skip("field list not written yet")
    doc = (BENCH / "DEEP_COSMOS_EXPANSION.md").read_text(encoding="utf-8")
    locked = re.search(r"sha256: `([0-9a-f]{64})`", doc).group(1)
    assert hashlib.sha256(sel.OUT.read_bytes()).hexdigest() == locked

"""The measurement helpers of the ambiguity study (2.61.7): small synthetic cases with known answers."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
D = V2 / "benchmark" / "association_ambiguity"


def load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_label_changes_pairs_objects_by_position_not_by_id():
    lc = load("label_changes")
    a = pd.DataFrame(dict(ra=[10.0, 10.001, 10.002], dec=[0.0, 0.0, 0.0]))
    # the variant lost the middle object (it joined the first) and its ids would all shift: pairing is by position
    b = pd.DataFrame(dict(ra=[10.0 + 0.05 / 3600, 10.002], dec=[0.0, 0.0]))
    ia, ib = lc.pair(a, b, 0.2)
    assert list(ia) == [0, 2] and list(ib) == [0, 1]
    far = pd.DataFrame(dict(ra=[10.0 + 5 / 3600], dec=[0.0]))
    assert len(lc.pair(a, far, 0.2)[0]) == 0  # beyond the tolerance: no pair


def test_exchange_counts_new_and_lost_joins_by_outcome():
    cv = load("compare_variants")
    base = pd.DataFrame(dict(catalog="AllWISE", field_row=["a", "b", "c", "d"], joined=[False, False, True, True], outcome=["missed", "missed", "correct", "false"]))
    var = pd.DataFrame(dict(catalog="AllWISE", field_row=["a", "b", "c", "d"], joined=[True, True, True, False], outcome=["correct", "unknown", "correct", "rightly_alone"]))
    ex = cv.exchange(base, var, "AllWISE")
    assert (ex["newly_joined"], ex["new_correct"], ex["new_false"], ex["new_unknown"]) == (2, 1, 0, 1)
    assert (ex["unjoined_now"], ex["lost_false"], ex["lost_correct"]) == (1, 1, 0)
    assert ex["net_correct"] == 1 and ex["net_false"] == -1  # a false link was dropped, a correct one gained
    # a row joined in both runs whose outcome changes counts in the net (Codex review of 2.61.8)
    base2 = pd.DataFrame(dict(catalog="GALEX AIS", field_row=["a", "b", "c"], joined=[True, True, False], outcome=["false", "correct", "missed"]))
    var2 = pd.DataFrame(dict(catalog="GALEX AIS", field_row=["a", "b", "c"], joined=[True, True, True], outcome=["unknown", "false", "correct"]))
    ex2 = cv.exchange(base2, var2, "GALEX AIS")
    assert (ex2["switched"], ex2["switched_from_false"], ex2["switched_to_false"], ex2["switched_from_correct"]) == (2, 1, 1, 1)
    assert (ex2["net_correct"], ex2["net_false"], ex2["net_unknown"]) == (0, 0, 1)  # +1 correct (c) -1 correct (b); false a -> unknown, b -> false
    lo, hi = cv.wilson(0, 100)
    assert lo == 0.0 or abs(lo) < 1e-9
    assert 3.0 < hi < 4.5


def test_candidate_rules_of_the_predictions():
    pr = load("predict_from_calibration")
    d = pd.DataFrame(dict(catalog=["SDSS DR18 PhotoObj", "AllWISE", "AllWISE", "GALEX AIS"], c12_sep=[0.1, 0.9, 0.9, 0.2],
                          sep1=[0.05, 0.05, 0.4, 0.5], sep2=[0.3, 0.6, 0.5, 0.7], has_truth=True,
                          best_score=["right", "right", "wrong", "right"], nearest=["right", "right", "right", "wrong"]))  # fmt: skip
    assert len(pr.apply_rule(d, "same")) == 2  # anchors closer than 0.3''
    nr = pr.apply_rule(d, "nearest")  # nearest < 0.3'' and the next >= 3 times further: rows 0 (0.05, 0.3) and 1 (0.05, 0.6)
    assert list(nr.catalog) == ["SDSS DR18 PhotoObj", "AllWISE"]
    assert len(pr.apply_rule(d, "best")) == 4


def test_ambiguous_row_flags_distance_and_same_object():
    an = load("analyse_ambiguity")
    d = pd.DataFrame(dict(association_status=["ambiguous_new", "matched"], object_id=["o1", "o2"], catalog="AllWISE", candidate_count=[2, 1],
                          diag_all_sep=["0.05|0.60", ""], diag_all_nsep=["0.1|1.0", ""], diag_all_score=["0.9|0.8", ""], diag_c12_nsep=[0.5, np.nan]))  # fmt: skip
    f = an.flags(d)
    assert len(f) == 1
    r = f.iloc[0]
    assert r.clear_distance and not r.clear_nsep  # 0.05'' against 0.60'': clear in distance, the likelihood ratio of the nsep is not
    assert r.same_object  # c12_nsep < 1
    assert not r.nearest_not_best


def test_lowlat_exchange_matches_each_variant_on_its_own_coordinates():
    """Codex review of 2.61.8: after a renumbering the same object id is another source; the match uses each variant's positions."""
    le = load("lowlat_exchange")
    a = 1 / 3600
    t = pd.DataFrame(dict(region="r1", variant=["base", "base", "v", "v"], object_id=["O2", "O3", "O2", "O3"], ra=[150.0 + 30 * a, 150.0 + 90 * a, 150.0 + 60 * a, 150.0 + 90 * a],
                          dec=2.0, ps1_i=[19.0, 21.0, 20.0, 21.0], n_catalogs=[2, 3, 2, 3]))  # fmt: skip
    ex = le.exchange(t, "base", "v", 1.0)
    assert (ex["kept"], ex["lost"], ex["gained"]) == (1, 1, 1)  # O3 kept; base O2 (+30'') lost, variant O2 (+60'') gained: not "kept" by id
    assert (ex["lost_i_lt_195"], ex["gained_i_lt_195"]) == (1, 0)
    wide = pd.DataFrame(dict(region="r1", object_id=["O2"], ra=[150.0], dec=[2.0], base=[True], v=[True]))
    try:
        le.exchange(wide, "base", "v", 1.0)
    except ValueError as e:
        assert "long table" in str(e)
    else:
        raise AssertionError("the wide table must be refused")


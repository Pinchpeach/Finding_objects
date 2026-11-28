"""``right_object_recount.py`` (task "러", 2.62.7): the reading of an association change that does not depend on who anchors an object.

The three cases that METRICS.md is about: a pure relabelling (an anchor becomes a joined row: ``correct`` +1, ``rightly_alone`` -1) is NOT a gain, a joined missed row is, and a row that
turns from "missed" into "rightly alone" (the counterpart's object now sits inside its own object) is a gain that ``correct`` does not see.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark" / "association_truth"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark"))
import right_object_recount as RR  # noqa: E402

FIELDS = [f"deep_cosmos_{i}" for i in range(1, 27)]


def rows(variant: str, **chg) -> pd.DataFrame:
    """One AllWISE record per field: 100 rows, 90 with an expected counterpart, a fixed baseline; ``chg`` is added to field 1 and field 12 only."""
    out = []
    for f in FIELDS:
        r = dict(variant=variant, field=f, catalog="AllWISE", rows=100, no_expected=10, matched=60, correct=50, false=2, unknown=8, missed=20, rightly_alone=20, shift_rows=100, shift_false=8, shift_any=20)
        if f in ("deep_cosmos_1", "deep_cosmos_12"):
            for k, v in chg.items():
                r[k] += v
        out.append(r)
    return pd.DataFrame(out)


def run(**chg):
    per = pd.concat([rows("base"), rows("v", **chg)], ignore_index=True)
    splits = {"cal9": FIELDS[:9], "conf17": FIELDS[9:], "all26": FIELDS}
    _, d = RR.compute(per, splits, "base")
    return d.set_index("split")


def test_splits_follow_the_field_number():
    s = pd.DataFrame({"name": FIELDS, "split": ["calibration"] * 15 + ["test"] * 11}).set_index("name").reset_index()
    p = Path(__file__).parent / "_split_tmp.csv"
    s.to_csv(p, index=False)
    try:
        sp = RR.split_fields(FIELDS, p)
    finally:
        p.unlink()
    assert sp["cal9"] == FIELDS[:9] and sp["conf17"] == FIELDS[9:] and len(sp["cal15"]) == 15 and len(sp["test11"]) == 11 and len(sp["all26"]) == 26


def test_relabelling_is_not_a_gain():
    d = run(correct=+1, rightly_alone=-1, matched=+1)
    assert d.loc["all26", "d_correct"] == 2 and d.loc["all26", "d_rightly_alone"] == -2
    assert d.loc["all26", "d_right_object"] == 0 and d.loc["all26", "relabel_share_of_d_correct_pct"] == 100.0


def test_a_new_correct_join_is_a_gain_without_relabelling():
    d = run(correct=+1, missed=-1, matched=+1)
    assert d.loc["all26", "d_right_object"] == 2 and d.loc["all26", "d_missed"] == -2 and d.loc["all26", "relabel_share_of_d_correct_pct"] == 0.0
    assert d.loc["cal9", "d_right_object"] == 1 and d.loc["conf17", "d_right_object"] == 1  # field 1 is in the calibration nine, field 12 in the confirmation seventeen


def test_missed_to_rightly_alone_is_seen_by_right_object_not_by_correct():
    d = run(missed=-3, rightly_alone=+3)
    assert d.loc["all26", "d_correct"] == 0 and d.loc["all26", "d_right_object"] == 6 and d.loc["all26", "d_missed"] == -6


def test_chance_joins_do_not_depend_on_the_anchor():
    d = run(shift_false=+5, shift_any=-3)  # the anchored reading gets worse while the anchor independent one gets better (the case of ``floored``)
    assert d.loc["all26", "d_shifted_false_pct"] > 0 > d.loc["all26", "d_shifted_any_pct"]


def test_bootstrap_interval_contains_the_estimate_and_counts_fields():
    d = run(correct=+1, missed=-1, matched=+1)
    r = d.loc["all26"]
    lo, hi = (float(x) for x in r.d_right_object_ci.split(" to "))
    assert lo <= r.d_right_object_pp <= hi + 1e-9 and r.fields_with_positive_d_right_object == 2 and r.fields_with_negative_d_right_object == 0

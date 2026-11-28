"""``right_object_recount.py`` (task "러", 2.62.7): the reading of an association change that does not depend on who anchors an object.

The cases that METRICS.md is about (``right_object`` = ``correct`` + ``alone_identified``, the reading of the 2.62.7 review): a pure relabelling (an anchor holding its counterpart becomes a joined
row: ``correct`` +1, ``alone_identified`` -1) is NOT a gain, a joined missed row is, a row that turns from "missed" into "alone, its own object holds the counterpart" is a gain that ``correct`` does
not see, and a row without any counterpart that is joined to an object without truth id (``rightly_alone`` -> ``unknown``) is neither a gain nor a loss.
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
        r = dict(variant=variant, field=f, catalog="AllWISE", rows=100, no_expected=10, matched=60, correct=50, false=2, unknown=8, missed=20, rightly_alone=20, alone_identified=15, alone_wrong=0, alone_unidentified=5, shared=10, displaced=12, shift_rows=100, shift_false=8, shift_any=20)
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
    d = run(correct=+1, rightly_alone=-1, alone_identified=-1, matched=+1)
    assert d.loc["all26", "d_correct"] == 2 and d.loc["all26", "d_alone_identified"] == -2
    assert d.loc["all26", "d_right_object"] == 0 and d.loc["all26", "relabel_share_of_d_correct_pct"] == 100.0


def test_a_new_correct_join_is_a_gain_without_relabelling():
    d = run(correct=+1, missed=-1, matched=+1)
    assert d.loc["all26", "d_right_object"] == 2 and d.loc["all26", "d_missed"] == -2 and d.loc["all26", "relabel_share_of_d_correct_pct"] == 0.0
    assert d.loc["cal9", "d_right_object"] == 1 and d.loc["conf17", "d_right_object"] == 1  # field 1 is in the calibration nine, field 12 in the confirmation seventeen


def test_a_row_without_counterpart_joined_to_an_object_without_truth_id_does_not_move_right_object():
    """The flaw of the first right_object (correct + rightly_alone): the same row alone is rightly_alone, joined to an object without truth id it is unknown."""
    d = run(rightly_alone=-1, alone_unidentified=-1, unknown=+1, matched=+1)
    assert d.loc["all26", "d_right_object"] == 0 and d.loc["all26", "d_unidentified"] == 0 and d.loc["all26", "d_rightly_alone"] == -2  # the old sum would have lost 2 rows


def test_missed_to_alone_identified_is_seen_by_right_object_not_by_correct():
    d = run(missed=-3, rightly_alone=+3, alone_identified=+3)
    assert d.loc["all26", "d_correct"] == 0 and d.loc["all26", "d_right_object"] == 6 and d.loc["all26", "d_missed"] == -6


def test_chance_joins_do_not_depend_on_the_anchor():
    d = run(shift_false=+5, shift_any=-3)  # the anchored reading gets worse while the anchor independent one gets better (the case of ``floored``)
    assert d.loc["all26", "d_shifted_false_pct"] > 0 > d.loc["all26", "d_shifted_any_pct"]


def test_bootstrap_interval_contains_the_estimate_and_counts_fields():
    d = run(correct=+1, missed=-1, matched=+1)
    r = d.loc["all26"]
    lo, hi = (float(x) for x in r.d_right_object_ci.split(" to "))
    assert lo <= r.d_right_object_pp <= hi + 1e-9 and r.fields_with_positive_d_right_object == 2 and r.fields_with_negative_d_right_object == 0


def test_the_headline_readings_are_the_ones_metrics_md_marks_as_independent_of_the_anchor():
    """A variant comparison concludes only from readings that do not move when an anchor changes (METRICS.md section 2): the tool's HEADLINE and the document stay in step."""
    import re

    text = (Path(__file__).resolve().parents[2] / "benchmark" / "association_truth" / "METRICS.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        if line.startswith("| ") and line.count("|") >= 5:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            for name in re.findall(r"`([a-z_]+)`", cells[0]):
                rows.setdefault(name, cells)
    for name in RR.HEADLINE:
        assert name in rows, f"{name} is not defined in METRICS.md"
        assert rows[name][2].startswith("**아니오**") or rows[name][2].startswith("아니오"), f"{name} is marked as anchor dependent: {rows[name][2]}"
        assert "예" in rows[name][3], f"{name} is not marked for variant comparison"
    for name in ("correct", "missed", "rightly_alone", "shifted_false_pct"):
        assert name in rows and "아니오" not in rows[name][2][:6], f"{name} should be marked as anchor dependent"
        assert rows[name][3].replace("*", "").startswith("아니오"), f"{name} must not be marked for variant comparison"


def test_a_measurement_without_the_new_counts_is_refused_not_read_as_zero(tmp_path):
    """Codex review of 2.62.10: a per-field JSON made before alone_* / shared / displaced existed must not give right_object = correct and zero fragments."""
    import json

    import pytest

    (tmp_path / "meas_old").mkdir()
    old = [{"field": "deep_cosmos_1", "AllWISE": {"rows": 10, "no_expected": 1, "matched": 5, "correct": 4, "false": 1, "unknown": 0, "missed": 2, "rightly_alone": 2}}]
    (tmp_path / "meas_old" / "per_field_old.json").write_text(json.dumps(old))
    with pytest.raises(SystemExit, match="re-run measure_association"):
        RR.field_table(tmp_path, "old")
    new = [{"field": "deep_cosmos_1", "AllWISE": {k: 1 for k in RR.COUNTS if k not in RR.SHIFT}}]  # no shifted copy measured
    (tmp_path / "meas_new").mkdir()
    (tmp_path / "meas_new" / "per_field_new.json").write_text(json.dumps(new))
    t = RR.field_table(tmp_path, "new")
    assert t.shift_any.isna().all() and RR.totals(t).shift_any.isna().all()  # missing, not 0


def test_the_runner_waits_for_every_background_job_by_its_pid():
    """Codex review of 2.62.10: a bare `wait` returns 0 whatever the children did."""
    import re

    text = (Path(__file__).resolve().parents[2] / "benchmark" / "association_truth" / "run_right_object_variants.sh").read_text()
    code = [l.split("#")[0] for l in text.splitlines()]
    assert not any(re.fullmatch(r"\s*wait\s*;?\s*", l) or re.search(r"then wait;", l) for l in code), "a bare wait"
    assert any('wait "$p"' in l for l in code) and sum("PIDS+=($!)" in l for l in code) == 2


def test_without_a_shifted_copy_the_shift_deltas_stay_missing_and_the_rest_is_computed():
    """Codex review of 2.62.10: the NaN shift counts of a measurement without --shifted-dir must not stop the delta table (int(NaN))."""
    import math

    base, v = rows("base"), rows("v", correct=+1, missed=-1, matched=+1)
    for t in (base, v):
        t[["shift_rows", "shift_false", "shift_any"]] = float("nan")
    _, d = RR.compute(pd.concat([base, v], ignore_index=True), {"all26": FIELDS}, "base")
    r = d.set_index("split").loc["all26"]
    assert r.d_right_object == 2 and math.isnan(r.d_shift_false) and math.isnan(r.d_shift_any) and math.isnan(r.d_shifted_any_pct)


def test_variants_that_do_not_cover_the_same_fields_are_refused():
    """Codex review of 2.62.10: a variant missing a field would be summed over 25 fields against the base's 26 under the same "fields" count."""
    import pytest

    v = rows("v")
    per = pd.concat([rows("base"), v[v.field != "deep_cosmos_7"]], ignore_index=True)
    with pytest.raises(SystemExit, match="v: lacks deep_cosmos_7/AllWISE"):
        RR.compute(per, {"all26": FIELDS}, "base")
    with pytest.raises(SystemExit, match="base variant 'base' is not among"):
        RR.compute(rows("v"), {"all26": FIELDS}, "base")


def test_a_partial_shifted_control_is_refused_but_none_at_all_stays_missing():
    """Codex review of 2.62.10 (3rd): a variant whose shifted copy lacks a field must not be compared with a complete one on d_shift_any; a variant with no shifted copy gives NaN."""
    import math

    import pytest

    v = rows("v")
    v.loc[v.field == "deep_cosmos_3", ["shift_rows", "shift_false", "shift_any"]] = float("nan")
    with pytest.raises(SystemExit, match="shifted control of v .against base.: lacks deep_cosmos_3/AllWISE"):
        RR.compute(pd.concat([rows("base"), v], ignore_index=True), {"all26": FIELDS}, "base")
    none = rows("v")
    none[["shift_rows", "shift_false", "shift_any"]] = float("nan")
    _, d = RR.compute(pd.concat([rows("base"), none], ignore_index=True), {"all26": FIELDS}, "base")
    assert math.isnan(d.set_index("split").loc["all26", "d_shift_any"])


def test_the_variant_runners_make_their_directory_arguments_absolute_before_cd():
    """Codex review of 2.62.10 (3rd): `cd "$HERE"` would turn a relative FIELDS_ROOT / OUT_DIR given from the repository root into a path under this directory."""
    import re

    d = Path(__file__).resolve().parents[2] / "benchmark" / "association_truth"
    for f in sorted(d.glob("run_*.sh")):
        lines = [l.split("#")[0] for l in f.read_text().splitlines()]
        at = [i for i, l in enumerate(lines) if re.search(r'(^|;)\s*cd "\$HERE"', l)]
        if not at:
            continue
        head = " ".join(lines[: at[0] + 1])
        args = re.findall(r'\b([A-Z])=\$\(cd "\$(\d)" && pwd\)', head)
        assert args, f"{f.name}: the arguments are used relative after cd"
        assert not re.search(r'\b[A-Z]=\$\d\b', head), f"{f.name}: a directory argument is kept as given"

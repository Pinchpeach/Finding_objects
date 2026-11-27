"""Archive errors make a validation run DEGRADED instead of a number; the truth sample does not depend on row order (2.61.9)."""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

CLS = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("val_status_test", CLS / "validate_independent_truth_sets.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["val_status_test"] = mod
    spec.loader.exec_module(mod)
    return mod


V = _load()


def _row(i, cls="RR_LYRAE", collectors=None, predicted="RR_LYRAE", status="X"):
    logs = collectors if collectors is not None else [{"collector": "gaia_dr3_variability_vizier", "status": "ok", "rows": 3}]
    return {"truth_id": f"T{i}", "axis": "variability", "truth_class": cls, "predicted_class": predicted, "status": status, "raw_score": 0.9, "match": True,
            "family_match": True, "classified": True, "sep_arcsec": 0.1, "collectors": json.dumps(logs)}  # fmt: skip


def test_an_error_status_of_a_collector_is_an_archive_error():
    ok = [{"collector": "a", "status": "ok", "rows": 2}, {"collector": "b", "status": "empty", "rows": 0}]
    bad = ok + [{"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "404"}]
    assert V.archive_errors(json.dumps(ok)) == []
    assert V.archive_errors(json.dumps(bad)) == ["gaia_dr3"]
    assert V.archive_errors("not json") == ["unreadable collector log"]
    assert V.archive_errors(None) == []


def test_run_status_is_ok_only_without_archive_errors_or_crashes():
    rows = [_row(i) for i in range(5)]
    assert V.run_status(rows)["status"] == "OK"
    rows[2] = _row(2, collectors=[{"collector": "gaia_dr3", "status": "error", "rows": 0}], predicted="UNKNOWN", status="NO_EVIDENCE")
    st = V.run_status(rows)
    assert st["status"] == "DEGRADED" and st["archive_error_rows"] == 1 and st["errors_by_collector"] == {"gaia_dr3": 1}
    assert st["affected_classes"] == ["variability|RR_LYRAE"]
    crashed = [_row(0, predicted="ERROR")]
    assert V.run_status(crashed)["status"] == "DEGRADED" and V.run_status(crashed)["evaluation_error_rows"] == 1


def test_a_row_that_met_an_archive_error_is_evaluated_again_and_a_clean_second_answer_replaces_it():
    truth = pd.DataFrame([{"truth_id": f"T{i}", "truth_axis": "variability", "truth_class": "RR_LYRAE", "ra": 1.0, "dec": 2.0} for i in range(4)])
    rows = [_row(i) for i in range(4)]
    rows[1] = _row(1, collectors=[{"collector": "gaia_dr3", "status": "error", "rows": 0}], predicted="UNKNOWN", status="NO_EVIDENCE")
    calls = []

    def evaluate(rec, base, radius):
        calls.append(str(rec.truth_id))
        return _row(int(str(rec.truth_id)[1:]))

    out, repeated = V.retry_errors(rows, truth, 0.5, 2, 1, evaluate=evaluate)
    assert calls == ["T1"] and repeated == 1
    assert V.run_status(out)["status"] == "OK" and out[1]["predicted_class"] == "RR_LYRAE"
    # an archive that stays down is still DEGRADED after the retries (no endless loop)
    always_bad = lambda rec, base, radius: _row(1, collectors=[{"collector": "gaia_dr3", "status": "error", "rows": 0}])  # noqa: E731
    out2, repeated2 = V.retry_errors([_row(1, collectors=[{"collector": "gaia_dr3", "status": "error", "rows": 0}])], truth, 0.5, 2, 2, evaluate=always_bad)
    assert repeated2 == 2 and V.run_status(out2)["status"] == "DEGRADED"


def test_the_report_says_degraded_and_unfrozen(tmp_path):
    rows = pd.DataFrame([_row(i) for i in range(3)])
    st = {"status": "DEGRADED", "archive_error_rows": 2, "evaluation_error_rows": 0, "errors_by_collector": {"gaia_dr3": 2}, "affected_classes": ["variability|RR_LYRAE"], "truth_list_frozen": False, "truth_list_sha256": "ab" * 32}
    V.write_report(rows, tmp_path, st)
    md = (tmp_path / "INDEPENDENT_TRUTH_VALIDATION.md").read_text()
    assert "DEGRADED RUN" in md and "UNFROZEN truth list" in md
    V.write_report(rows, tmp_path / "ok", None)  # the old call still works
    assert "DEGRADED" not in (tmp_path / "ok" / "INDEPENDENT_TRUTH_VALIDATION.md").read_text()


def test_sample_truth_does_not_depend_on_the_order_of_the_file(tmp_path):
    df = pd.DataFrame({"truth_id": [f"ID{i:04d}" for i in range(500)], "ra": [float(i % 360) for i in range(500)], "dec": 1.0, "truth_axis": "variability", "truth_class": "RR_LYRAE"})
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    df.to_csv(a / "variables_truth.csv", index=False)
    df.sample(frac=1.0, random_state=5).to_csv(b / "variables_truth.csv", index=False)
    sa, sb = V.sample_truth(a, 250), V.sample_truth(b, 250)
    assert len(sa) == 250 and list(sa.truth_id) == list(sb.truth_id)


def _rows_with_coverage(n, classified):
    out = []
    for i in range(n):
        r = _row(i)
        r["classified"] = i < classified
        r["predicted_class"] = "RR_LYRAE" if i < classified else "UNKNOWN"
        out.append(r)
    return out


def test_a_class_that_lost_coverage_against_the_baseline_is_degraded_although_no_collector_raised():
    base = {"tolerance": 0.05, "classes": {"variability|RR_LYRAE": 0.93}}
    healthy = _rows_with_coverage(100, 93)
    outage = _rows_with_coverage(100, 47)  # an archive that answers with zero rows: no error, but half the objects fall to UNKNOWN
    assert V.run_status(healthy, base)["status"] == "OK" and V.run_status(healthy)["coverage_baseline"] is False
    st = V.run_status(outage, base)
    assert st["status"] == "DEGRADED" and st["archive_error_rows"] == 0
    assert st["coverage_drops"] == [{"class": "variability|RR_LYRAE", "baseline": 0.93, "observed": 0.47, "tolerance": 0.05}]
    assert V.run_status(_rows_with_coverage(100, 99), base)["status"] == "OK"  # a gain is not a problem
    assert V.run_status(outage)["status"] == "OK"  # no baseline recorded yet: only errors and crashes count


def test_the_baseline_is_written_from_a_run_and_read_back_by_the_next_one(tmp_path):
    import numpy as np  # noqa: F401  (kept out of the module header: the file must stay importable under unittest)

    spec = importlib.util.spec_from_file_location("agg_baseline_test", CLS / "aggregate_independent_truth.py")
    A = importlib.util.module_from_spec(spec)
    sys.modules["agg_baseline_test"] = A
    spec.loader.exec_module(A)
    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "x_truth.csv").write_text("truth_id,ra,dec,truth_axis,truth_class\nA,1,2,variability,RR_LYRAE\n")
    import hashlib

    sha = hashlib.sha256((truth / "x_truth.csv").read_bytes()).hexdigest()
    (truth / "truth_manifest.json").write_text(json.dumps({"sets": {"x": {"file": "x_truth.csv", "sha256": sha, "rows": 1, "status": "ok", "classes": {}}}}))
    sh = tmp_path / "shards" / "s"
    sh.mkdir(parents=True)
    pd.DataFrame(_rows_with_coverage(100, 93)).to_csv(sh / "independent_truth_predictions.csv", index=False)
    out = tmp_path / "out"
    first = A.aggregate(tmp_path / "shards", truth, out, True)
    assert first["status"] == "OK"
    rows = pd.read_csv(out / "independent_truth_predictions.csv")
    cov = V.coverage_by_class(rows)
    assert cov == {"variability|RR_LYRAE": 0.93}
    # as --write-baseline writes it: with the hash of the list it was measured on (a baseline of another list is not used)
    (tmp_path / "base.json").write_text(json.dumps({"tolerance": 0.05, "truth_list_sha256": first["truth_list_sha256"], "classes": cov}))
    assert A.aggregate(tmp_path / "shards", truth, tmp_path / "out2", True, baseline=tmp_path / "base.json")["status"] == "OK"
    pd.DataFrame(_rows_with_coverage(100, 40)).to_csv(sh / "independent_truth_predictions.csv", index=False)
    st = A.aggregate(tmp_path / "shards", truth, tmp_path / "out3", True, baseline=tmp_path / "base.json")
    assert st["status"] == "DEGRADED" and st["coverage_drops"][0]["observed"] == 0.4
    assert "coverage below the baseline" in (tmp_path / "out3" / "INDEPENDENT_TRUTH_VALIDATION.md").read_text()


def test_a_partial_answer_of_a_collector_is_an_archive_error(tmp_path, monkeypatch):
    """Codex review of 2.62.0: agb_suh2021 / asas_sn_supernova return the rows of the tables that answered and mark the failed one in
    ``*_query_status``; that row must be retried and make the run DEGRADED, not pass as ``ok``."""
    frame = pd.DataFrame({"ra": [1.0], "dec": [2.0], "agb_query_status": ["error:J/ApJS/256/43/table2"]})
    assert V.partial_failure(frame) == "error:J/ApJS/256/43/table2"
    assert V.partial_failure(pd.DataFrame({"ra": [1.0], "ps1_query_status": ["vizier_fallback"]})) == ""  # an alternative source is not a failure
    assert V.partial_failure(pd.DataFrame({"ra": [1.0]})) == ""

    class Fake:
        @staticmethod
        def fetch(ra, dec, radius, **kw):
            return frame

        @staticmethod
        def save(df, path):
            pass

    monkeypatch.setattr(V, "load_module", lambda path, name: Fake)
    row = pd.Series(dict(truth_axis="physical", truth_class="AGB", truth_id="A1", ra=1.0, dec=2.0))
    logs = V.collect(row, tmp_path, 2.0)
    agb = [e for e in logs if e["collector"] == "agb_suh2021"][0]
    assert agb["status"] == "error_partial" and agb["rows"] == 1
    st = V.run_status([_row(1, cls="AGB", collectors=logs)])
    assert st["status"] == "DEGRADED" and st["errors_by_collector"].get("agb_suh2021") == 1

"""The aggregate step of the cross validation as a script: OK / DEGRADED, the truth-list hash, the provenance of a refit (2.61.9)."""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

CLS = Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


A = _load(CLS / "aggregate_independent_truth.py", "agg_script_test")


def _truth_dir(tmp_path):
    d = tmp_path / "truth"
    d.mkdir()
    (d / "pn_truth.csv").write_text("truth_id,ra,dec,truth_axis,truth_class\nPN1,1.0,2.0,phenomenon,PN\nPN2,3.0,4.0,phenomenon,PN\n")
    import hashlib

    sha = hashlib.sha256((d / "pn_truth.csv").read_bytes()).hexdigest()
    ids = hashlib.sha256("\n".join(["PN1", "PN2"]).encode()).hexdigest()
    (d / "truth_manifest.json").write_text(json.dumps({"schema": 1, "sets": {"pn": {"file": "pn_truth.csv", "sha256": sha, "rows": 2, "status": "ok", "classes": {"phenomenon|PN": {"rows": 2, "ids_sha256": ids}}}}}))
    return d


def _shard(tmp_path, name, rows):
    d = tmp_path / "shards" / name
    d.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(d / "independent_truth_predictions.csv", index=False)


def _row(i, err=False):
    logs = [{"collector": "hash_pn", "status": "error" if err else "ok", "rows": 0 if err else 1}]
    return {"truth_id": f"PN{i}", "axis": "phenomenon", "truth_class": "PN", "predicted_class": "PN", "status": "HASH_PN_CATALOG_MATCH", "raw_score": 0.9, "match": True,
            "family_match": True, "classified": True, "sep_arcsec": 0.1, "collectors": json.dumps(logs)}  # fmt: skip


def test_an_ok_run_and_a_degraded_run(tmp_path):
    truth = _truth_dir(tmp_path)
    _shard(tmp_path, "pn", [_row(1), _row(2)])
    st = A.aggregate(tmp_path / "shards", truth, tmp_path / "out", frozen=True, source_commit="abc")
    assert st["status"] == "OK" and st["truth_list_frozen"] is True and len(st["truth_list_sha256"]) == 64 and st["source_commit"] == "abc"
    assert "DEGRADED" not in (tmp_path / "out" / "INDEPENDENT_TRUTH_VALIDATION.md").read_text()
    assert json.loads((tmp_path / "out" / "validation_status.json").read_text())["status"] == "OK"
    _shard(tmp_path, "pn2", [_row(3, err=True)])
    st2 = A.aggregate(tmp_path / "shards", truth, tmp_path / "out2", frozen=False)
    assert st2["status"] == "DEGRADED" and st2["archive_error_rows"] == 1
    md = (tmp_path / "out2" / "INDEPENDENT_TRUTH_VALIDATION.md").read_text()
    assert "DEGRADED RUN" in md and "UNFROZEN" in md


def test_the_provenance_of_a_refit_names_the_list_the_predictions_and_the_run(tmp_path):
    truth = _truth_dir(tmp_path)
    _shard(tmp_path, "pn", [_row(1)])
    st = A.aggregate(tmp_path / "shards", truth, tmp_path / "out", frozen=True, source_commit="abc")
    f = A.fitted_on(st, tmp_path / "out" / "independent_truth_predictions.csv", "4242")
    assert f["truth_list_sha256"] == st["truth_list_sha256"] and f["run_status"] == "OK" and f["run_id"] == "4242" and len(f["predictions_sha256"]) == 64

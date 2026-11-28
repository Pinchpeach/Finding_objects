#!/usr/bin/env python3
"""Merge the shards of the independent truth validation, decide OK / DEGRADED, write the report (2.61.9).

    python aggregate_independent_truth.py --shards DIR --truth-dir DIR --out DIR [--frozen true|false] [--fitted-on-out FILE]

Used by the ``aggregate`` job of ``v2_scientific_cross_validation.yml`` (it used to be a heredoc there, which nothing could test).  Reads every
``**/independent_truth_predictions.csv`` below ``--shards``, writes the predictions, the summary and the markdown report to ``--out`` and
``validation_status.json``: ``status`` OK or DEGRADED (a row met an archive error that the retry did not clear, or crashed), the SHA-256 of the truth list
(the manifest of ``--truth-dir``) and whether that list is the committed one; with ``--baseline`` a class whose classified share fell more than the tolerance below the
share measured on the frozen list also makes the run DEGRADED (``--write-baseline`` writes such a file from an OK run).  With ``--fitted-on-out`` it also writes the provenance JSON that
``calibration/fit_axis_calibration.py --fitted-on-json`` stamps into a refit.  Prints ``state=OK|DEGRADED`` (for ``$GITHUB_OUTPUT``).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pandas as pd

CLS = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def aggregate(shards: Path, truth_dir: Path, out: Path, frozen: bool, source_commit: str = "", baseline: Path | None = None) -> dict:
    files = sorted(shards.glob("**/independent_truth_predictions.csv"))
    if not files:
        raise SystemExit("no shard predictions")
    rows = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
    val = _load(CLS / "validate_independent_truth_sets.py", "agg_validate")
    bld = _load(CLS / "truth" / "build_independent_truth_sets.py", "agg_build")
    base = json.loads(baseline.read_text(encoding="utf-8")) if baseline and baseline.exists() else None
    list_sha = bld.list_sha256(truth_dir)
    mismatch = None
    if base is not None and base.get("truth_list_sha256") != list_sha:
        # a baseline measured on another truth list (left in truth/fixed/ after a refreeze) says nothing about this one: it is not used, as if
        # there were none, and the status names it so that a new baseline is committed (Codex review of 2.62.0)
        mismatch = {"baseline_truth_list_sha256": base.get("truth_list_sha256"), "truth_list_sha256": list_sha}
        base = None
    status = val.run_status(rows, base)
    status["baseline_mismatch"] = mismatch
    status["truth_list_sha256"] = list_sha
    status["truth_list_frozen"] = bool(frozen)
    status["source_commit"] = source_commit
    out.mkdir(parents=True, exist_ok=True)
    val.write_report(rows, out, status)
    times = val.collector_times(rows)  # per class and collector, from the seconds in the logs (2.62.12); none for logs written before
    if len(times):
        times.to_csv(out / "collector_times.csv", index=False)
    (out / "validation_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def fitted_on(status: dict, predictions: Path, run_id: str = "") -> dict:
    return {
        "truth_list_sha256": status["truth_list_sha256"],
        "truth_list_frozen": status["truth_list_frozen"],
        "predictions_sha256": hashlib.sha256(predictions.read_bytes()).hexdigest(),
        "run_status": status["status"],
        "source_commit": status.get("source_commit", ""),
        "run_id": run_id,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shards", type=Path, required=True)
    ap.add_argument("--truth-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frozen", default="false")
    ap.add_argument("--fitted-on-out", type=Path)
    ap.add_argument("--baseline", type=Path, help="truth/fixed/baseline_coverage.json: classified share per class measured once on the frozen list")
    ap.add_argument("--write-baseline", type=Path, help="write this run's classified shares as a baseline candidate (commit it by hand after an OK run on the frozen list)")
    a = ap.parse_args()
    status = aggregate(a.shards, a.truth_dir, a.out, a.frozen.lower() == "true", os.environ.get("GITHUB_SHA", ""), a.baseline)
    if a.write_baseline:
        val = _load(CLS / "validate_independent_truth_sets.py", "agg_validate")
        rows = pd.read_csv(a.out / "independent_truth_predictions.csv")
        a.write_baseline.write_text(json.dumps({"tolerance": val.COVERAGE_TOLERANCE, "truth_list_sha256": status["truth_list_sha256"], "run_status": status["status"],
                                                "source_commit": status["source_commit"], "classes": val.coverage_by_class(rows)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if a.fitted_on_out:
        a.fitted_on_out.write_text(json.dumps(fitted_on(status, a.out / "independent_truth_predictions.csv", os.environ.get("GITHUB_RUN_ID", "")), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"state={status['status']}")
    print(json.dumps(status, indent=2, sort_keys=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

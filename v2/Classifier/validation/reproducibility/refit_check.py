#!/usr/bin/env python3
"""Is ``models.json`` a deterministic function of the committed predictions?  (2.61.9)

    python refit_check.py --out refit_check.csv [--commits 8daf15d e19159e ...]

For every listed commit of the cross-validation bot: take its ``independent_truth_predictions.csv`` and its ``models.json``, refit on top of that
``models.json`` (``calibration/fit_axis_calibration.py`` keeps the rules measured by other jobs, which is why the refit runs on a copy of the file) and compare every
number.  ``identical`` = the refit reproduces the committed file.  If it does, a change of the coefficients between two bot commits is a change of the predictions
(of the truth list or of an archive), not of the fit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
MODELS = "v2/Classifier/calibration/models.json"
PRED = "v2/Classifier/validation/independent_truth/independent_truth_predictions.csv"
DEFAULT = ["8daf15d", "e19159e", "411ba89", "13be466", "f1f38dd", "766db6d", "e6d079a", "cf4ad77"]


def show(commit: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=REPO, check=True, capture_output=True, text=True).stdout


def flat(d, p=""):
    out = {}
    for k, v in d.items():
        out.update(flat(v, p + k + "/") if isinstance(v, dict) else {p + k: v})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--commits", nargs="*", default=DEFAULT)
    a = ap.parse_args()
    rows = []
    for c in a.commits:
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "pred.csv").write_text(show(c, PRED), encoding="utf-8")
            (t / "models.json").write_text(show(c, MODELS), encoding="utf-8")
            subprocess.run(["python", str(REPO / "v2/Classifier/calibration/fit_axis_calibration.py"), "--input", str(t / "pred.csv"), "--out", str(t / "models.json")],
                           check=True, capture_output=True)  # fmt: skip
            old, new = flat(json.loads(show(c, MODELS))), flat(json.loads((t / "models.json").read_text()))
        diff = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k) and not (isinstance(old.get(k), float) and isinstance(new.get(k), float) and abs(old[k] - new[k]) < 1e-9))
        rows.append(dict(commit=c, identical=not diff, differing_keys=";".join(diff[:5])))
    t = pd.DataFrame(rows)
    t.to_csv(a.out, index=False)
    print(t.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

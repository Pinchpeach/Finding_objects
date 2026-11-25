#!/usr/bin/env python3
"""A monotone recalibration of the association posterior, fitted on the calibration half, scored on the test half (2.60.11).

    python isotonic_check.py --rows rows_base.csv.gz --out DIR

The table ``results_2026-11-25/isotonic_check_test_half.csv`` of the 2.60.8 report was made by hand; this makes it.
Rows are the joined low-resolution rows with a known truth outcome (correct / false), as in ``posterior_calibration.py``
(conditional on a counterpart in the truth), the score is ``L / (1 + L)`` (the pipeline's match-time posterior).  Per
catalogue an isotonic regression (``sklearn.isotonic.IsotonicRegression``, clipped to [0, 1]) is fitted on the calibration
half and applied to the test half; the Brier score, the expected calibration error and the sum of the scores against the
number of correct associations (Budavari & Szalay 2008: sum P = N*) are printed for both versions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.isotonic import IsotonicRegression

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_association as M  # noqa: E402
import posterior_calibration as P  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    split = pd.read_csv(HERE / "fields_split.csv").set_index("name").split
    d = pd.read_csv(a.rows)
    d["split"] = d.field.map(split)
    k = d[d.joined & d.outcome.isin(["correct", "false"]) & d.lr.notna()].copy()
    k["y"] = (k.outcome == "correct").astype(float)
    k["current"] = k.lr / (1.0 + k.lr)
    rows = []
    for cat in M.LOWRES:
        tr, te = k[(k.catalog == cat) & (k.split == "calibration")], k[(k.catalog == cat) & (k.split == "test")]
        if len(tr) < 30 or len(te) < 30:
            continue
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(tr.current, tr.y)
        for name, p in (("current", te.current.to_numpy()), ("isotonic(calibration half)", iso.predict(te.current))):
            rows.append(dict(catalog=cat, score=name, **P.summarise(p, te.y.to_numpy())))
    r = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out / "isotonic_check_test_half.csv", index=False)
    print(r.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

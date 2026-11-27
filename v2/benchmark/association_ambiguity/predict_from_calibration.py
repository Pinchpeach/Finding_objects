#!/usr/bin/env python3
"""What each ambiguity rule should do, computed from the calibration fields only, before any variant is run (2.61.7).

    python predict_from_calibration.py --cand DIR_CANDIDATE_TRUTH_CAL --out OUT

``candidate_truth.py`` was run on the calibration COSMOS fields (deep_cosmos_1..9) with the baseline Stage 1 (``V2_ASSOC_DIAG=1``).  For each rule
(``same``: the anchors of the two best candidates are closer than 0.3'', then the best candidate; ``nearest``: nearest < 0.3'' and the next at
least 3 times further, then the nearest; ``best``: the best candidate always) the rows it would join are counted by what the join would be
against COSMOS2020: right (the object holds the row's truth source), wrong (it holds others), unknown (no truth id).  Nothing here looks at a
confirmation field.  The counts are predictions of the number of joins, not of the end metrics (a join can also pull a later row in).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

SAME, NEAR_SEP, NEAR_RATIO = 0.3, 0.3, 3.0
GROUPS = {"resolving": ["DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject", "SDSS DR18 PhotoObj", "Gaia DR3", "SGA-2020"],
          "AllWISE": ["AllWISE"], "GALEX AIS": ["GALEX AIS"], "2MASS PSC": ["2MASS PSC"]}  # fmt: skip


def apply_rule(d: pd.DataFrame, rule: str) -> pd.DataFrame:
    same = d.c12_sep < SAME
    near = (d.sep1 < NEAR_SEP) & (d.sep2 >= NEAR_RATIO * d.sep1.clip(lower=1e-3))
    out = d.copy()
    if rule == "same":
        out["joined"], out["verdict"] = same, d.best_score
    elif rule == "nearest":
        out["joined"], out["verdict"] = near, d.nearest
    elif rule == "same+nearest":
        out["joined"] = same | near
        out["verdict"] = d.best_score.where(same, d.nearest)
    elif rule == "best":
        out["joined"], out["verdict"] = True, d.best_score
    return out[out.joined]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cand", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = pd.read_csv(a.cand / "candidate_truth_rows.csv.gz")
    rows = []
    for rule in ("same", "nearest", "same+nearest", "best"):
        j = apply_rule(d, rule)
        for g, cats in GROUPS.items():
            x = j[j.catalog.isin(cats)]
            tot = int(d.catalog.isin(cats).sum())
            rows.append(dict(rule=rule, group=g, ambiguous_rows=tot, joined=len(x), joined_with_truth=int(x.has_truth.sum()),
                             right=int((x.verdict == "right").sum()), wrong=int((x.verdict == "wrong").sum()), unknown=int((x.verdict == "unknown").sum())))  # fmt: skip
    t = pd.DataFrame(rows)
    t["joined_pct"] = (100 * t.joined / t.ambiguous_rows.where(t.ambiguous_rows > 0)).round(1)
    t["wrong_pct_of_known"] = (100 * t.wrong / (t.right + t.wrong).where((t.right + t.wrong) > 0)).round(1)
    a.out.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out / "predicted_joins_calibration.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(t.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

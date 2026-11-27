#!/usr/bin/env python3
"""Of the COSMOS2020 association misses (2.60.9 definition), how many went through ``ambiguous_new`` (2.61.7).

    python missed_by_path.py --rows rows_base.csv.gz --out OUT

``rows_<variant>.csv.gz`` is the per-row table of ``association_truth/measure_association.py``.  A low-resolution row (AllWISE, 2MASS,
GALEX) that is not joined is *missed* when another object holds a source of its acceptable set; its ``status`` says whether it left
the group because no candidate was accepted (``new``) or because a second candidate scored at least 0.67 of the first (``ambiguous_new``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = pd.read_csv(a.rows, low_memory=False)
    d = d[d.outcome.isin(["correct", "false", "unknown", "missed", "rightly_alone"])]
    rows = []
    for cat, g in d.groupby("catalog"):
        amb = g[g.status == "ambiguous_new"]
        missed = g[g.outcome == "missed"]
        rows.append(dict(catalog=cat, rows_with_expected_counterpart=len(g), missed=len(missed), missed_via_ambiguous=int((missed.status == "ambiguous_new").sum()),
                         missed_via_new=int((missed.status == "new").sum()), ambiguous_new=len(amb), ambiguous_that_were_missed=int((amb.outcome == "missed").sum()),
                         ambiguous_rightly_alone=int((amb.outcome == "rightly_alone").sum())))  # fmt: skip
    t = pd.DataFrame(rows)
    t["missed_via_ambiguous_pct"] = (100 * t.missed_via_ambiguous / t.missed).round(1)
    t["ambiguous_missed_pct"] = (100 * t.ambiguous_that_were_missed / t.ambiguous_new).round(1)
    a.out.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out / "missed_by_path.csv", index=False)
    print(t.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

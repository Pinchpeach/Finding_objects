#!/usr/bin/env python3
"""Two label tables of ``regroup.py`` compared three ways: fixed and broken truth labels of a variant against its base (2.62.6).

    python rescore_labels.py --pairs NAME=BASE.csv.gz:VARIANT.csv.gz [...] --out OUT.csv [--fields-split fields_split.csv]

A truth source (COSMOS2020, STAR / GALAXY, F814W < 24.5) gets, in every ``regroup_labels_<variant>.csv.gz``, three readings:

  pick     the class of the ONE object with the most catalogues within 1.5'' (the tool of 2.60.8-2.61.0: ``score_accuracy`` as it was)
  exists   an object within 0.5'' has the truth class (the order of 2026-11-28, task d)
  every    objects exist within 0.5'' and all of them have the truth class
  exists_both_near   ``exists`` restricted to the truth sources that have an object within 0.5'' in BOTH runs: the change of the CLASS of what is there, not of whether an
           object moved into or out of the 0.5'' ring (an association change moves anchors: 105 of the 108 truth sources that lost their right-class object within 0.5''
           between the old and the new row order had no object within 0.5'' any more, not an object of the wrong class)

A rule that removes fragments (``hc``, ``m15hc``) or a new row order changes WHICH object is the pick: when the pick was a fragment of the wrong class and is now
grouped under a right parent, ``pick`` counts a fixed label although no object of the right class is new.  ``exists`` does not see that.  For each pair the table
has, per half (calibration / test / all) and reading: truth sources (``exists_both_near``: those with an object within 0.5'' in both), correct in the base, correct in the variant, only the base right
(``broken``), only the variant right (``fixed``), the exact two-sided McNemar p, and the truth sources that gained or lost every object within 0.5''.
"""

from __future__ import annotations

import argparse
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
KEY = ["field", "ra", "dec"]
sys.path.insert(0, str(HERE.parent))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def mcnemar(n_base_only: int, n_variant_only: int) -> float:
    n = n_base_only + n_variant_only
    return min(1.0, 2 * sum(comb(n, k) for k in range(0, min(n_base_only, n_variant_only) + 1)) / 2**n) if n else 1.0


def readings(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["pick"] = t.pred.notna() & (t.pred == t.truth)
    t["has_pick"] = t.pred.notna()
    t["exists"] = t.exists_near.astype(bool) if "exists_near" in t else np.nan
    t["every"] = t.all_near.astype(bool) if "all_near" in t else np.nan
    t["near_any"] = t.n_near.gt(0) if "n_near" in t else np.nan
    return t


def compare(base: pd.DataFrame, var: pd.DataFrame, split: pd.Series) -> list[dict]:
    m = readings(base).merge(readings(var), on=KEY, suffixes=("_b", "_v"))
    m["split"] = m.field.map(split)
    rows = []
    for half, whole in (("calibration", m[m.split == "calibration"]), ("test", m[m.split == "test"]), ("all", m)):
        for kind in ("pick", "exists", "every", "exists_both_near"):
            sub = whole
            col = kind
            if kind == "exists_both_near":
                col = "exists"
                if "near_any_b" not in whole or whole.near_any_b.isna().all():
                    continue
                sub = whole[whole.near_any_b.astype(bool) & whole.near_any_v.astype(bool)]
            if f"{col}_b" not in sub or sub[f"{col}_b"].isna().all():
                continue
            b, v = sub[f"{col}_b"].astype(bool), sub[f"{col}_v"].astype(bool)
            nb, nv = int((b & ~v).sum()), int((~b & v).sum())
            rows.append(dict(half=half, reading=kind, truth_sources=len(sub), correct_base=int(b.sum()), correct_variant=int(v.sum()), broken=nb, fixed=nv,
                             net=nv - nb, mcnemar_p=round(mcnemar(nb, nv), 4), labels_changed=int((sub.pred_b.fillna("") != sub.pred_v.fillna("")).sum()) if kind == "pick" else np.nan,
                             lost_every_object_within_0p5=int((whole.near_any_b & ~whole.near_any_v).sum()) if kind == "exists" else np.nan,
                             gained_object_within_0p5=int((~whole.near_any_b & whole.near_any_v).sum()) if kind == "exists" else np.nan))  # fmt: skip
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", nargs="+", required=True, help="NAME=BASE.csv.gz:VARIANT.csv.gz")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields-split", type=Path, default=HERE / "fields_split.csv")
    a = ap.parse_args()
    t0 = RI.start()
    split = pd.read_csv(a.fields_split).set_index("name").split
    rows = []
    for spec in a.pairs:
        name, files = spec.split("=", 1)
        fb, fv = files.split(":", 1)
        for r in compare(pd.read_csv(fb), pd.read_csv(fv), split):
            rows.append(dict(comparison=name, **r))
    d = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(d[d.half != "all"].drop(columns=["lost_every_object_within_0p5", "gained_object_within_0p5"]).to_string(index=False))
    RI.write(a.out, [*[f for s in a.pairs for f in s.split("=", 1)[1].split(":")]], t0=t0, note="rescore_labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The loss of faint real quasars at low latitude, estimated from the deep COSMOS fields and the survey counts of the plane (2.61.5).

    python reweight.py --cosmos DIR_FAINT_COST --dist DIR_SURVEY_DISTRIBUTION --out OUT

The deep COSMOS fields (|b| = 42 deg, every survey there) tell, for Chandra type 1 AGN, how likely the base labels a quasar QSO given
its number of surveys k and its Pan-STARRS1 i bin: ``q(k, i)`` (``faint_cost.py``: ``type1_ps1_i_by_surveys.csv``).  The survey
counts of the objects of the low-latitude regions (``survey_distribution.py``) give how many surveys an object of that i bin has there,
``c(k | i, cones)``, separately for cones with and without Legacy Surveys.  A switch that needs ``need`` surveys withholds the labels of
the objects with k < need, so for the quasars the base labels QSO

    lost(i, cones) = sum_{k < need} c(k | i) q(k, i)  /  sum_k c(k | i) q(k, i).

Assumptions (the table is an estimate, not a measurement): a real quasar of a given i has the survey count of an average object of that
i in those cones (quasars are brighter in WISE than the average object, so this is on the pessimistic side), and q(k, i) of COSMOS holds
at low latitude (extinction and crowding make the quasars there fainter and the labels rarer).  q is pooled over i where a bin has fewer than
``MIN_N`` type 1 AGN: ``q(k)`` of the bright (i < 21) or the faint (i >= 21) half.  The overall figure weights the i bins by the number of
base-labelled type 1 AGN of COSMOS in each (i < 22 and ``no PS1``: the range the plane's PS1 reaches).  COSMOS labels no type 1 AGN
with 1 or 2 surveys (q = 0 there; ``q_cosmos.csv`` has its 95 % Wilson upper limit ``q_upper95``), so the estimate is 0 for both
switches: the switches cannot remove a correct label that the base does not give.  ``share_ge_need`` is the other number that matters,
the ceiling: the share of the objects of that i bin (all objects of the cones) that has enough surveys to be labelled QSO at all.
"""

from __future__ import annotations

import sys

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

MIN_N = 8
SURVEY_COLS = {"1": "surveys_1", "2": "surveys_2", "3": "surveys_3", "4+": "surveys_4plus"}
ORDER = ["<19", "19-20", "20-21", "21-22", ">=22", "no PS1"]
HALF = {"<19": "bright", "19-20": "bright", "20-21": "bright", "21-22": "faint", ">=22": "faint", "no PS1": "faint"}


def wilson_hi(k: int, n: int, z: float = 1.959964) -> float:
    if n == 0:
        return 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    return min(1.0, (c + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d)


def q_table(cross: pd.DataFrame) -> pd.DataFrame:
    """q(k, i) = P(base labels QSO | type 1, k surveys, i bin), pooled over the half where the bin has too few objects."""
    c = cross.copy()
    c["half"] = c.ps1_i.map(HALF)
    pooled = c.groupby(["half", "surveys"])[["n_type1", "base_labels_qso"]].sum()
    rows = []
    for r in c.itertuples():
        n, k = r.n_type1, r.base_labels_qso
        pn, pk = pooled.loc[(r.half, r.surveys)]
        use_pool = n < MIN_N
        rows.append(dict(ps1_i=r.ps1_i, surveys=r.surveys, n_type1=n, base_labels_qso=k, pooled=use_pool,
                         q=(pk / pn if pn else 0.0) if use_pool else k / n,
                         q_upper95=wilson_hi(int(pk), int(pn)) if use_pool else wilson_hi(int(k), int(n))))  # fmt: skip
    return pd.DataFrame(rows)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cosmos", type=Path, required=True)
    ap.add_argument("--dist", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    cross = pd.read_csv(a.cosmos / "type1_ps1_i_by_surveys.csv")
    q = q_table(cross)
    q.to_csv(a.out / "q_cosmos.csv", index=False)
    dist = pd.read_csv(a.dist / "survey_distribution.csv")
    dist = dist[dist.population == "all objects"]
    w_bin = cross.groupby("ps1_i").base_labels_qso.sum()  # COSMOS weight of each i bin (base-labelled type 1 AGN)
    rows = []
    for cones in ("all", "LS cones", "no-LS cones"):
        d = dist[dist.cones == cones].set_index("ps1_i")
        for need in (2, 3):
            tot_lost = tot_all = 0.0
            for b in ORDER:
                if b not in d.index:
                    continue
                num = den = 0.0
                qt = q[q.ps1_i == b].set_index("surveys")
                for nm, col in SURVEY_COLS.items():
                    c = float(d.loc[b, col])
                    k = 4 if nm == "4+" else int(nm)
                    num += c * qt.q[nm] * (k < need)
                    den += c * qt.q[nm]
                lost = num / den if den else math.nan
                rows.append(dict(cones=cones, switch=f"surveys{need}", ps1_i=b, objects=int(d.loc[b, "objects"]),
                                 share_ge_need=float(d.loc[b, "share_ge2" if need == 2 else "share_ge3"]),
                                 estimated_lost_share=round(lost, 4) if den else math.nan))  # fmt: skip
                if b != ">=22" and den:
                    wgt = float(w_bin.get(b, 0))
                    tot_lost += wgt * lost
                    tot_all += wgt
            rows.append(dict(cones=cones, switch=f"surveys{need}", ps1_i="weighted (i<22 and no PS1)", objects=int(d.objects.sum()),
                             share_ge_need=math.nan, estimated_lost_share=round(tot_lost / tot_all, 4) if tot_all else math.nan))  # fmt: skip
    r = pd.DataFrame(rows)
    r.to_csv(a.out / "estimated_loss.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(r.to_string(index=False))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Position-error model and simultaneous assignment: measurements only (2.60.9, task 4 step 4).

    python error_model_and_assignment.py --rows rows_diag.csv.gz --out DIR

Two questions, answered from the per-row table of ``measure_association.py`` (COSMOS2020 truth, 26 deep fields).

1. Error model.  The stage's effective error of a row is ``max(poserr, PSF/6)`` (PSF/6 = 1.02'' AllWISE, 0.42'' 2MASS,
   0.88'' GALEX) combined with the anchor's.  Where do the rows really lie relative to the truth source that dominates
   their flux?  Taking rows whose acceptable set is a single source (``n_acc == 1``: no blend), the offset to that source
   is compared with a Rayleigh distribution of scale sigma_model: its median, 68, 90, 95, 99 % points against
   1.177, 1.515, 2.146, 2.448, 3.035 sigma, and the share of rows farther than 1.75 / 2.5 / 3 sigma.  The Rayleigh
   scale of the core (median / 1.177) and the tail share beyond 3 sigma_core are what a two-component model (Gaussian core
   + blend tail, Wilson & Naylor 2017, 2018a) would need.  The truth position error (~0.1'') is added in quadrature.
2. Simultaneous assignment.  The stage places detections one at a time and a group takes one row per catalogue.  Of the
   unjoined rows whose counterpart has an object, how many are blocked by a row of the same catalogue already in that
   object, and in how many of those is the blocked row the closer one to the truth source (a greedy-order error that a
   one-to-one assignment of the island, Budavari & Basu 2016, would turn around)?
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PSF = {"AllWISE": 6.1, "2MASS PSC": 2.5, "GALEX AIS": 5.3}
RAYLEIGH = {"p50": 1.1774, "p68": 1.5174, "p90": 2.1460, "p95": 2.4477, "p99": 3.0349}
TRUTH_SIGMA = 0.1


def error_model(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    split = pd.read_csv(HERE / "fields_split.csv").set_index("name").split
    d = d.assign(split=d.field.map(split))
    for cat, psf in PSF.items():
        for kind, mask in (("isolated", d.n_acc == 1), ("blend", d.n_acc > 1)):
            x = d[(d.catalog == cat) & mask & d.sep_dom.notna()]
            if len(x) < 30:
                continue
            sig = np.hypot(np.maximum(x.poserr.fillna(0.5), psf / 6.0), TRUTH_SIGMA)
            rec = dict(catalog=cat, kind=kind, n=len(x), sigma_model_median=round(float(sig.median()), 3))
            q = x.sep_dom.quantile([0.5, 0.68, 0.9, 0.95, 0.99]).to_numpy()
            for (k, r), v in zip(RAYLEIGH.items(), q):
                rec[k + "_arcsec"] = round(float(v), 2)
                rec[k + "_over_model"] = round(float(v / (r * sig.median())), 2)  # 1 = the model's Rayleigh point
            core = float(x.sep_dom.median() / 1.1774)
            rec["core_sigma_arcsec"] = round(core, 3)
            rec["core_over_model"] = round(core / float(sig.median()), 2)
            for k in (1.75, 2.5, 3.0):
                rec[f"beyond_{k}sigma_model_pct"] = round(100 * float((x.sep_dom > k * sig).mean()), 2)
            rec["beyond_3sigma_core_pct"] = round(100 * float((x.sep_dom > 3 * core).mean()), 2)
            rec["rayleigh_expected_beyond_3sigma_pct"] = 1.1
            out.append(rec)
    return pd.DataFrame(out)


def assignment(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    split = pd.read_csv(HERE / "fields_split.csv").set_index("name").split
    d = d.assign(split=d.field.map(split))
    for cat in PSF:
        for half in ("calibration", "test", "all"):
            x = d[(d.catalog == cat) & ((d.split == half) | (half == "all"))]
            if x.empty:
                continue
            miss = x[(~x.joined) & x.any_holder & x.outcome.isin(["missed", "rightly_alone"])]
            miss = miss[miss.outcome == "missed"]
            blocked = miss[miss.blocked]
            closer = blocked[blocked.sep_dom < blocked.blocker_sep]
            amb = miss[miss.status.eq("ambiguous_new")]
            new0 = miss[miss.status.eq("new") & ~miss.blocked]
            out.append(dict(catalog=cat, half=half, rows=len(x), joined=int(x.joined.sum()), missed=len(miss),
                            missed_ambiguous=len(amb), missed_blocked=len(blocked), blocked_row_closer_to_truth=len(closer),
                            blocked_closer_pct_of_missed=round(100 * len(closer) / max(len(miss), 1), 2),
                            missed_no_candidate=len(new0),
                            missed_pct_of_rows=round(100 * len(miss) / max(len(x), 1), 2)))  # fmt: skip
    return pd.DataFrame(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(a.rows)
    e, s = error_model(d), assignment(d)
    e.to_csv(a.out / "error_model.csv", index=False)
    s.to_csv(a.out / "assignment_blocking.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(e.to_string(index=False))
        print(s.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

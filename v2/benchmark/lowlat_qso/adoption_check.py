#!/usr/bin/env python3
"""The pre-registered predictions and adoption criteria of PREDICTIONS_CONFIRM.md, checked against the confirmation regions (2.61.2).

    python adoption_check.py --calibration DIR_CAL --confirmation DIR_CONF --highlat-identical yes --out DIR

``DIR_*`` hold ``ab_variants.csv`` and ``ab_variants_by_stratum.csv`` of ``ab_variants.py``.  The numbers below are copied from
PREDICTIONS_CONFIRM.md, which was committed before the first confirmation region was collected (commit 8b108c2); a prediction
that fails is printed as failed.  Writes ``predictions.csv`` (one row per prediction: predicted, observed, holds), ``adoption.csv``
(one row per candidate: criteria a-c) and ``exchange.csv`` (calibration and confirmation side by side: recall lost against false
density removed).

Adoption criteria (for the candidate to be offered as an option; the default stays off):
  (a) the 95 % region-bootstrap interval of the paired false-QSO density it removes is above 0,
  (b) it loses at most 3 of the sample quasars of the confirmation regions,
  (c) the labels at |b| >= 20 deg are identical (--highlat-identical, checked separately on the deep COSMOS fields and the others).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

CANDIDATES = ["surveys2", "surveys3", "pm", "wise_second", "surveys2_wise_second_wise_footprint"]
# prediction 1: recall by |b| stratum of the calibration regions and the overall interval stated in advance
PRED_RECALL = {"b5-10": 0.46, "b10-15": 0.78, "b15-20": 0.75}
PRED_RECALL_ALL = (0.55, 0.70)
PRED_FALSE_BASE = (90.0, 250.0)  # per deg^2, the interval stated around 156
PRED_SINGLE_SURVEY_SHARE = (0.35, 0.55)
PRED_REMOVED_SHARE = {"surveys2": (0.30, 0.60), "surveys3": (0.60, 0.85), "wise_second": (0.08, 0.25)}
PRED_LOST_MAX = {"surveys2": 2, "surveys3": 3, "pm": 2, "wise_second": 0}
HIGH_LAT_QSO_DENSITY = 8.0  # deg^-2, upper end of the 5-8 deg^-2 expected at high latitude (LOWLAT_QSO.md)


def load(d: Path):
    v = pd.read_csv(d / "ab_variants.csv").set_index("variant")
    v = v.rename(index={"surveys2_wise_second": "surveys2_wise_second_wise_footprint"})  # the name used in the calibration run
    s = pd.read_csv(d / "ab_variants_by_stratum.csv")
    return v, s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", type=Path, required=True)
    ap.add_argument("--confirmation", type=Path, required=True)
    ap.add_argument("--highlat-identical", choices=["yes", "no"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cal, cal_s = load(a.calibration)
    con, con_s = load(a.confirmation)
    base = con.loc["base"]
    rows = []

    def add(pid, what, predicted, observed, holds):
        rows.append(dict(id=pid, what=what, predicted=predicted, observed=observed, holds="yes" if holds else "NO"))

    # 1  base recall
    bs = con_s[con_s.variant == "base"].set_index("stratum")
    for st, p in PRED_RECALL.items():
        if st in bs.index:
            r = bs.loc[st]
            add("1", f"base recall {st}", f"{p:.0%}", f"{r.recall:.1%} ({int(r.qso)}/{int(r.n)}; 95 % {r.lo:.0%}-{r.hi:.0%})", r.lo <= p <= r.hi)
    add("1", "base recall overall", f"{PRED_RECALL_ALL[0]:.0%}-{PRED_RECALL_ALL[1]:.0%}",
        f"{base.recall:.1%} ({int(base.recall_qso)}/{int(base.quasars)}; 95 % {base.recall_lo:.0%}-{base.recall_hi:.0%})",
        PRED_RECALL_ALL[0] <= base.recall <= PRED_RECALL_ALL[1])  # fmt: skip
    # 2  base false density, share on a single survey
    add("2", "base false QSO density (per deg^2)", f"156 ({PRED_FALSE_BASE[0]:.0f}-{PRED_FALSE_BASE[1]:.0f})",
        f"{base.false_all_per_deg2:.1f} (bootstrap {base.false_all_lo:.0f}-{base.false_all_hi:.0f}; n = {int(base.false_all_n)})",
        PRED_FALSE_BASE[0] <= base.false_all_per_deg2 <= PRED_FALSE_BASE[1])  # fmt: skip
    single = 1.0 - base.false_multi_survey_n / base.false_all_n if base.false_all_n else float("nan")
    add("2", "share of false labels on one survey", f"45 % ({PRED_SINGLE_SURVEY_SHARE[0]:.0%}-{PRED_SINGLE_SURVEY_SHARE[1]:.0%})", f"{single:.1%}",
        PRED_SINGLE_SURVEY_SHARE[0] <= single <= PRED_SINGLE_SURVEY_SHARE[1])  # fmt: skip
    # 3-6  the candidates
    for name in ("surveys2", "surveys3", "pm", "wise_second"):
        if name not in con.index:
            continue
        c = con.loc[name]
        n = {"surveys2": "3", "surveys3": "4", "pm": "5", "wise_second": "6"}[name]
        add(n, f"{name}: sample quasars lost (of {int(c.quasars)})", f"<= {PRED_LOST_MAX[name]}", f"{int(c.quasars_lost_vs_control)}", c.quasars_lost_vs_control <= PRED_LOST_MAX[name])
        share = c.false_removed_vs_control / base.false_all_n if base.false_all_n else float("nan")
        if name in PRED_REMOVED_SHARE:
            lo, hi = PRED_REMOVED_SHARE[name]
            add(n, f"{name}: share of false labels removed", f"{lo:.0%}-{hi:.0%}",
                f"{share:.1%} ({int(c.false_removed_vs_control)} of {int(base.false_all_n)}; paired {c.removed_per_deg2:.1f} deg^-2, {c.removed_lo:.1f}-{c.removed_hi:.1f})",
                lo <= share <= hi)  # fmt: skip
        else:
            add(n, f"{name}: labels changed", "<= 2", f"{int(c.false_removed_vs_control + c.false_added_vs_control)} false, {int(c.quasars_lost_vs_control)} quasars",
                c.false_removed_vs_control + c.false_added_vs_control + c.quasars_lost_vs_control <= 2)  # fmt: skip
    # 7  the bright false labels stay above the high-latitude quasar density
    for name in ("base", "surveys2", "surveys3", "wise_second", "surveys2_wise_second_wise_footprint"):
        if name in con.index:
            c = con.loc[name]
            add("7", f"{name}: false labels with PS1 i < 19.5 (per deg^2)", f"> {HIGH_LAT_QSO_DENSITY:.0f}" + (" (about 10)" if name == "surveys3" else ""),
                f"{c.false_i_lt_195_per_deg2:.1f} (n = {int(c.false_i_lt_195_n)})", c.false_i_lt_195_per_deg2 > HIGH_LAT_QSO_DENSITY)  # fmt: skip
    # 8  high latitude
    add("8", "all switches inert at |b| >= 20 deg", "identical", "identical" if a.highlat_identical == "yes" else "DIFFERENT", a.highlat_identical == "yes")
    pred = pd.DataFrame(rows)
    pred.to_csv(a.out / "predictions.csv", index=False)

    adopt = []
    for name in CANDIDATES:
        if name not in con.index:
            continue
        c = con.loc[name]
        ca = (c.removed_lo > 0) if "removed_lo" in c and pd.notna(c.get("removed_lo")) else False
        cb = c.quasars_lost_vs_control <= 3
        cc = a.highlat_identical == "yes"
        adopt.append(dict(candidate=name, quasars_lost=int(c.quasars_lost_vs_control), removed_per_deg2=c.get("removed_per_deg2"),
                          removed_lo=c.get("removed_lo"), removed_hi=c.get("removed_hi"), a_interval_above_0="yes" if ca else "NO",
                          b_lost_at_most_3="yes" if cb else "NO", c_highlat_identical="yes" if cc else "NO",
                          adopted_as_option="yes" if (ca and cb and cc) else "NO"))  # fmt: skip
    pd.DataFrame(adopt).to_csv(a.out / "adoption.csv", index=False)

    ex = []
    for name in ["base"] + CANDIDATES:
        for lab, t in (("calibration", cal), ("confirmation", con)):
            if name not in t.index:
                continue
            c = t.loc[name]
            ex.append(dict(variant=name, set=lab, quasars=int(c.quasars), labelled_qso=int(c.recall_qso), recall=c.recall, recall_lo=c.recall_lo,
                           recall_hi=c.recall_hi, false_per_deg2=c.false_all_per_deg2, false_lo=c.false_all_lo, false_hi=c.false_all_hi,
                           false_i_lt_195_per_deg2=c.false_i_lt_195_per_deg2, quasars_lost=int(c.quasars_lost_vs_control),
                           false_removed=int(c.false_removed_vs_control), removed_per_deg2=c.get("removed_per_deg2"),
                           removed_lo=c.get("removed_lo"), removed_hi=c.get("removed_hi"), nonquasars_labelled_qso=c.nonquasars_labelled_qso))  # fmt: skip
    pd.DataFrame(ex).to_csv(a.out / "exchange.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 90):
        print(pred.to_string(index=False))
        print()
        print(pd.DataFrame(adopt).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

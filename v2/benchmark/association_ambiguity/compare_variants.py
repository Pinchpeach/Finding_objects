#!/usr/bin/env python3
"""Variants of the ambiguity rules against the baseline on the COSMOS2020 association truth: rates, exchange table, intervals (2.61.7).

    python compare_variants.py --measure DIR --variants base same_nearest ... --out OUT [--fields deep_cosmos_1,...]

``DIR/<variant>/`` is the output of ``association_truth/measure_association.py`` for that variant (``rows_<v>.csv.gz``,
``false_missed_<v>.csv``, ``structure_<v>.csv``, ``fragments_<v>.csv``, ``per_field_<v>.json``).  Written:

  rates.csv       per variant and catalogue (AllWISE, 2MASS, GALEX): rows with an expected counterpart, joined, false rate of the known
                  joins, missed rate of the unjoined rows (pooled over the fields, Wilson interval)
  exchange.csv    against the first variant (the baseline), row by row: rows that joined and did not before, by what the join is
                  (correct / false / unknown), rows that joined before and no longer do (by the outcome they had), rows joined in both
                  whose outcome changed (``switched_*``), and the net change of correct, false and unknown links over all paired rows.
                  A false link added is the cost, a missed counterpart found the gain.
  paired.csv      the paired change of the false rate (percentage points) and of the missed rate, with a field-bootstrap 95 % interval
                  (the fields are the unit of independence; the same fields in both variants)
  structure.csv   objects, merged objects (two truth sources more than 1'' / 2'' apart), truth sources with an extra one-catalogue
                  top-level object (fragments) and the extra objects
"""

from __future__ import annotations

import sys

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

CATS = ["AllWISE", "2MASS PSC", "GALEX AIS"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def rows_of(d: Path, v: str, fields) -> pd.DataFrame:
    r = pd.read_csv(d / v / f"rows_{v}.csv.gz", low_memory=False)
    return r[r.field.isin(fields)] if fields else r


def per_field_counts(r: pd.DataFrame, cat: str) -> pd.DataFrame:
    x = r[(r.catalog == cat) & r.outcome.isin(["correct", "false", "unknown", "missed", "rightly_alone"])]
    g = x.groupby("field").outcome.value_counts().unstack(fill_value=0)
    for c in ("correct", "false", "unknown", "missed", "rightly_alone"):
        if c not in g:
            g[c] = 0
    g["joined"] = g.correct + g.false + g.unknown
    g["known"] = g.correct + g.false
    g["unjoined"] = g.missed + g.rightly_alone
    return g


def rates(r: pd.DataFrame, cat: str) -> dict:
    g = per_field_counts(r, cat).sum()
    lo_f, hi_f = wilson(g.false, g.known)
    lo_m, hi_m = wilson(g.missed, g.unjoined)
    return dict(rows=int(g.joined + g.unjoined), joined=int(g.joined), correct=int(g.correct), false=int(g.false), unknown=int(g.unknown), missed=int(g.missed),
                false_pct=round(100 * g.false / g.known, 3) if g.known else math.nan, false_ci=f"{lo_f:.2f}-{hi_f:.2f}",
                missed_pct=round(100 * g.missed / g.unjoined, 3) if g.unjoined else math.nan, missed_ci=f"{lo_m:.2f}-{hi_m:.2f}")  # fmt: skip


def boot_paired(rb: pd.DataFrame, rv: pd.DataFrame, cat: str, n=4000, seed=1):
    a, b = per_field_counts(rb, cat), per_field_counts(rv, cat)
    f = sorted(set(a.index) & set(b.index))
    a, b = a.loc[f], b.loc[f]
    rng = np.random.default_rng(seed)

    def stat(idx):
        x, y = a.iloc[idx].sum(), b.iloc[idx].sum()
        return (100 * (y.false / y.known - x.false / x.known), 100 * (y.missed / y.unjoined - x.missed / x.unjoined))

    est = stat(np.arange(len(f)))
    s = np.array([stat(rng.integers(0, len(f), len(f))) for _ in range(n)])
    return est, np.nanpercentile(s, [2.5, 97.5], axis=0)


def exchange(rb: pd.DataFrame, rv: pd.DataFrame, cat: str) -> dict:
    cols = ["field_row", "joined", "outcome"]
    b = rb[rb.catalog == cat][cols]
    v = rv[rv.catalog == cat][cols]
    m = b.merge(v, on="field_row", suffixes=("_b", "_v"))
    new = m[~m.joined_b & m.joined_v]
    lost = m[m.joined_b & ~m.joined_v]
    out = dict(newly_joined=len(new), new_correct=int((new.outcome_v == "correct").sum()), new_false=int((new.outcome_v == "false").sum()),
               new_unknown=int((new.outcome_v == "unknown").sum()), unjoined_now=len(lost), lost_correct=int((lost.outcome_b == "correct").sum()),
               lost_false=int((lost.outcome_b == "false").sum()), lost_unknown=int((lost.outcome_b == "unknown").sum()))  # fmt: skip
    # rows joined in both runs whose outcome changed (joined to another object): left out until the Codex review of 2.61.8, so the
    # net counts were not the real net change (GALEX same_nearest: false 80 -> 79 in rates.csv, net_false 0 here)
    both = m[m.joined_b & m.joined_v & (m.outcome_b != m.outcome_v)]
    out.update(switched=len(both), switched_to_correct=int((both.outcome_v == "correct").sum()), switched_to_false=int((both.outcome_v == "false").sum()),
               switched_from_correct=int((both.outcome_b == "correct").sum()), switched_from_false=int((both.outcome_b == "false").sum()))  # fmt: skip
    # net change over every paired row: (joined with this outcome in the variant) - (in the base)
    for k in ("correct", "false", "unknown"):
        out[f"net_{k}"] = int(((m.outcome_v == k) & m.joined_v).sum() - ((m.outcome_b == k) & m.joined_b).sum())
    return out


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields", default="")
    a = ap.parse_args()
    t0 = RI.start()
    fields = [f for f in a.fields.split(",") if f]
    a.out.mkdir(parents=True, exist_ok=True)
    R = {v: rows_of(a.measure, v, fields) for v in a.variants}
    base = a.variants[0]
    rt, ex, pr, st = [], [], [], []
    for v in a.variants:
        for c in CATS:
            rt.append(dict(variant=v, catalog=c, **rates(R[v], c)))
            if v != base:
                ex.append(dict(variant=v, catalog=c, **exchange(R[base], R[v], c)))
                est, ci = boot_paired(R[base], R[v], c)
                pr.append(dict(variant=v, catalog=c, d_false_pp=round(est[0], 3), d_false_ci=f"{ci[0][0]:.3f} to {ci[1][0]:.3f}", d_missed_pp=round(est[1], 3),
                               d_missed_ci=f"{ci[0][1]:.3f} to {ci[1][1]:.3f}"))  # fmt: skip
        s = pd.read_csv(a.measure / v / f"structure_{v}.csv")
        s = s[s.field.isin(fields)] if fields else s
        row = dict(variant=v, fields=len(s), objects=int(s.n_objects.sum()), merged_gt1=int(s.merged_objects_gt1.sum()), merged_gt2=int(s.merged_objects_gt2.sum()))
        f_fr = a.measure / v / f"fragments_{v}.csv"  # only from a full pipeline run (objects_summary.csv)
        if f_fr.exists():
            fr = pd.read_csv(f_fr)
            fr = fr[fr.field.isin(fields)] if fields else fr
            row.update(top_level_objects=int(fr.top_level_objects.sum()), truth_sources=int(fr.truth_sources.sum()), truth_with_fragments=int(fr.truth_with_fragments.sum()),
                       extra_fragment_objects=int(fr.extra_fragment_objects.sum()))  # fmt: skip
        st.append(row)
    for name, rows in (("rates", rt), ("exchange", ex), ("paired", pr), ("structure", st)):
        pd.DataFrame(rows).to_csv(a.out / f"{name}.csv", index=False)
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(f"== {name}\n{pd.DataFrame(rows).to_string(index=False)}")
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

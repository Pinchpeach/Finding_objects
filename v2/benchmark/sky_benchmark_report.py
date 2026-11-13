#!/usr/bin/env python3
"""Scores on the sky-spread SDSS benchmark (2.52.0; build_sdss_sky_truth.py).

Every object is new to the models (anything within 1.5" of a training or
tuning set was removed), so the whole set is a test set; the sky-cell split
(test = held-out cells) is reported as well for later refits.  Uncertainties
resample sky cells (field_stats.field_bootstrap with field = sky_cell),
because objects in one cell share plates, depth and extinction.  Breakdowns
by Galactic latitude and SDSS r PSF magnitude answer the review's question of
whether the plate-clustered 2.x benchmark represents the sky (3.1).

    python v2/benchmark/sky_benchmark_report.py --dir v2/benchmark/sdss_sky \
        --pred-fusion P1.csv --pred-gbm P2.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_stats as FS  # noqa: E402


def load(pred, truth, manifest):
    p = pd.read_csv(pred)[["benchmark_id", "truth_class", "primary_class"]]
    return p.merge(truth, on="benchmark_id", how="left").merge(manifest, on="benchmark_id", how="left")


def scores(m, nboot):
    x = m.rename(columns={"primary_class": "ours", "truth_class": "t_truth"}).assign(field=m.sky_cell)
    s = FS.summary(x, nboot)
    s["n"] = len(m)
    s["unknown"] = int((m.primary_class == "UNKNOWN").sum())
    for c in FS.C:
        t = m.truth_class == c
        s[f"recall_{c}"] = round(100 * float((m.primary_class[t] == c).mean()), 2) if t.any() else None
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--pred-fusion", type=Path, required=True)
    ap.add_argument("--pred-gbm", type=Path)
    ap.add_argument("--nboot", type=int, default=1000)
    a = ap.parse_args()
    truth = pd.read_csv(a.dir / "truth.csv", usecols=lambda c: c in ("benchmark_id", "gal_b", "psfmag_r", "sky_cell", "plate"))
    manifest = pd.read_csv(a.dir / "manifest.csv", usecols=["benchmark_id", "split"])
    preds = {"fusion": load(a.pred_fusion, truth, manifest)}
    if a.pred_gbm and a.pred_gbm.exists():
        preds["gbm"] = load(a.pred_gbm, truth, manifest)
    rows = []
    for model, m in preds.items():
        m = m.assign(b_bin=pd.cut(m.gal_b.abs(), [0, 20, 30, 45, 60, 90], include_lowest=True).astype(str),
                     r_bin=pd.cut(pd.to_numeric(m.psfmag_r, errors="coerce"), [0, 17, 18, 19, 20, 21, 30]).astype(str))
        rows.append({"model": model, "subset": "all", **scores(m, a.nboot)})
        rows.append({"model": model, "subset": "test_cells", **scores(m[m.split == "test"], a.nboot)})
        for col in ("b_bin", "r_bin"):
            for k, g in m.groupby(col):
                if len(g) >= 30 and g.truth_class.nunique() > 0:
                    rows.append({"model": model, "subset": f"{col}={k}", **scores(g, 200)})
    res = pd.DataFrame(rows)
    keep = ["model", "subset", "n", "n_fields", "acc", "acc_lo", "acc_hi", "bal_acc", "recall_STAR", "recall_GALAXY",
            "recall_QSO", "precision_STAR", "precision_GALAXY", "precision_QSO", "unknown", "baseline_dsc", "ours_on_dsc"]
    res = res[[c for c in keep if c in res]]
    res.to_csv(a.dir / "scores.csv", index=False)
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))
    if "gbm" in preds:
        f, g = preds["fusion"].set_index("benchmark_id"), preds["gbm"].set_index("benchmark_id")
        g = g.loc[f.index]
        p, n01, n10 = FS.mcnemar((g.primary_class == g.truth_class).to_numpy(), (f.primary_class == f.truth_class).to_numpy())
        print(f"\nsingle GBM vs fusion: GBM only right {n01}, fusion only right {n10}, exact McNemar p = {p:.3g}")
    t = pd.read_csv(a.dir / "truth.csv")
    print("\nplates per class:", t.groupby("truth_class").plate.nunique().to_dict(),
          "| sky cells per class:", t.groupby("truth_class").sky_cell.nunique().to_dict())


if __name__ == "__main__":
    main()

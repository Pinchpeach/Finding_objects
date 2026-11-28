#!/usr/bin/env python3
"""How much the benchmark numbers rest on samples that the server filled from the front (2.62.7, task 거 item 4; MEASUREMENT AND PROPOSALS, nothing is changed).

    python server_fill_dependence.py --out OUT [--eval-dir DIR]

Three samples, each drawn from a list the service returned without ``ORDER BY`` and cut with ``row_limit`` / ``TOP`` (WORK_REPORT_2026-11-28a.md section 2):

* ``desi_external/truth.csv`` (4,795 DESI DR1 spectra): per (class, r bin, 10 deg RA window) cell ``row_limit = 4 x per cell`` rows, then a random draw.  The tool measures the footprint of every cell
  (``desi_external_cells.csv``: how far the cell's RA range sits from the window's lower edge, how much of the window it covers), then runs the coarse rule baseline of the repository on the
  committed features (the test split, ``validate_catalog_truth.py`` + ``evaluate_rule_baseline.py``, offline) and gives ``accuracy_when_classified`` with the interval the independence
  assumption gives (Wilson) and the intervals that treat the cell, and the RA window, as the unit (bootstrap over cells / windows): ``desi_external_ci.csv``; accuracy by window and
  a homogeneity test: ``desi_external_by_window.csv``.
* ``truth_data/ground_truth.csv`` (the SDSS benchmark, ``ORDER BY specObjID``): plates, MJD and sky footprint of the whole list and of the test split (``sdss_footprint.csv``).
* ``reference_objects.csv.gz`` (DR16Q 300 rows) and the 520-object validation plan: RA range of the sample, and how many plan objects are in the committed table (``reference_footprint.csv``,
  ``reference_plan_overlap.csv``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark"))
import run_info as RI  # noqa: E402

def windows() -> tuple:
    import ast

    for node in ast.parse((V2 / "benchmark" / "build_desi_truth.py").read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "RA_WINDOWS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("RA_WINDOWS not found")


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(c - h), float(c + h)


def cells(truth: pd.DataFrame) -> pd.DataFrame:
    w = windows()
    t = truth.copy()
    t["window"] = [next((i for i, (lo, hi) in enumerate(w) if lo <= ra <= hi), -1) for ra in t.ra]
    t["cell"] = t.truth_class + "|" + t.r_bin.astype(str) + "|w" + t.window.astype(str)
    rows = []
    for c, g in t.groupby("cell"):
        lo, hi = w[int(g.window.iloc[0])]
        rows.append(dict(cell=c, truth_class=g.truth_class.iloc[0], r_bin=g.r_bin.iloc[0], window=f"{lo:g}-{hi:g}", n=len(g), ra_min=g.ra.min(), ra_max=g.ra.max(),
                         ra_width_deg=g.ra.max() - g.ra.min(), min_ra_above_window_edge_deg=g.ra.min() - lo, window_width_deg=hi - lo))
    return t, pd.DataFrame(rows)


def run_eval(out: Path) -> Path:
    """The rule baseline on the committed DESI external features, test split (offline, ~30 s); the same two commands as ``v2_desi_external_validation.yml`` with ``--split test``."""
    d = V2 / "benchmark" / "desi_external"
    ready, ev = out / "ready", out / "eval_test"
    subprocess.run([sys.executable, str(V2 / "benchmark" / "validate_catalog_truth.py"), "--truth", str(d / "truth.csv"), "--catalog-root", str(d / "catalog_features"), "--out", str(ready), "--allow-unbalanced"],
                   check=True, capture_output=True)
    subprocess.run([sys.executable, str(V2 / "benchmark" / "evaluate_rule_baseline.py"), "--truth", str(d / "truth.csv"), "--catalog-root", str(d / "catalog_features"), "--manifest", str(ready / "benchmark_manifest.csv"),
                    "--out", str(ev), "--split", "test"], check=True, capture_output=True)
    return ev / "rule_baseline_test_predictions.csv"


def acc(g: pd.DataFrame) -> tuple[int, int]:
    c = g.primary_class.ne("UNKNOWN")
    return int((g.primary_class == g.truth_class)[c].sum()), int(c.sum())


def boot(groups: list[pd.DataFrame], reps: int = 4000, seed: int = 1) -> tuple[float, float]:
    ks = np.array([acc(g)[0] for g in groups])
    ns = np.array([acc(g)[1] for g in groups])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(groups), size=(reps, len(groups)))
    est = ks[idx].sum(axis=1) / np.maximum(1, ns[idx].sum(axis=1))
    return float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--eval-dir", type=Path, help="reuse the predictions of an earlier run of this tool (default: run the baseline)")
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)

    # 1. DESI external: footprint of the cells
    truth = pd.read_csv(V2 / "benchmark" / "desi_external" / "truth.csv")
    t, c = cells(truth)
    c.to_csv(a.out / "desi_external_cells.csv", index=False)
    w = windows()
    cover = []
    for i, (lo, hi) in enumerate(w):
        g = t[t.window == i]
        iv = sorted((cc.ra_min, cc.ra_max) for cc in c[c.window == f"{lo:g}-{hi:g}"].itertuples())
        merged = []
        for s, e in iv:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        cover.append(dict(window=f"{lo:g}-{hi:g}", n_objects=len(g), n_cells=g.cell.nunique(), covered_deg=sum(e - s for s, e in merged), window_deg=hi - lo,
                          covered_pct=round(100 * sum(e - s for s, e in merged) / (hi - lo), 2),
                          occupied_0p1deg_bins_pct=round(100 * g.ra.sub(lo).floordiv(0.1).nunique() / ((hi - lo) / 0.1), 1), median_min_ra_above_edge_deg=float(c[c.window == f"{lo:g}-{hi:g}"].min_ra_above_window_edge_deg.median())))
    pd.DataFrame(cover).to_csv(a.out / "desi_external_window_cover.csv", index=False)
    summ = dict(cells=len(c), objects=len(t), median_cell_ra_width_deg=float(c.ra_width_deg.median()), cells_with_width_lt_0p5=int((c.ra_width_deg < 0.5).sum()),
                share_cells_width_lt_0p5_pct=round(100 * float((c.ra_width_deg < 0.5).mean()), 1), max_min_ra_above_window_edge_deg=float(c.min_ra_above_window_edge_deg.max()),
                share_objects_in_cells_with_min_ra_within_0p2_of_edge_pct=round(100 * float(t.cell.map(c.set_index("cell").min_ra_above_window_edge_deg).le(0.2).mean()), 1),
                max_window_cover_pct=float(max(x["covered_pct"] for x in cover)), max_window_occupied_0p1deg_bins_pct=float(max(x["occupied_0p1deg_bins_pct"] for x in cover)))
    pd.DataFrame([summ]).to_csv(a.out / "desi_external_footprint_summary.csv", index=False)

    # 2. DESI external: accuracy with independence vs cluster intervals
    pred_path = (a.eval_dir / "eval_test" / "rule_baseline_test_predictions.csv") if a.eval_dir else run_eval(a.out)
    p = pd.read_csv(pred_path).merge(t[["benchmark_id", "cell", "window", "r_bin"]], on="benchmark_id")
    k, n = acc(p)
    lo_w, hi_w = wilson(k, n)
    lo_c, hi_c = boot([g for _, g in p.groupby("cell")])
    lo_x, hi_x = boot([g for _, g in p.groupby("window")])
    ci = pd.DataFrame([dict(split="test", n_test=len(p), classified=n, correct=k, accuracy_when_classified=round(k / n, 4), wilson_lo=round(lo_w, 4), wilson_hi=round(hi_w, 4),
                            wilson_width_pp=round(100 * (hi_w - lo_w), 2), cell_bootstrap_lo=round(lo_c, 4), cell_bootstrap_hi=round(hi_c, 4), cell_bootstrap_width_pp=round(100 * (hi_c - lo_c), 2),
                            window_bootstrap_lo=round(lo_x, 4), window_bootstrap_hi=round(hi_x, 4), window_bootstrap_width_pp=round(100 * (hi_x - lo_x), 2),
                            cells_in_test=p.cell.nunique(), windows_in_test=p.window.nunique())])
    ci["width_ratio_cell_vs_wilson"] = round(ci.cell_bootstrap_width_pp / ci.wilson_width_pp, 2)
    ci["width_ratio_window_vs_wilson"] = round(ci.window_bootstrap_width_pp / ci.wilson_width_pp, 2)
    ci.to_csv(a.out / "desi_external_ci.csv", index=False)
    rows = []
    for win, g in p.groupby("window"):
        kk, nn = acc(g)
        rows.append(dict(window=f"{w[int(win)][0]:g}-{w[int(win)][1]:g}", n=len(g), classified=nn, correct=kk, accuracy=round(kk / max(1, nn), 4)))
    bw = pd.DataFrame(rows)
    table = np.array([[r["correct"], r["classified"] - r["correct"]] for r in rows])
    chi2, pval, _, _ = stats.chi2_contingency(table)
    bw["max_minus_min_pp"] = round(100 * (bw.accuracy.max() - bw.accuracy.min()), 2)
    bw["chi2_homogeneity_p"] = round(float(pval), 4)
    bw.to_csv(a.out / "desi_external_by_window.csv", index=False)

    # 3. SDSS benchmark: plates and footprint
    sd = pd.read_csv(V2 / "benchmark" / "truth_data" / "ground_truth.csv")
    import hashlib

    def split_for(bid):  # the SDSS split is by benchmark_id (validate_catalog_truth.py)
        x = int(hashlib.sha256(bid.encode()).hexdigest()[:8], 16) % 10
        return "train" if x < 6 else ("calibration" if x < 8 else "test")

    sd["split"] = sd.benchmark_id.map(split_for)
    foot = []
    for label, g in (("all", sd), ("test", sd[sd.split == "test"])):
        for cls, gg in [("all", g), *list(g.groupby("truth_class"))]:
            top = gg.plate.value_counts()
            foot.append(dict(subset=label, truth_class=cls, n=len(gg), plates=int(gg.plate.nunique()), plate_mjd_pairs=int(gg[["plate", "mjd"]].drop_duplicates().shape[0]), top10_plate_share_pct=round(100 * top.head(10).sum() / len(gg), 1),
                             mjd_min=int(gg.mjd.min()), mjd_max=int(gg.mjd.max()), ra_min=round(gg.ra.min(), 1), ra_max=round(gg.ra.max(), 1), dec_min=round(gg.dec.min(), 1), dec_max=round(gg.dec.max(), 1),
                             specobjid_min=int(gg.specobjid.min()), specobjid_max=int(gg.specobjid.max())))
    pd.DataFrame(foot).to_csv(a.out / "sdss_footprint.csv", index=False)

    # 4. reference objects
    ref = pd.read_csv(V2 / "reference_objects" / "reference_objects.csv.gz")
    plan = pd.read_csv(V2 / "reference_objects" / "validation" / "plan.csv")
    q = ref[ref.type == "QSO_SPECTROSCOPIC"]
    pq = plan[plan.type == "QSO_SPECTROSCOPIC"]
    pd.DataFrame([dict(sample="committed table, QSO_SPECTROSCOPIC", n=len(q), ra_min=q.ra.min(), ra_max=q.ra.max(), dec_min=q.dec.min(), dec_max=q.dec.max()),
                  dict(sample="validation plan (2.46.2), QSO_SPECTROSCOPIC", n=len(pq), ra_min=pq.ra.min(), ra_max=pq.ra.max(), dec_min=pq.dec.min(), dec_max=pq.dec.max())]).to_csv(a.out / "reference_footprint.csv", index=False)
    m = plan.merge(ref[["name", "type"]].assign(in_table=True), on=["name", "type"], how="left")
    m["in_table"] = m.in_table.fillna(False)
    ov = m.groupby("type").agg(plan_n=("name", "size"), in_committed_table=("in_table", "sum")).reset_index()
    ov["missing"] = ov.plan_n - ov.in_committed_table
    ov.sort_values("missing", ascending=False).to_csv(a.out / "reference_plan_overlap.csv", index=False)

    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(pd.DataFrame([summ]).T.to_string(header=False))
        print(pd.DataFrame(cover).to_string(index=False))
        print(ci.T.to_string(header=False))
        print(bw.to_string(index=False))
        print(pd.DataFrame(foot).to_string(index=False))
        print(pd.read_csv(a.out / "reference_footprint.csv").to_string(index=False))
        print(ov[ov.missing > 0].sort_values("missing", ascending=False).to_string(index=False), f"\nplan objects missing from the committed table: {int(ov.missing.sum())} of {int(ov.plan_n.sum())}")
    RI.write(a.out, [V2 / "benchmark" / "desi_external" / "truth.csv", V2 / "benchmark" / "truth_data" / "ground_truth.csv", V2 / "reference_objects" / "reference_objects.csv.gz",
                     V2 / "reference_objects" / "validation" / "plan.csv"], t0=t0, note="server-fill dependence; reads committed tables, runs the rule baseline offline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

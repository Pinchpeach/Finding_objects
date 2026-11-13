#!/usr/bin/env python3
"""Score a prior-layer A/B run (2.52.0, ROADMAP_2026-11-12 item 4).

prior_layer_study.py replays Stage 5 on one stored run; this script scores
the variants of a real A/B run (experiment-ab-fields.yml, fresh collection,
the same 89 fields) on the fixed calibration / test field split of that
study, so the COSMOS counts in faint_class_prior_cosmos.csv (built from the
calibration fields) are judged only on fields they never saw.

For every variant: label accuracy, balanced accuracy, per-class recall and
precision, ECE (15 bins, Guo et al. 2017), classwise ECE (Kull et al. 2019),
NLL and Brier of p_*, by split and field group; paired exact McNemar of the
labels and a field bootstrap of dECE / dNLL against the base variant on the
test fields.

Runs before 2.52.0's class_prior.consistent wrote p_* = Q (the prior-layer
posterior) in the unified layer; ``--consistent`` applies that step here, so
the reported p_* are those 2.52.0 writes.

    python v2/benchmark/score_prior_layer_ab.py \
        --ab v2/benchmark/experiments/prior_layer_2_52 --base base --out OUT
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
sys.path.insert(0, str(B))
import prior_layer_study as S  # noqa: E402
from field_stats import mcnemar  # noqa: E402

_s = importlib.util.spec_from_file_location("v2_class_prior_ab", B.parent / "Preprocess" / "class_prior.py")
CP = importlib.util.module_from_spec(_s)
_s.loader.exec_module(CP)

C = S.C
EPS = S.EPS


def load(path: Path) -> pd.DataFrame:
    t = pd.read_csv(path, low_memory=False)
    # runs scored before the merge fix carry the probability columns twice (_x, _y; identical)
    for c in [c for c in t.columns if c.endswith("_x")]:
        t[c[:-2]] = t[c]
    t = t.drop(columns=[c for c in t.columns if c.endswith(("_x", "_y"))])
    return t


def probs(t: pd.DataFrame, consistent: bool) -> np.ndarray:
    P = np.clip(t[[f"p_{c.lower()}" for c in C]].to_numpy(float), EPS, 1)
    P = P / P.sum(1, keepdims=True)
    if consistent and t.get("prior_layer", pd.Series("legacy")).eq("unified").all():
        P = CP.consistent(P, t.ours.tolist(), pd.to_numeric(t.primary_confidence, errors="coerce").to_numpy(), C)
    return P


def label_stats(lab: np.ndarray, truth: np.ndarray) -> dict:
    d = {"label_acc": round(100 * float((lab == truth).mean()), 3), "unknown": int((lab == "UNKNOWN").sum())}
    rec = []
    for c in C:
        t, p = truth == c, lab == c
        r = float((lab[t] == c).mean()) if t.any() else np.nan
        rec.append(r)
        d[f"recall_{c}"] = round(100 * r, 2)
        d[f"precision_{c}"] = round(100 * float((truth[p] == c).mean()), 2) if p.any() else None
    d["bal_acc"] = round(100 * float(np.nanmean(rec)), 3)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ab", type=Path, required=True, help="directory with truth_probs_<variant>.csv.gz")
    ap.add_argument("--base", default="base")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-consistent", action="store_true")
    ap.add_argument("--nboot", type=int, default=1000)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    files = sorted(a.ab.glob("truth_probs_*.csv.gz"))
    tabs = {f.name[len("truth_probs_"):-len(".csv.gz")]: load(f) for f in files}
    key = ["field", "t_ra", "t_dec"]
    base = tabs[a.base]
    base = base[base.t_truth.isin(C)].reset_index(drop=True)
    k0 = base[key].round(6).apply(tuple, axis=1)
    y = base.t_truth.map({c: i for i, c in enumerate(C)}).to_numpy()
    truth = base.t_truth.to_numpy()
    split = S.split(base.field).to_numpy()
    group = np.where(base.field.str.startswith("deep"), "cosmos", "bright")
    r = pd.to_numeric(base.get(S.FAINT.R_COLUMN), errors="coerce").to_numpy(float)
    rb = S.r_bin(r)
    V = {}
    for v, t in tabs.items():
        t = t.assign(_k=t[key].round(6).apply(tuple, axis=1)).drop_duplicates("_k").set_index("_k").loc[k0]
        V[v] = (probs(t, not a.no_consistent), t.ours.to_numpy())
    rows = []
    for sp in ("cal", "test", "all"):
        for grp in ("all", "cosmos", "bright"):
            k = (split == sp if sp != "all" else True) & (group == grp if grp != "all" else True)
            k = np.broadcast_to(k, y.shape)
            for v, (P, lab) in V.items():
                rows.append({"split": sp, "group": grp, "variant": v, **S.metrics(P[k], y[k]), **label_stats(lab[k], truth[k])})
    res = pd.DataFrame(rows)
    by_r = []
    for b in range(len(S.R_EDGES)):
        k = (split == "test") & (rb == b)
        if k.any():
            for v, (P, lab) in V.items():
                by_r.append({"r_bin": b, "variant": v, **S.metrics(P[k], y[k]), **label_stats(lab[k], truth[k])})
    by_r = pd.DataFrame(by_r)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(res.to_string(index=False))
    print("\ntest fields by LS r bin", list(S.R_EDGES), "(last bin: no LS r)")
    print(by_r.to_string(index=False))
    rng = np.random.default_rng(2052)
    tests = []
    Pb, lb = V[a.base]
    for grp in ("all", "cosmos", "bright"):
        k = (split == "test") & ((group == grp) if grp != "all" else True)
        fk = base.field.to_numpy()[k]
        uf = np.unique(fk)
        idx = {f: np.flatnonzero(fk == f) for f in uf}
        yk = y[k]
        for v, (P, lab) in V.items():
            if v == a.base:
                continue
            p, n01, n10 = mcnemar(lab[k] == truth[k], lb[k] == truth[k])
            de, dl, da = [], [], []
            for _ in range(a.nboot):
                j = np.concatenate([idx[f] for f in rng.choice(uf, len(uf))])
                de.append(100 * (S.ece(P[k][j], yk[j]) - S.ece(Pb[k][j], yk[j])))
                pa = np.clip(P[k][j][np.arange(len(j)), yk[j]], EPS, 1)
                pb = np.clip(Pb[k][j][np.arange(len(j)), yk[j]], EPS, 1)
                dl.append(float(-np.log(pa).mean() + np.log(pb).mean()))
                tj = truth[k][j]
                da.append(100 * (float((lab[k][j] == tj).mean()) - float((lb[k][j] == tj).mean())))
            q = lambda x: np.percentile(x, [2.5, 97.5])  # noqa: E731
            tests.append({"group": grp, "variant": v, "n_fields": len(uf), "only_variant_right": n01, "only_base_right": n10,
                          "mcnemar_p": float(f"{p:.3g}"),
                          "dacc_lo": round(q(da)[0], 3), "dacc_hi": round(q(da)[1], 3),
                          "dece_lo": round(q(de)[0], 3), "dece_hi": round(q(de)[1], 3),
                          "dnll_lo": round(q(dl)[0], 4), "dnll_hi": round(q(dl)[1], 4)})
    tests = pd.DataFrame(tests)
    print(f"\ntest fields vs {a.base}: exact McNemar and field bootstrap ({a.nboot}) of dacc, dECE (points), dNLL")
    print(tests.to_string(index=False))
    res.to_csv(a.out / "prior_layer_ab_metrics.csv", index=False)
    by_r.to_csv(a.out / "prior_layer_ab_by_r.csv", index=False)
    tests.to_csv(a.out / "prior_layer_ab_tests.csv", index=False)


if __name__ == "__main__":
    main()

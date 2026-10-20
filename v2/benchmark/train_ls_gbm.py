#!/usr/bin/env python3
"""Train the Legacy Surveys gradient-boosting coarse classifier (LS-GBM-001,
2.11.0) and export it for numpy-only inference (Preprocess/ls_gbm.py).

Training data: desi_gbm_truth/train.csv.gz (build_desi_gbm_truth.py; DESI
DR1 SPECTYPE, LS DR9 photometry, no benchmark objects).  DR9 rows carry E(B-V)
instead of the MW transmissions the production DR10 collector returns; the
transmission is 10^(-0.4 R E(B-V)) with the Legacy Surveys DR9 coefficients
(DECam g, r, z = 3.214, 2.165, 1.211; BASS/MzLS g, r, z = 3.258, 2.176,
1.199; WISE W1, W2 = 0.184, 0.113; legacysurvey.org/dr9/catalogs, from
Schlafly & Finkbeiner 2011).

A random 10 % of the training rows is held out for early stopping and a
report; the independent checks are the benchmark test splits (SDSS, DESI),
run through the full pipeline after the fusion refit.

    python v2/benchmark/train_ls_gbm.py [--out v2/Preprocess/ls_gbm_model.npz]
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
V2 = BENCH.parent
sys.path.insert(0, str(V2 / "Preprocess"))
import ls_gbm  # noqa: E402

R_SOUTH = {"g": 3.214, "r": 2.165, "z": 1.211, "w1": 0.184, "w2": 0.113}
R_NORTH = {"g": 3.258, "r": 2.176, "z": 1.199, "w1": 0.184, "w2": 0.113}


def production_frame(d: pd.DataFrame) -> pd.DataFrame:
    """DR9 training columns (p_*) -> the production DR10 column names."""
    P = ls_gbm.P
    out = pd.DataFrame(index=d.index)
    north = d.get("p_photsys", pd.Series("S", index=d.index)).astype(str).str.strip().str.upper().eq("N")
    ebv = pd.to_numeric(d.get("p_ebv"), errors="coerce").fillna(0.0)
    for b in ls_gbm.BANDS:
        out[P + f"flux_{b}"] = pd.to_numeric(d.get(f"p_flux_{b}"), errors="coerce")
        out[P + f"flux_ivar_{b}"] = pd.to_numeric(d.get(f"p_flux_ivar_{b}"), errors="coerce")
        r = np.where(north, R_NORTH[b], R_SOUTH[b])
        out[P + f"mw_transmission_{b}"] = 10 ** (-0.4 * r * ebv)
    out[P + "type"] = d.get("p_morphtype", pd.Series("", index=d.index)).astype(str)
    out[P + "shape_r"] = pd.to_numeric(d.get("p_shape_r"), errors="coerce")
    out[P + "sersic"] = pd.to_numeric(d.get("p_sersic"), errors="coerce")
    return out


def export(clf, path: Path, names=ls_gbm.FEATURES) -> None:
    """Flatten the fitted HistGradientBoostingClassifier trees into arrays."""
    feat, thr, mleft, left, right, leaf, value, start, tcls = [], [], [], [], [], [], [], [], []
    offset = 0
    for it in clf._predictors:
        for k, pred in enumerate(it):
            n = pred.nodes
            if n["is_categorical"].any():
                raise ValueError("categorical splits are not exported")
            start.append(offset)
            tcls.append(k)
            feat.append(n["feature_idx"].astype(np.int64))
            thr.append(n["num_threshold"].astype(float))
            mleft.append(n["missing_go_to_left"].astype(bool))
            left.append(n["left"].astype(np.int64))
            right.append(n["right"].astype(np.int64))
            leaf.append(n["is_leaf"].astype(bool))
            value.append(n["value"].astype(float))
            offset += len(n)
    base = np.asarray(clf._baseline_prediction, float).ravel()
    np.savez_compressed(
        path,
        feature=np.concatenate(feat),
        threshold=np.concatenate(thr),
        missing_left=np.concatenate(mleft),
        left=np.concatenate(left),
        right=np.concatenate(right),
        is_leaf=np.concatenate(leaf),
        value=np.concatenate(value),
        tree_start=np.array(start, np.int64),
        tree_class=np.array(tcls, np.int64),
        baseline=base,
        n_classes=np.int64(len(clf.classes_)),
        classes=np.array(list(clf.classes_)),
        features=np.array(names),
    )


def balance_weights(r: np.ndarray, y: np.ndarray, width: float = 0.5, cap: float = 30.0) -> np.ndarray:
    """Sample weights giving STAR, GALAXY and QSO equal total weight in every
    ``width``-mag bin of r (option ``--balance``; measured, not adopted).

    DESI targets few faint stars, so trained on the DESI class mix the trees
    learn "faint point source = QSO" (holdout star recall 0.44 at r = 21-22).
    The classifier should give class likelihoods; the class mix of the sky
    belongs in a separate prior (Bovy et al. 2011 keep the number-count prior
    out of the density model; Chaussidon et al. 2023 reweight their star
    training set to the QSO magnitude distribution).  Alone it raises the
    holdout faint-star recall (r 21-22: 0.44 -> 0.86), but after the fusion
    refit the benchmark gain in stars is paid in quasars (DESI test 92.41 ->
    92.31 %; McNemar p = 1.0).
    """
    b = np.floor(np.nan_to_num(r, nan=99.0) / width)
    key = b * 10 + y
    _, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    _, binv, bcnt = np.unique(b, return_inverse=True, return_counts=True)
    w = bcnt[binv] / (3.0 * cnt[inv])
    return np.clip(w, 0.0, cap)


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier

    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ls_gbm.MODEL_PATH)
    p.add_argument("--seed", type=int, default=7)
    # Measured 2026-10-20 and not adopted (WORK_REPORT_2026-10-20b.md): they
    # move faint stars from QSO to STAR but cost as many quasars.
    p.add_argument("--balance", action="store_true", help="class-balance each 0.5-mag r bin (see balance_weights)")
    p.add_argument("--snr", action="store_true", help="add the per-band S/N features (ls_gbm.SNR_FEATURES)")
    a = p.parse_args()
    d = pd.read_csv(BENCH / "desi_gbm_truth" / "train.csv.gz", low_memory=False)
    d = d[d.spectype.isin(ls_gbm.CLASSES)].reset_index(drop=True)
    X = ls_gbm.features(production_frame(d))
    names = ls_gbm.ALL_FEATURES if a.snr else ls_gbm.FEATURES
    X = X[:, : len(names)]
    y = d.spectype.map({c: i for i, c in enumerate(ls_gbm.CLASSES)}).to_numpy()
    keep = np.isfinite(X[:, 0]) | np.isfinite(X[:, 3])
    X, y = X[keep], y[keep]
    rng = np.random.default_rng(a.seed)
    hold = rng.random(len(y)) < 0.1
    clf = HistGradientBoostingClassifier(
        max_iter=400,
        learning_rate=0.08,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        random_state=a.seed,
    )
    clf.fit(X[~hold], y[~hold], sample_weight=balance_weights(X[~hold, 0], y[~hold]) if a.balance else None)
    assert list(clf.classes_) == [0, 1, 2]
    export(clf, a.out, names)
    ls_gbm.load_model.cache_clear()
    model = ls_gbm.load_model(str(a.out))
    z = ls_gbm.raw_scores(X[hold], model)
    p_np = np.exp(z - z.max(1, keepdims=True))
    p_np /= p_np.sum(1, keepdims=True)
    p_sk = clf.predict_proba(X[hold])
    acc = float((p_sk.argmax(1) == y[hold]).mean())
    rep = {
        "train_rows": int((~hold).sum()),
        "holdout_rows": int(hold.sum()),
        "iterations": int(clf.n_iter_),
        "holdout_accuracy": round(acc, 4),
        "numpy_vs_sklearn_max_abs_diff": float(np.abs(p_np - p_sk).max()),
        "holdout_accuracy_by_r": {},
    }
    r = X[hold, 0]
    for lo, hi in ((0, 19), (19, 21), (21, 22), (22, 23), (23, 30)):
        m = (r >= lo) & (r < hi)
        if m.any():
            rep["holdout_accuracy_by_r"][f"{lo}-{hi}"] = {
                "n": int(m.sum()),
                "acc": round(float((p_sk[m].argmax(1) == y[hold][m]).mean()), 4),
            }
    print(json.dumps(rep, indent=1))
    (BENCH / "desi_gbm_truth" / "train_report.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()

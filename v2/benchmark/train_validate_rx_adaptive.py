#!/usr/bin/env python3
"""Selection-aware radio/X-ray classifier.

Train optical/IR/UV and radio/X-ray-enriched candidates on the same training
split. Split the designated calibration partition into calibration-fit and
model-selection halves. Radio/X-ray features are enabled only when they improve
held-out calibration log-loss by a material margin without worsening Brier
score. The test split remains untouched until the variant is selected.
"""

from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)

import train_validate_classifier as tv

CLASSES = ["STAR", "GALAXY", "QSO"]


def half(bid: str) -> bool:
    return int(hashlib.sha256(("rx-select:" + str(bid)).encode()).hexdigest()[:8], 16) % 2 == 0


def brier(y, p, classes):
    one = np.zeros_like(p, float)
    mp = {c: i for i, c in enumerate(classes)}
    for i, v in enumerate(y):
        one[i, mp[v]] = 1.0
    return float(np.mean(np.sum((p - one) ** 2, axis=1)))


def ece(y, p, classes, bins=10):
    pred = np.argmax(p, axis=1)
    conf = np.max(p, axis=1)
    truth = np.array([classes.index(v) for v in y])
    ok = pred == truth
    out = 0.0
    for lo, hi in zip(np.linspace(0, 1, bins + 1)[:-1], np.linspace(0, 1, bins + 1)[1:]):
        m = (conf >= lo) & (conf < (hi if hi < 1 else hi + 1e-12))
        if m.any():
            out += m.mean() * abs(float(ok[m].mean()) - float(conf[m].mean()))
    return float(out)


def add_rx(x: pd.DataFrame, truth: pd.DataFrame):
    native = [
        c
        for c in truth.columns
        if c.startswith("rx_") and not c.startswith("rx_has_") and not c.endswith("_sep_arcsec")
    ]
    if not native:
        return x
    q = truth[["benchmark_id"] + native].copy()
    for col in native:
        q[col] = pd.to_numeric(q[col], errors="coerce")
    if "rx_radio_peak" in q and "rx_radio_integr" in q:
        peak = q["rx_radio_peak"].where(q["rx_radio_peak"] > 0)
        integ = q["rx_radio_integr"].where(q["rx_radio_integr"] > 0)
        q["rx_radio_log_peak"] = np.log10(peak)
        q["rx_radio_log_integr"] = np.log10(integ)
        q["rx_radio_integr_peak_ratio"] = integ / peak
    for col in list(native):
        low = col.lower()
        if any(k in low for k in ("flux", "rate", "count")):
            q["log10__" + col] = np.log10(q[col].where(q[col] > 0))
    return x.merge(q, on="benchmark_id", how="left")


def fit_calibrated(data, features, train_mask, cal_mask):
    base = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        min_samples_leaf=15,
        l2_regularization=1.0,
        random_state=42,
    )
    base.fit(data.loc[train_mask, features], data.loc[train_mask, "truth_class"])
    model = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    model.fit(data.loc[cal_mask, features], data.loc[cal_mask, "truth_class"])
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--catalog-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-logloss-improvement", type=float, default=0.005)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    truth = pd.read_csv(a.truth)
    manifest = pd.read_csv(a.manifest)
    cats = tv.read_catalogs(a.catalog_root)
    xb = tv.build_matrix(truth, cats)
    xe = add_rx(xb.copy(), truth)
    meta = truth[["benchmark_id", "truth_class"] + ([c for c in ["truth_selection"] if c in truth.columns])]
    split = manifest[["benchmark_id", "split"]]
    db = meta.merge(split, on="benchmark_id").merge(xb, on="benchmark_id")
    de = meta.merge(split, on="benchmark_id").merge(xe, on="benchmark_id")
    tr = db.split.eq("train")
    cal = db.split.eq("calibration")
    te = db.split.eq("test")
    cal_fit = cal & db.benchmark_id.map(half)
    cal_sel = cal & ~db.benchmark_id.map(half)
    # Guard pathological hash imbalance by swapping if either half misses a class.
    if set(db.loc[cal_fit, "truth_class"]) != set(CLASSES) or set(db.loc[cal_sel, "truth_class"]) != set(CLASSES):
        order = db.loc[cal].sort_values(["truth_class", "benchmark_id"]).copy()
        ids = set(
            order.groupby("truth_class", group_keys=False)
            .apply(lambda g: g.iloc[::2].benchmark_id, include_groups=False)
            .explode()
            .dropna()
        )
        cal_fit = cal & db.benchmark_id.isin(ids)
        cal_sel = cal & ~db.benchmark_id.isin(ids)

    variants = {}
    for name, data in [("baseline", db), ("radio_xray", de)]:
        feats = [c for c in data.columns if c not in {"benchmark_id", "truth_class", "truth_selection", "split"}]
        model = fit_calibrated(data, feats, tr, cal_fit)
        y = data.loc[cal_sel, "truth_class"].to_numpy()
        p = model.predict_proba(data.loc[cal_sel, feats])
        classes = list(model.classes_)
        variants[name] = {
            "features": feats,
            "select_log_loss": float(log_loss(y, p, labels=classes)),
            "select_brier": brier(y, p, classes),
            "select_ece": ece(y, p, classes),
        }

    base = variants["baseline"]
    rx = variants["radio_xray"]
    choose_rx = (
        rx["select_log_loss"] <= base["select_log_loss"] - a.min_logloss_improvement
        and rx["select_brier"] <= base["select_brier"]
    )
    chosen = "radio_xray" if choose_rx else "baseline"
    data = de if choose_rx else db
    feats = variants[chosen]["features"]
    final = fit_calibrated(data, feats, tr, cal)
    y = data.loc[te, "truth_class"].to_numpy()
    p = final.predict_proba(data.loc[te, feats])
    classes = list(final.classes_)
    pred = np.array(classes)[np.argmax(p, axis=1)]
    metrics = {
        "selected_variant": chosen,
        "selection_rule": "rx requires >=0.005 lower held-out calibration log-loss and non-worse Brier",
        "selection": {k: {kk: vv for kk, vv in v.items() if kk != "features"} for k, v in variants.items()},
        "test_rows": int(te.sum()),
        "features": len(feats),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "log_loss": float(log_loss(y, p, labels=classes)),
        "multiclass_brier": brier(y, p, classes),
        "confidence_ece_10bin": ece(y, p, classes),
    }
    if "truth_selection" in data:
        sel = data.loc[te, "truth_selection"].fillna("UNKNOWN").to_numpy()
        for g in sorted(set(sel)):
            m = sel == g
            metrics[f"accuracy_{g.lower()}"] = float(accuracy_score(y[m], pred[m]))
            metrics[f"n_{g.lower()}"] = int(m.sum())
    pd.DataFrame(
        confusion_matrix(y, pred, labels=CLASSES),
        index=[f"true_{c}" for c in CLASSES],
        columns=[f"pred_{c}" for c in CLASSES],
    ).to_csv(a.out / "confusion_matrix.csv")
    pd.DataFrame(classification_report(y, pred, labels=CLASSES, output_dict=True, zero_division=0)).T.to_csv(
        a.out / "classification_report.csv"
    )
    (a.out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    joblib.dump(
        {"model": final, "features": feats, "classes": classes, "selected_variant": chosen}, a.out / "classifier.joblib"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate STAR-branch WHITE_DWARF vs NORMAL_STAR classification.

Truth: clean SDSS spectroscopy.
Features: Gaia DR3 astrometry/photometry only.
Baseline: broad Gaia HR cut from Gentile Fusillo et al. (2021):
          M_G > 6 + 5*(BP-RP), parallax_over_error > 1.
Learned model: HistGradientBoosting + held-out sigmoid calibration.
"""

from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

try:
    from sklearn.frozen import FrozenEstimator
except Exception:
    FrozenEstimator = None
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)

CLASSES = ["NORMAL_STAR", "WHITE_DWARF"]


def split_for(bid: str) -> str:
    x = int(hashlib.sha256(("star-wd:" + str(bid)).encode()).hexdigest()[:8], 16) % 10
    return "train" if x < 6 else ("calibration" if x < 8 else "test")


def num(d, c):
    return pd.to_numeric(d[c], errors="coerce") if c in d else pd.Series(np.nan, index=d.index)


def prepare(d):
    x = pd.DataFrame({"benchmark_id": d.benchmark_id.astype(str)})
    aliases = {
        "parallax": ["parallax", "Plx"],
        "parallax_error": ["parallax_error", "e_Plx"],
        "pmra": ["pmra", "pmRA"],
        "pmra_error": ["pmra_error", "e_pmRA"],
        "pmdec": ["pmdec", "pmDE"],
        "pmdec_error": ["pmdec_error", "e_pmDE"],
        "ruwe": ["ruwe", "RUWE"],
        "g": ["phot_g_mean_mag", "Gmag"],
        "bp": ["phot_bp_mean_mag", "BPmag"],
        "rp": ["phot_rp_mean_mag", "RPmag"],
        "bp_rp": ["bp_rp", "BP-RP"],
    }
    for out, names in aliases.items():
        src = next((n for n in names if n in d.columns), None)
        x[out] = pd.to_numeric(d[src], errors="coerce") if src else np.nan
    if x.bp_rp.isna().all():
        x["bp_rp"] = x.bp - x.rp
    x["parallax_over_error"] = x.parallax / x.parallax_error.where(x.parallax_error > 0)
    x["pm_significance"] = np.sqrt(
        (x.pmra / x.pmra_error.where(x.pmra_error > 0)) ** 2 + (x.pmdec / x.pmdec_error.where(x.pmdec_error > 0)) ** 2
    )
    # Gaia parallax is mas: M = m + 5 log10(parallax_mas) - 10.
    x["absolute_g"] = x.g + 5 * np.log10(x.parallax.where(x.parallax > 0)) - 10
    x["bp_g"] = x.bp - x.g
    x["g_rp"] = x.g - x.rp
    for c in [z for z in x.columns if z != "benchmark_id"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    # Explicit missingness lets the model learn availability patterns while HGB
    # retains native NaN routing. Spectroscopic labels/coordinates are excluded.
    base = [c for c in x.columns if c != "benchmark_id"]
    miss = {f"missing__{c}": x[c].isna().astype(float) for c in base if x[c].isna().any()}
    if miss:
        x = pd.concat([x, pd.DataFrame(miss, index=x.index)], axis=1)
    return x


def brier_binary(y, p):
    yy = (np.asarray(y) == "WHITE_DWARF").astype(float)
    return float(np.mean((p - yy) ** 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(a.features)
    if set(raw.star_truth_class) != {"WHITE_DWARF", "NORMAL_STAR"}:
        raise ValueError("STAR truth must contain WHITE_DWARF and NORMAL_STAR")
    x = prepare(raw)
    data = raw[["benchmark_id", "star_truth_class"]].merge(x, on="benchmark_id")
    data["split"] = data.benchmark_id.map(split_for)

    # Interpretable literature baseline. Objects lacking usable parallax/color
    # default to NORMAL_STAR for full-coverage evaluation; coverage is also reported.
    usable = (data.parallax_over_error > 1) & data.absolute_g.notna() & data.bp_rp.notna()
    baseline_wd = usable & (data.absolute_g > 6 + 5 * data.bp_rp)
    baseline = np.where(baseline_wd, "WHITE_DWARF", "NORMAL_STAR")

    feats = [c for c in x.columns if c != "benchmark_id"]
    tr = data.split.eq("train")
    ca = data.split.eq("calibration")
    te = data.split.eq("test")
    base = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        min_samples_leaf=15,
        l2_regularization=1.0,
        random_state=42,
    )
    base.fit(data.loc[tr, feats], data.loc[tr, "star_truth_class"])
    if FrozenEstimator is not None:
        model = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    else:
        model = CalibratedClassifierCV(base, method="sigmoid", cv="prefit")
    model.fit(data.loc[ca, feats], data.loc[ca, "star_truth_class"])

    y = data.loc[te, "star_truth_class"].to_numpy()
    p = model.predict_proba(data.loc[te, feats])
    classes = list(model.classes_)
    pred = np.array(classes)[np.argmax(p, axis=1)]
    wd_i = classes.index("WHITE_DWARF")
    pwd = p[:, wd_i]

    bpred = baseline[te.to_numpy()]
    busable = usable[te].to_numpy()
    hybrid = np.where(busable, bpred, pred)
    conf = np.max(p, axis=1)
    consensus = np.full(len(y), "UNKNOWN", dtype=object)
    agree = busable & (bpred == pred)
    consensus[agree] = pred[agree]
    fallback = (~busable) & (conf >= 0.90)
    consensus[fallback] = pred[fallback]
    classified = consensus != "UNKNOWN"
    metrics = {
        "matched_rows": int(len(data)),
        "split_counts": data.split.value_counts().to_dict(),
        "test_rows": int(te.sum()),
        "feature_count": len(feats),
        "baseline": {
            "rule": "M_G > 6 + 5*(BP-RP) and parallax_over_error > 1",
            "usable_fraction_test": float(busable.mean()),
            "accuracy": float(accuracy_score(y, bpred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, bpred)),
            "f1_white_dwarf": float(f1_score(y, bpred, pos_label="WHITE_DWARF")),
            "precision_white_dwarf": float(precision_score(y, bpred, pos_label="WHITE_DWARF", zero_division=0)),
            "recall_white_dwarf": float(recall_score(y, bpred, pos_label="WHITE_DWARF", zero_division=0)),
            "usable_only": {
                "n": int(busable.sum()),
                "accuracy": float(accuracy_score(y[busable], bpred[busable])),
                "balanced_accuracy": float(balanced_accuracy_score(y[busable], bpred[busable])),
                "f1_white_dwarf": float(f1_score(y[busable], bpred[busable], pos_label="WHITE_DWARF")),
            },
        },
        "consensus": {
            "policy": "classify when HR baseline and calibrated model agree; if HR unavailable use model only at p>=0.90; otherwise UNKNOWN",
            "coverage": float(classified.mean()),
            "classified_rows": int(classified.sum()),
            "accuracy_when_classified": (
                float(accuracy_score(y[classified], consensus[classified])) if classified.any() else None
            ),
            "balanced_accuracy_when_classified": (
                float(balanced_accuracy_score(y[classified], consensus[classified])) if classified.any() else None
            ),
            "macro_f1_when_classified": (
                float(f1_score(y[classified], consensus[classified], average="macro")) if classified.any() else None
            ),
            "unknown_rows": int((~classified).sum()),
        },
        "hybrid": {
            "policy": "literature HR baseline when usable; calibrated learned model only as fallback",
            "accuracy": float(accuracy_score(y, hybrid)),
            "balanced_accuracy": float(balanced_accuracy_score(y, hybrid)),
            "macro_f1": float(f1_score(y, hybrid, average="macro")),
            "wd_precision": float(precision_score(y, hybrid, pos_label="WHITE_DWARF", zero_division=0)),
            "wd_recall": float(recall_score(y, hybrid, pos_label="WHITE_DWARF", zero_division=0)),
            "wd_f1": float(f1_score(y, hybrid, pos_label="WHITE_DWARF", zero_division=0)),
        },
        "learned": {
            "accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, average="macro")),
            "f1_white_dwarf": float(f1_score(y, pred, pos_label="WHITE_DWARF")),
            "precision_white_dwarf": float(precision_score(y, pred, pos_label="WHITE_DWARF", zero_division=0)),
            "recall_white_dwarf": float(recall_score(y, pred, pos_label="WHITE_DWARF", zero_division=0)),
            "log_loss": float(log_loss(y, p, labels=classes)),
            "brier_white_dwarf": brier_binary(y, pwd),
            "on_baseline_usable_subset": {
                "n": int(busable.sum()),
                "accuracy": float(accuracy_score(y[busable], pred[busable])),
                "balanced_accuracy": float(balanced_accuracy_score(y[busable], pred[busable])),
                "macro_f1": float(f1_score(y[busable], pred[busable], average="macro")),
            },
        },
    }

    pd.DataFrame(
        confusion_matrix(y, bpred, labels=CLASSES),
        index=[f"true_{c}" for c in CLASSES],
        columns=[f"pred_{c}" for c in CLASSES],
    ).to_csv(a.out / "baseline_confusion.csv")
    pd.DataFrame(
        confusion_matrix(y, pred, labels=CLASSES),
        index=[f"true_{c}" for c in CLASSES],
        columns=[f"pred_{c}" for c in CLASSES],
    ).to_csv(a.out / "learned_confusion.csv")
    pd.DataFrame(classification_report(y, pred, labels=CLASSES, output_dict=True, zero_division=0)).T.to_csv(
        a.out / "classification_report.csv"
    )
    po = data.loc[te, ["benchmark_id", "star_truth_class"]].copy()
    po["baseline_prediction"] = bpred
    po["learned_prediction"] = pred
    po["hybrid_prediction"] = hybrid
    po["consensus_prediction"] = consensus
    po["p_white_dwarf"] = pwd
    po.to_csv(a.out / "test_predictions.csv", index=False)
    (a.out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    joblib.dump({"model": model, "features": feats, "classes": classes}, a.out / "star_wd_classifier.joblib")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

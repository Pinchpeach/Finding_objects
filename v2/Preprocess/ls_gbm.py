"""Legacy Surveys gradient-boosting STAR / GALAXY / QSO evidence (LS-GBM-001, 2.11.0).

A histogram gradient-boosting classifier (scikit-learn
HistGradientBoostingClassifier; Friedman 2001, Ke et al. 2017) trained on
DESI DR1 spectroscopic classes (benchmark/build_desi_gbm_truth.py; every
benchmark object removed) with the Legacy Surveys Tractor photometry and
morphology DESI targeted on.  Machine-learned star / galaxy / quasar
separation from these features is standard for the DESI imaging (e.g.
Chaussidon et al. 2023 random forest for DESI QSO targets; Zhou et al.
2023 for the LRG/ELG photometry).  Unlike the colour kNN (LS-CKNN-001) it
uses morphological type, depth (r S/N) and five bands together.

Inference needs only numpy: the fitted trees are exported to
``ls_gbm_model.npz`` (benchmark/train_ls_gbm.py) and evaluated here, so the
app does not ship scikit-learn.  Missing features follow the trained
missing-value direction of each split, as in scikit-learn.
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

CLASSES = ("STAR", "GALAXY", "QSO")
MODEL_PATH = Path(__file__).with_name("ls_gbm_model.npz")
P = "desi_legacy_surveys_dr10__"
BANDS = ("g", "r", "z", "w1", "w2")
TYPES = ("PSF", "REX", "EXP", "DEV", "SER")
# Only features the preserved benchmark features also carry, so the model's
# benchmark score is its production score (adding W1 S/N, half-light radius
# and Sersic index raised held-out accuracy by only 0.2 points, 95.6 -> 95.8 %).
FEATURES = ("r_mag", "g_r", "r_z", "z_w1", "w1_w2", "r_w1", "log_snr_r", *[f"type_{t}" for t in TYPES])
# Per-band S/N (train_ls_gbm.py --snr), so the trees can tell a noisy colour
# from a real one at the faint end (photometric errors as classifier inputs;
# Bovy et al. 2011 deconvolve them).  Measured 2026-10-20, not adopted: the
# shipped model uses FEATURES only; inference takes as many columns as the
# model was trained on.
SNR_FEATURES = ("log_snr_g", "log_snr_z", "log_snr_w1", "log_snr_w2")
ALL_FEATURES = FEATURES + SNR_FEATURES


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def features(df: pd.DataFrame, prefix: str = P) -> np.ndarray:
    """Feature matrix from Legacy Surveys Tractor columns (``<prefix>flux_g`` ...).

    Dereddened AB magnitudes 22.5 - 2.5 log10(flux / mw_transmission); a
    non-positive flux gives NaN (handled as missing).  Rows without any LS
    flux are all-NaN and get no evidence.
    """
    mag = {}
    for b in BANDS:
        f = _col(df, f"{prefix}flux_{b}")
        t = _col(df, f"{prefix}mw_transmission_{b}")
        t = np.where(np.isfinite(t) & (t > 0), t, 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            mag[b] = np.where(f > 0, 22.5 - 2.5 * np.log10(f / t), np.nan)
    snr = {}
    for b in BANDS:
        f, iv = _col(df, f"{prefix}flux_{b}"), _col(df, f"{prefix}flux_ivar_{b}")
        with np.errstate(divide="ignore", invalid="ignore"):
            s = f * np.sqrt(np.where(iv > 0, iv, np.nan))
            snr[b] = np.where(s > 0, np.log10(s), np.nan)
    typ = (
        df[f"{prefix}type"].astype(str).str.strip().str.upper().to_numpy()
        if f"{prefix}type" in df
        else np.array([""] * len(df))
    )
    typ = np.where(typ == "GPSF", "PSF", typ)  # DR9 Gaia point source = point-source model
    known = np.isin(typ, TYPES)
    onehot = [np.where(known, (typ == t).astype(float), np.nan) for t in TYPES]
    X = np.column_stack(
        [
            mag["r"],
            mag["g"] - mag["r"],
            mag["r"] - mag["z"],
            mag["z"] - mag["w1"],
            mag["w1"] - mag["w2"],
            mag["r"] - mag["w1"],
            snr["r"],
            *onehot,
            snr["g"],
            snr["z"],
            snr["w1"],
            snr["w2"],
        ]
    )
    return X


@lru_cache(maxsize=1)
def load_model(path: str = str(MODEL_PATH)):
    p = Path(path)
    if not p.exists():
        return None
    m = np.load(p, allow_pickle=False)
    return {k: m[k] for k in m.files}


def raw_scores(X: np.ndarray, model: dict) -> np.ndarray:
    """Sum of tree outputs per class plus the baseline (log-odds space)."""
    n = len(X)
    k = int(model["n_classes"])
    out = np.tile(model["baseline"].reshape(1, k), (n, 1)).astype(float)
    feat, thr, mleft = model["feature"], model["threshold"], model["missing_left"]
    left, right, leaf, value = model["left"], model["right"], model["is_leaf"], model["value"]
    rows = np.arange(n)
    for t, (start, cls) in enumerate(zip(model["tree_start"], model["tree_class"])):
        node = np.full(n, start, dtype=np.int64)
        active = ~leaf[node]
        while active.any():
            idx = node[active]
            x = X[rows[active], feat[idx]]
            go_left = np.where(np.isnan(x), mleft[idx], x <= thr[idx])
            node[active] = np.where(go_left, left[idx], right[idx]) + start
            active = ~leaf[node]
        out[:, cls] += value[node]
    return out


def predict_proba(df: pd.DataFrame, prefix: str = P) -> np.ndarray:
    """(n, 3) STAR/GALAXY/QSO probabilities; NaN rows where there is no LS photometry or no model."""
    model = load_model()
    X = features(df, prefix)
    if model is not None:  # the columns the model was trained on (older models: FEATURES only)
        X = X[:, : len(model["features"])]
    probs = np.full((len(df), len(CLASSES)), np.nan)
    has = np.isfinite(X[:, [0, 6]]).any(axis=1) | np.isfinite(X[:, 3])  # r mag, r S/N or z-W1
    # The model only saw DESI targets, which all have g, r and z imaging
    # (NOBS >= 1 per band; Myers et al. 2023, AJ 165, 50).  A source outside
    # that footprint, e.g. DR10 DECam areas without r (field 340/-30,
    # 2026-10-21), sends every r feature down an untrained missing branch:
    # extended Sersic galaxies scored STAR 1.00.  No evidence there.
    for b in ("g", "r", "z"):
        iv = _col(df, f"{prefix}flux_ivar_{b}")
        if f"{prefix}flux_ivar_{b}" in df:
            has &= np.isfinite(iv) & (iv > 0)
    if model is None or not has.any():
        return probs
    z = raw_scores(X[has], model)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    probs[has] = e / e.sum(axis=1, keepdims=True)
    return probs

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
import os
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
# Tractor extent beyond the discrete TYPE and the stellar-locus distance in
# z-W1 (2.44.0, train_ls_gbm.py --fit): the relative REX-PSF chi^2 gain
# (Chaussidon et al. 2023, ApJ 944, 107; Liu et al. 2025, PASP 137, 084501),
# the half-light-radius significance and z-W1 - [0.8(r-z) - 0.6] (Zhou et al.
# 2023, AJ 165, 58).  Trees split on one feature at a time, so the locus
# distance, a linear combination of two inputs, is given explicitly.
FIT_FEATURES = ("dchisq_rex_rel_log", "size_sig_log", "zw1_excess")
ALL_FEATURES = FEATURES + SNR_FEATURES + FIT_FEATURES


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def features(df: pd.DataFrame, prefix: str = P, names=ALL_FEATURES) -> np.ndarray:
    """Feature matrix (columns ``names``) from Legacy Surveys Tractor columns (``<prefix>flux_g`` ...).

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
    d_psf, d_rex = _col(df, f"{prefix}dchisq_1"), _col(df, f"{prefix}dchisq_2")
    r_e, r_iv = _col(df, f"{prefix}shape_r"), _col(df, f"{prefix}shape_r_ivar")
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.clip((d_rex - d_psf) / np.where(d_psf > 0, d_psf, np.nan), 0, None)
        size = np.log10(1.0 + np.clip(r_e, 0, None) * np.sqrt(np.where(r_iv >= 0, r_iv, np.nan)))
    cols = {
        "r_mag": mag["r"],
        "g_r": mag["g"] - mag["r"],
        "r_z": mag["r"] - mag["z"],
        "z_w1": mag["z"] - mag["w1"],
        "w1_w2": mag["w1"] - mag["w2"],
        "r_w1": mag["r"] - mag["w1"],
        "log_snr_r": snr["r"],
        **{f"type_{t}": v for t, v in zip(TYPES, onehot)},
        "log_snr_g": snr["g"],
        "log_snr_z": snr["z"],
        "log_snr_w1": snr["w1"],
        "log_snr_w2": snr["w2"],
        "dchisq_rex_rel_log": np.log10(rel + 1e-4),
        "size_sig_log": size,
        "zw1_excess": (mag["z"] - mag["w1"]) - (0.8 * (mag["r"] - mag["z"]) - 0.6),
    }
    return np.column_stack([cols[n] for n in names])


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


# Training domain (2.55.0).  The model's training objects (DESI DR1 targets,
# desi_gbm_truth/train.csv.gz, 149,769) with r observed (flux_ivar_r > 0) are
# detected in r: only 4 have flux_r <= 0 with g and z detected (z: also 4),
# and 99.9 % of the detected ones have r S/N >= 3.  The 209 training objects
# with flux_r <= 0 and z > 0 are 206 stars with no r measurement (ivar = 0),
# so the trees' missing-r branch says "bright star without r".  A faint
# source seen only in z (r observed, not detected) went down that branch:
# in a 2' COSMOS search 30 of 92 STAR labels were such sources (26 of them
# extended, REX), and 7 of the 9 r-undetected objects matched to COSMOS2020
# truth in the 2.52.0 A/B are galaxies, all labelled STAR.  The model now
# gives evidence only inside its domain (V2_LS_GBM_DOMAIN):
#   detected  g, r, z observed and r, z detected (flux > 0)   default
#   snr3      as detected, and r S/N >= 3 (the training 0.1 % quantile)
#   observed  g, r, z observed (flux_ivar > 0) only           2.54 and earlier
DOMAINS = ("detected", "snr3", "observed")
R_SNR_MIN = 3.0


def domain() -> str:
    v = os.environ.get("V2_LS_GBM_DOMAIN", "detected").strip().lower() or "detected"
    if v not in DOMAINS:
        raise ValueError(f"V2_LS_GBM_DOMAIN={v!r}; known: {DOMAINS}")
    return v


def in_domain(df: pd.DataFrame, prefix: str = P, which: str | None = None) -> np.ndarray:
    """Rows inside the model's training domain (see DOMAINS)."""
    which = which or domain()
    ok = np.ones(len(df), dtype=bool)
    for b in ("g", "r", "z"):
        if f"{prefix}flux_ivar_{b}" in df:
            iv = _col(df, f"{prefix}flux_ivar_{b}")
            ok &= np.isfinite(iv) & (iv > 0)
    if which == "observed":
        return ok
    for b in ("r", "z"):
        if f"{prefix}flux_{b}" in df:
            ok &= _col(df, f"{prefix}flux_{b}") > 0
    if which == "snr3":
        f, iv = _col(df, f"{prefix}flux_r"), _col(df, f"{prefix}flux_ivar_r")
        with np.errstate(invalid="ignore"):
            ok &= f * np.sqrt(np.where(iv > 0, iv, np.nan)) >= R_SNR_MIN
    return ok


def predict_proba(df: pd.DataFrame, prefix: str = P) -> np.ndarray:
    """(n, 3) STAR/GALAXY/QSO probabilities; NaN rows where there is no LS photometry or no model."""
    model = load_model()
    # the columns the model was trained on, by name
    names = [str(n) for n in model["features"]] if model is not None else list(FEATURES)
    X = features(df, prefix, [*names, "r_mag", "log_snr_r", "z_w1"])
    probs = np.full((len(df), len(CLASSES)), np.nan)
    has = np.isfinite(X[:, -3:]).any(axis=1)  # r mag, r S/N or z-W1
    X = X[:, :-3]
    # The model only saw DESI targets, which all have g, r and z imaging
    # (NOBS >= 1 per band; Myers et al. 2023, AJ 165, 50).  A source outside
    # that footprint, e.g. DR10 DECam areas without r (field 340/-30,
    # 2026-10-21), sends every r feature down an untrained missing branch:
    # extended Sersic galaxies scored STAR 1.00.  No evidence there.
    # 2.55.0: also detected in r and z (in_domain above).
    has &= in_domain(df, prefix)
    if model is None or not has.any():
        return probs
    z = raw_scores(X[has], model)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    probs[has] = e / e.sum(axis=1, keepdims=True)
    return probs

"""One class-prior layer and probability calibration for Stage 5 (2.52.0).

Until 2.51 the balanced-training fusion probabilities P were changed in
three places: the position prior (local Gaia density, else latitude and
Magellanic factors) and the QSO factors (magnitude prior, vetoes) before the
decision, and the faint star:galaxy prior after it, on the label only -- so
``p_*`` and the label could disagree (COSMOS: 1,635 of 28,194 truth objects,
ab_2_51_ls).  ``V2_PRIOR_LAYER=unified`` applies every factor once, to the
probabilities, before the decision:

    Q(c | x)  ~  P(c | e) x pi(c | r, position) / pi_train(c)
               x V(c | x)                                   (evidence vetoes)

the label shift of Saerens, Latinne & Decaestecker (2002, Neural Computation
14, 21: multiply by the new prior over the training prior and renormalise;
Bailer-Jones et al. 2019, MNRAS 490, 5615 for Gaia star / quasar / galaxy
classes; a prior continuous in brightness and latitude as in Jamal &
Bailer-Jones 2024, arXiv:2405.01340).  The position term acts on GALAXY and
QSO, the magnitude term on QSO, and the faint star:galaxy term moves
probability only between STAR and GALAXY (the QSO share is unchanged: the
hierarchical form of the 2.46.0 rule that the faint prior must not create
QSOs or push faint QSOs to STAR, LITERATURE_REMAINING_ERRORS_2026-11-06).

Calibration.  The prior-adjusted probabilities are not calibrated by
construction: the fusion is overconfident at faint magnitudes (sky-spread
SDSS benchmark, class-balanced per r bin: ECE 0.4 % at r < 19, 3.2 % at
r > 21) and the priors are approximations.  ``p_*_calibrated`` applies one
temperature per LS r bin to log Q (temperature scaling, Guo et al. 2017,
ICML, PMLR 70, 1321), fitted on the calibration fields of the independent
validation (probability_calibration.json, benchmark/prior_layer_study.py).
Temperature scaling keeps the order of the classes, so labels do not change;
the decision thresholds and the real-sky purity table of high_confidence.py
stay on the uncalibrated ``primary_confidence`` scale they were measured on.
Class-specific bias terms (Alexandari et al. 2020, ICML) were tried on the
SDSS benchmark and dropped: unstable in sparse bins (r < 18, no LS r).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

LAYERS = ("legacy", "unified")
CALIBRATION = Path(__file__).resolve().parent / "probability_calibration.json"
R_COLUMN = "std_mag__ls_r"
EPS = 1e-12


def layer() -> str:
    v = os.environ.get("V2_PRIOR_LAYER", "legacy").strip().lower() or "legacy"
    if v not in LAYERS:
        raise ValueError(f"V2_PRIOR_LAYER={v!r}; known: {LAYERS}")
    return v


def faint_split(Q: np.ndarray, factors: np.ndarray) -> np.ndarray:
    """Faint star:galaxy prior inside the STAR+GALAXY mass: odds(G:S) x F_G / F_S.

    ``factors`` (n, 2) are faint_class_prior.star_galaxy_factors; rows with a
    NaN are left unchanged.  Columns of Q are STAR, GALAXY, QSO."""
    Q = np.array(Q, dtype=float, copy=True)
    if not len(Q):
        return Q
    ok = np.isfinite(factors).all(1)
    s = Q[ok, 0] + Q[ok, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        odds = (Q[ok, 1] / np.maximum(Q[ok, 0], EPS)) * (factors[ok, 1] / factors[ok, 0])
    g = np.where(np.isfinite(odds), s * odds / (1 + odds), s)
    Q[ok, 1], Q[ok, 0] = g, s - g
    return Q


@lru_cache(maxsize=4)
def load_calibration(path: str | Path = CALIBRATION) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def r_bins(df: pd.DataFrame, edges) -> np.ndarray:
    """Bin index per row: magnitude bins, then one bin for rows without an LS r."""
    r = pd.to_numeric(df[R_COLUMN], errors="coerce").to_numpy(float) if R_COLUMN in df else np.full(len(df), np.nan)
    inner = [float(e) for e in edges[1:-1]]
    b = np.digitize(r, inner)
    return np.where(np.isfinite(r), b, len(inner) + 1)


def calibrate(Q: np.ndarray, df: pd.DataFrame, cal: dict | None = None) -> np.ndarray | None:
    """Temperature-scaled probabilities per LS r bin; None without a calibration file."""
    cal = load_calibration() if cal is None else cal
    if not cal or not len(Q):
        return None
    T = np.asarray(cal["temperature"], float)
    rb = np.clip(r_bins(df, cal["r_edges"]), 0, len(T) - 1)
    a = np.log(np.clip(Q, EPS, 1)) / T[rb][:, None]
    a -= a.max(1, keepdims=True)
    e = np.exp(a)
    return e / e.sum(1, keepdims=True)


def consistent(Pc: np.ndarray, labels, confidence, classes) -> np.ndarray:
    """Make the reported probabilities agree with the label.

    Where a rule other than the fused evidence set the label (2MASS counts,
    BGS test, MYStIX membership, sparse priors, motion, faint prior in the
    legacy layer) and it is not the most probable class, the label gets its
    rule confidence and the other classes share the rest in proportion."""
    out = np.array(Pc, dtype=float, copy=True)
    for i, (lab, conf) in enumerate(zip(labels, confidence)):
        if lab not in classes:
            continue
        k = classes.index(lab)
        if int(out[i].argmax()) == k:
            continue
        c = float(conf) if np.isfinite(conf) else 0.5
        rest = np.delete(out[i], k)
        rest = rest / rest.sum() * (1 - c) if rest.sum() > 0 else np.full(len(rest), (1 - c) / len(rest))
        out[i] = np.insert(rest, k, c)
    return out

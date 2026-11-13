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

Reported probabilities.  In the unified layer ``p_*`` agree with the label:
where a rule other than the fused evidence set it (2MASS counts, BGS test,
MYStIX membership, sparse priors, Gaia motion) the label gets the rule's
confidence and the other classes share the rest (``consistent``);
``likelihood_*`` keep the evidence-and-prior values.

Calibration (measured, benchmark/prior_layer_study.py, 2.52.0).  On the
held-out validation fields (half of the COSMOS deep fields, half of set B)
the unified layer with the COSMOS2020 faint counts has ECE 0.37 % (COSMOS)
and 0.82 % (bright fields), against 1.52 % and 0.82 % for 2.51.  Temperature
scaling per LS r bin on top (Guo et al. 2017) was fitted on the other half
and dropped: ECE +0.04 points (95 % field-bootstrap interval -0.18 to
+0.21), NLL -0.001.  Class-specific bias terms (Alexandari et al. 2020) were
unstable on the sky-spread SDSS benchmark (sparse r bins).
"""

from __future__ import annotations

import os

import numpy as np

LAYERS = ("legacy", "unified")
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


def consistent(Pc: np.ndarray, labels, confidence, classes) -> np.ndarray:
    """Make the reported probabilities agree with the label.

    Where a rule other than the fused evidence set the label (2MASS counts,
    BGS test, MYStIX membership, sparse priors, motion) and it is not the
    most probable class, the label gets its rule confidence and the other
    classes share the rest in proportion."""
    out = np.array(Pc, dtype=float, copy=True)
    if not len(out):
        return out
    k = np.array([classes.index(x) if x in classes else -1 for x in labels])
    fix = (k >= 0) & (out.argmax(1) != k)
    if not fix.any():
        return out
    rows = np.flatnonzero(fix)
    c = np.asarray(confidence, dtype=float)[rows]
    c = np.where(np.isfinite(c), c, 0.5)
    sub = out[rows]
    lab = np.zeros_like(sub, dtype=bool)
    lab[np.arange(len(rows)), k[rows]] = True
    rest = np.where(lab, 0.0, sub)
    tot = rest.sum(1, keepdims=True)
    even = (~lab) / (sub.shape[1] - 1)
    rest = np.where(tot > 0, rest / np.where(tot > 0, tot, 1), even) * (1 - c)[:, None]
    out[rows] = np.where(lab, c[:, None], rest)
    return out

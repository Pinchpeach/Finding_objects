#!/usr/bin/env python3
"""Prior-layer and calibration study (2.52.0, ROADMAP_2026-11-12 item 4).

Input: the per-truth-object probabilities of an A/B run scored by
compare_ab_fields.py (truth_probs_base.csv.gz: p_* final, p_*_training_prior
balanced-training fusion output, magnitudes, positions, decision basis).

What it does
  1. Rebuilds the factors Stage 5 multiplied into the balanced-training
     probabilities P: position L (GALAXY and QSO odds) and the QSO factor M
     (magnitude prior x vetoes) from the ratios of p_* to P, or from the
     prior_* columns when the run wrote them; the faint star:galaxy factors
     from faint_class_prior.py.
  2. Replays the decision of evidence-based objects under
       legacy  -- 2.51 Stage 5: faint prior after the decision, S/G only;
       unified -- one prior layer: position, QSO magnitude, vetoes and the
                  faint star:galaxy odds all inside the probabilities before
                  the decision; the S/G prior moves probability only between
                  STAR and GALAXY (QSO share unchanged, the hierarchical form
                  of the 2.46.0 rule that a faint prior must not create QSOs).
     Override decisions (BGS, 2MASS, MYStIX, sparse priors, motion, host) are
     kept as they were.
  3. Fits temperatures per r bin on the final log-probabilities of the
     calibration fields (Guo et al. 2017; argmax-preserving, so accuracy is
     unchanged) and reports ECE / classwise ECE / NLL / Brier on the test
     fields, by field group and r bin.

Field split (fixed before looking at results): COSMOS odd-numbered fields
and every other set-B field (sorted by name) calibrate; the rest test.

    python v2/benchmark/prior_layer_study.py --truth-probs DIR/truth_probs_base.csv.gz --out OUT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

V2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2 / "Preprocess"))
import faint_class_prior as FAINT  # noqa: E402

C = ["STAR", "GALAXY", "QSO"]
R_EDGES = (-np.inf, 19.0, 20.0, 21.0, 22.0, 23.0, np.inf)  # + one bin for objects without an LS r
MIN_CONF = 0.5
EPS = 1e-12


def split(fields: pd.Series) -> pd.Series:
    """'cal' or 'test' per field (fixed rule, see module doc)."""
    names = sorted(fields.unique())
    bright = [f for f in names if not f.startswith("deep")]
    cal = {f for f in names if f.startswith("deep") and int(f.rsplit("_", 1)[1]) % 2 == 1}
    cal |= set(bright[::2])
    return fields.map(lambda f: "cal" if f in cal else "test")


def r_bin(r: np.ndarray) -> np.ndarray:
    b = np.digitize(r, R_EDGES[1:-1])
    return np.where(np.isfinite(r), b, len(R_EDGES) - 1)


# ---------------------------------------------------------------- metrics
def ece(P, y, nb=15):
    conf, acc = P.max(1), P.argmax(1) == y
    b = np.minimum((conf * nb).astype(int), nb - 1)
    return float(sum((b == k).mean() * abs(acc[b == k].mean() - conf[b == k].mean()) for k in range(nb) if (b == k).any()))


def classwise_ece(P, y, nb=15):
    """Kull et al. 2019 (NeurIPS), mean over classes of |freq - p| in p bins."""
    out = []
    for c in range(P.shape[1]):
        p, t = P[:, c], y == c
        b = np.minimum((p * nb).astype(int), nb - 1)
        out.append(sum((b == k).mean() * abs(t[b == k].mean() - p[b == k].mean()) for k in range(nb) if (b == k).any()))
    return float(np.mean(out))


def metrics(P, y, label=None):
    n = len(y)
    if n == 0:
        return {}
    pt = np.clip(P[np.arange(n), y], EPS, 1)
    d = {
        "n": n,
        "argmax_acc": round(100 * float((P.argmax(1) == y).mean()), 3),
        "ece": round(100 * ece(P, y), 3),
        "cw_ece": round(100 * classwise_ece(P, y), 3),
        "nll": round(float(-np.log(pt).mean()), 4),
        "brier": round(float(((P - np.eye(3)[y]) ** 2).sum(1).mean()), 4),
    }
    if label is not None:
        d["label_acc"] = round(100 * float((label == np.array(C)[y]).mean()), 3)
    return d


# ---------------------------------------------------------------- layers
def rebuild_factors(t: pd.DataFrame):
    """Position L and QSO factor M with p_* = norm(P x (1, L, L*M))."""
    P = np.clip(t[[f"p_{c.lower()}_training_prior" for c in C]].to_numpy(float), EPS, 1)
    Q = np.clip(t[[f"p_{c.lower()}" for c in C]].to_numpy(float), EPS, 1)
    if "prior_position" in t and t.prior_position.notna().any():
        L = t.prior_position.to_numpy(float)
        M = (t.prior_qso_magnitude * t.prior_qso_veto).to_numpy(float)
    else:  # ratios of the stored probabilities (2.51 runs wrote no factors)
        with np.errstate(divide="ignore", invalid="ignore"):
            L = (Q[:, 1] / Q[:, 0]) / (P[:, 1] / P[:, 0])
            M = (Q[:, 2] / Q[:, 0]) / (P[:, 2] / P[:, 0]) / L
    L = np.where(np.isfinite(L) & (L > 0), np.clip(L, 1e-4, 1), 1.0)
    M = np.where(np.isfinite(M) & (M > 0), np.clip(M, 1e-4, 1), 1.0)
    pos = pd.DataFrame({"ra": t.t_ra, "dec": t.t_dec, FAINT.R_COLUMN: t.get(FAINT.R_COLUMN)})
    F = FAINT.star_galaxy_factors(pos)
    return P, L, M, F


def prior_layer(P, L, M):
    Q = P * np.c_[np.ones(len(P)), L, L * M]
    return Q / Q.sum(1, keepdims=True)


def faint_split(Q, F):
    """Hierarchical S:G prior: odds(G:S) x F_G/F_S inside the S+G mass."""
    Q = Q.copy()
    ok = np.isfinite(F).all(1)
    s = Q[ok, 0] + Q[ok, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        odds = (Q[ok, 1] / np.maximum(Q[ok, 0], EPS)) * (F[ok, 1] / F[ok, 0])
    g = s * odds / (1 + odds)
    Q[ok, 1], Q[ok, 0] = g, s - g
    return Q


def legacy_faint(Q, F, label):
    """2.46.0 post-decision rule on S/G-labelled evidence objects."""
    out = label.copy()
    for i in np.flatnonzero(np.isfinite(F).all(1) & np.isin(label, ["STAR", "GALAXY"])):
        w = Q[i].copy()
        w[0] *= F[i, 0]
        w[1] *= F[i, 1]
        w /= w.sum()
        k = int(w.argmax())
        if w[k] >= MIN_CONF and C[k] != "QSO":
            out[i] = C[k]
    return out


def decide(Q, base_label, basis, status):
    """Evidence decisions from Q; overrides and abstentions for other reasons kept."""
    lab = np.array(base_label, dtype=object).copy()
    ev = (basis.fillna("evidence").isin(["evidence", "", "nan"]).to_numpy()) & np.isin(
        status, ["CLASSIFIED", "LOW_CONFIDENCE"]
    )
    conf = Q.max(1)
    top = np.array(C)[Q.argmax(1)]
    lab[ev] = np.where(conf[ev] >= MIN_CONF, top[ev], "UNKNOWN")
    return lab


# ---------------------------------------------------------------- calibration
def fit_temperatures(logQ, y, rb, nbins):
    T = np.ones(nbins)
    for b in range(nbins):
        k = rb == b
        if k.sum() < 50:
            continue

        def nll(lt):
            a = logQ[k] / np.exp(lt)
            a = a - a.max(1, keepdims=True)
            lp = a - np.log(np.exp(a).sum(1, keepdims=True))
            return -lp[np.arange(k.sum()), y[k]].mean()

        T[b] = float(np.exp(minimize_scalar(nll, bounds=(-2, 2), method="bounded").x))
    return T


def apply_temperatures(logQ, rb, T):
    a = logQ / T[rb][:, None]
    a = a - a.max(1, keepdims=True)
    e = np.exp(a)
    return e / e.sum(1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth-probs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(a.truth_probs, low_memory=False)
    t = t[t.t_truth.isin(C) & t.p_star_training_prior.notna() & t.p_star.notna()].reset_index(drop=True)
    y = t.t_truth.map({c: i for i, c in enumerate(C)}).to_numpy()
    t["split"] = split(t.field)
    t["group"] = np.where(t.field.str.startswith("deep"), "cosmos", "bright")
    r = pd.to_numeric(t.get(FAINT.R_COLUMN), errors="coerce").to_numpy(float)
    rb = r_bin(r)
    nb = len(R_EDGES)  # magnitude bins + no LS r
    P, L, M, F = rebuild_factors(t)
    status = t.classification_status.fillna("").to_numpy()
    basis = t.get("classification_basis", pd.Series("evidence", index=t.index))
    Q_legacy = prior_layer(P, L, M)
    stored = np.clip(t[["p_star", "p_galaxy", "p_qso"]].to_numpy(float), EPS, 1)
    rebuild_err = float(np.abs(Q_legacy - stored).max())
    lab_legacy_q = decide(Q_legacy, t.ours.to_numpy(), basis, status)
    lab_legacy = legacy_faint(Q_legacy, F, lab_legacy_q)
    Q_uni = faint_split(Q_legacy, F)
    lab_uni = decide(Q_uni, t.ours.to_numpy(), basis, status)
    cal = (t.split == "cal").to_numpy()
    T = fit_temperatures(np.log(np.clip(Q_uni, EPS, 1))[cal], y[cal], rb[cal], nb)
    Q_cal = apply_temperatures(np.log(np.clip(Q_uni, EPS, 1)), rb, T)
    rows = []
    variants = {
        "stored (2.51 p_*, label)": (stored, t.ours.to_numpy()),
        "replayed legacy": (Q_legacy, lab_legacy),
        "unified prior layer": (Q_uni, lab_uni),
        "unified + temperature": (Q_cal, lab_uni),
        "balanced training P": (P, None),
    }
    for sp in ("cal", "test"):
        for grp in ("all", "cosmos", "bright"):
            k = (t.split == sp).to_numpy() & ((t.group == grp).to_numpy() if grp != "all" else True)
            for name, (Qv, lab) in variants.items():
                rows.append({"split": sp, "group": grp, "variant": name, **metrics(Qv[k], y[k], None if lab is None else lab[k])})
    res = pd.DataFrame(rows)
    by_r = []
    for b in range(nb):
        k = (t.split == "test").to_numpy() & (rb == b)
        if not k.any():
            continue
        for name in ("stored (2.51 p_*, label)", "unified prior layer", "unified + temperature"):
            Qv, lab = variants[name]
            by_r.append({"r_bin": b, "variant": name, **metrics(Qv[k], y[k], lab[k])})
    by_r = pd.DataFrame(by_r)
    pd.set_option("display.width", 220)
    print(f"rebuild check: max |legacy layer - stored p_*| = {rebuild_err:.2e}")
    print(f"label agreement replayed legacy vs stored: {100 * (lab_legacy == t.ours.to_numpy()).mean():.3f} %")
    print(res.to_string(index=False))
    print("\ntest fields by LS r bin", list(R_EDGES))
    print(by_r.to_string(index=False))
    print("temperatures per r bin:", [round(float(x), 3) for x in T])
    k = (t.split == "test").to_numpy()
    ok_s, ok_u = t.ours.to_numpy()[k] == t.t_truth.to_numpy()[k], lab_uni[k] == t.t_truth.to_numpy()[k]
    from field_stats import mcnemar

    p, n01, n10 = mcnemar(ok_u, ok_s)
    print(f"test fields, unified vs stored labels: unified only right {n01}, stored only right {n10}, exact McNemar p = {p:.3g}")
    res.to_csv(a.out / "prior_layer_metrics.csv", index=False)
    by_r.to_csv(a.out / "prior_layer_by_r.csv", index=False)
    (a.out / "temperatures.json").write_text(json.dumps({"r_edges": [None if not np.isfinite(e) else e for e in R_EDGES],
                                                         "temperature": [round(float(x), 4) for x in T]}, indent=1) + "\n")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()

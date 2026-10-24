#!/usr/bin/env python3
"""Real-sky purity / completeness of the coarse classes and the confidence
thresholds of the high-confidence flag (2.36.0).

The truth samples are not the sky: the independent fields' spectroscopic
surveys target stars (LAMOST, RAVE), emission-line galaxies (WiggleZ) or
UV-excess quasars (2QZ), and the DESI test set has equal numbers per class
in each magnitude bin.  Purity measured on them describes their mix, not a
search field, where faint galaxies outnumber quasars ~50:1.  The recall
matrix P(predicted c, confidence >= t | true class, magnitude bin) does not
depend on the class mix, so (Bayes, as in e.g. Bovy et al. 2011 for
quasar-target purity):

  1. R_b(t)  from the truth samples per magnitude bin b (independent blind
     fields for the bright bins, the DESI DR1 test set for the faint ones);
  2. the true class counts n_b of the 18 search fields.  Quasars are fixed
     from published number counts (QSO_DENSITY x field area): faint
     galaxies outnumber them so much that a 2-5 % galaxy leak explains every
     QSO prediction, and a free fit drives the quasar fraction to 0.  Stars
     and galaxies then follow from the field's predicted classes,
     f_b = n_b . R_b(0.5), solved for n_star, n_galaxy >= 0 (NNLS);
  3. purity_b(c, t) = pi_bc R_b,cc(t) / sum_s pi_bs R_b,sc(t),
     completeness_b(c, t) = R_b,cc(t); field totals weight bins by the
     estimated true counts.

Uncertainty: 200 bootstrap resamples of the truth objects (16-84 %);
rates are Jeffreys estimates, so an unseen leak keeps a finite upper value.

The high-confidence threshold of class c in bin b is the lowest confidence
t whose purity is >= TARGET in >= 84 % of the resamples (a one-sided 1-sigma
lower bound), with at least MIN_TRUTH truth objects predicted c there;
no such t -> no photometric high-confidence objects of c in that bin.

    python v2/benchmark/natural_purity.py --desi-pred PRED_CSV --out DIR [--write]
(PRED_CSV: rule_baseline_test_predictions.csv of evaluate_rule_baseline.py
on the DESI external test set.)  --write stores the thresholds in
v2/Classifier/high_confidence.json.

The per-region products live on the validation-data branch (233 MB);
fetch them first: v2/benchmark/independent_fields/README.md.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls

B = Path(__file__).resolve().parent
C = ["STAR", "GALAXY", "QSO"]
EDGES = [-np.inf, 18.0, 20.0, 21.0, 22.0, np.inf]
LABELS = ["r<=18", "18-20", "20-21", "21-22", "r>22"]
THR = [0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999]
TARGET = 0.98
MIN_TRUTH = 20
NBOOT = 200
# Quasar surface density per magnitude bin (deg^-2), from the cumulative
# counts N(<r) ~ 2, 20, 50, 120, 230 at r = 18, 20, 21, 22, 23: the
# variability-selected (near-complete) Stripe 82 sample of Palanque-
# Delabrouille et al. 2016 (A&A 587, A41: 13,876 quasars to g < 22.5 over
# 94.5 deg^2 = 147 deg^-2) and the DESI quasar density to r < 23
# (~230 deg^-2, DESI Collaboration 2016, arXiv:1611.00036); bright end
# from the SDSS DR7 quasar counts (Schneider et al. 2010; ~10 deg^-2 to i < 19.1).
QSO_DENSITY = {"r<=18": 2.0, "18-20": 18.0, "20-21": 30.0, "21-22": 70.0, "r>22": 110.0}
MAG_COLUMNS = ("std_mag__ls_r", "std_mag__ps1_r", "std_mag__sdss_r", "gaia_dr3__phot_g_mean_mag")


def magnitude(d):
    r = pd.Series(np.nan, index=d.index)
    for c in MAG_COLUMNS:
        if c in d:
            r = r.fillna(pd.to_numeric(d[c], errors="coerce"))
    return r


def magnitude_bin(r):
    return pd.cut(pd.to_numeric(r, errors="coerce"), EDGES, labels=LABELS)


def truth_samples(desi_pred):
    """(truth, predicted class or None, confidence, magnitude bin) of every truth object."""
    import score_independent_fields as sf

    bench = sf.benchmark_positions()
    parts = []
    for fdir in sorted(p for p in (B / "independent_fields").iterdir() if (p / "objects_blind.csv.gz").exists()):
        m, _ = sf.field_matches(fdir, "blind", bench)
        ok = m.classification_status.eq("CLASSIFIED")
        parts.append(
            pd.DataFrame(
                {
                    "truth": m.t_truth,
                    "pred": m.ours.where(ok),
                    "conf": m.primary_confidence,
                    "bin": magnitude_bin(magnitude(m)),
                    "sample": "independent",
                }
            )
        )
    p = pd.read_csv(desi_pred)
    p = p[p.split.eq("test")] if "split" in p else p
    t = pd.read_csv(B / "desi_external" / "truth.csv", usecols=["benchmark_id", "r_mag"])
    p = p.merge(t, on="benchmark_id", how="left")
    ok = p.classification_status.eq("CLASSIFIED")
    parts.append(
        pd.DataFrame(
            {
                "truth": p.truth_class,
                "pred": p.primary_class.where(ok),
                "conf": p.primary_confidence,
                "bin": magnitude_bin(p.r_mag),
                "sample": "desi_test",
            }
        )
    )
    s = pd.concat(parts, ignore_index=True)
    return s[s.truth.isin(C) & s.bin.notna()].reset_index(drop=True)


def field_objects():
    """Classified top-level objects of the 18 blind field runs."""
    out = []
    for fdir in sorted(p for p in (B / "independent_fields").iterdir() if (p / "objects_blind.csv.gz").exists()):
        o = pd.read_csv(fdir / "objects_blind.csv.gz", low_memory=False)
        if "parent_object_id" in o:
            o = o[o.parent_object_id.isna()]
        o = o[o.classification_status.eq("CLASSIFIED")]
        out.append(pd.DataFrame({"pred": o.primary_class, "conf": o.primary_confidence, "bin": magnitude_bin(magnitude(o))}))
    return pd.concat(out, ignore_index=True)


def recall(s, t):
    """R[true, pred] = P(pred, conf >= t | true) in sample s, as the Jeffreys
    estimate (k + 1/2) / (n + 1): a leak never seen among n truth objects is
    not zero (with ~75 faint galaxies per quasar, even 1/200 matters)."""
    R = np.zeros((3, 3))
    for i, tc in enumerate(C):
        g = s[s.truth.eq(tc)]
        if len(g):
            for j, pc in enumerate(C):
                R[i, j] = (((g.pred == pc) & (g.conf >= t)).sum() + 0.5) / (len(g) + 1)
    return R


def true_counts(f_counts, R05, n_qso):
    """True (star, galaxy, quasar) counts: quasars fixed, stars and galaxies
    with f ~ n . R(0.5), n >= 0."""
    resid = f_counts - n_qso * R05[2]
    ng, _ = nnls(R05[:2].T, resid)
    return np.array([ng[0], ng[1], n_qso])


def estimate(s, F, area):
    """{bin: {"pi", "n_true", rows per class x threshold}} for one (re)sample."""
    out = {}
    for b in LABELS:
        sb, fb = s[s.bin.eq(b)], F[F.bin.eq(b)]
        if not len(sb) or not len(fb):
            continue
        R05 = recall(sb, 0.5)
        fc = np.array([(fb.pred == c).sum() for c in C], float)
        n = true_counts(fc, R05, QSO_DENSITY[b] * area)
        n_true = n.sum()
        pi = n / max(n_true, 1e-9)
        rows = {}
        for t in THR:
            R = recall(sb, t)
            for j, c in enumerate(C):
                tp = pi[j] * R[j, j]
                allp = pi @ R[:, j]
                rows[(c, t)] = (tp / allp if allp > 0 else np.nan, R[j, j], n_true * allp, int(((sb.pred == c) & (sb.conf >= t)).sum()))
        out[b] = {"pi": pi, "n_true": n_true, "rows": rows}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desi-pred", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="store the thresholds in v2/Classifier/high_confidence.json")
    a = ap.parse_args()
    import sys

    sys.path.insert(0, str(B))
    s, F = truth_samples(a.desi_pred), field_objects()
    area = sum(np.pi * (json.loads(f.read_text())["radius_arcmin"] / 60) ** 2 for f in (B / "independent_fields").glob("*/field.json"))
    est = estimate(s, F, area)
    rng = np.random.default_rng(1)
    groups = list(s.groupby(["bin", "truth"], observed=True).indices.values())
    boots = []
    for _ in range(NBOOT):  # resample within (bin, true class): the recall matrix rows
        idx = np.concatenate([rng.choice(g, len(g)) for g in groups])
        boots.append(estimate(s.iloc[idx], F, area))
    rows, thresholds, lower = [], {}, {}
    for b, e in est.items():
        for c in C:
            chosen = None
            for t in THR:
                pur, comp, npred, ntruth = e["rows"][(c, t)]
                bp = np.array([x[b]["rows"][(c, t)][0] for x in boots if b in x])
                lo, hi = np.nanpercentile(bp, [16, 84]) if np.isfinite(bp).any() else (np.nan, np.nan)
                ok = ntruth >= MIN_TRUTH and np.nanmean(bp >= TARGET) >= 0.84
                if ok and chosen is None:
                    chosen = t
                    lower.setdefault(b, {})[c] = round(float(lo), 4)
                rows.append(dict(bin=b, cls=c, thr=t, pi=round(float(e["pi"][C.index(c)]), 4), purity=pur, purity_lo=lo, purity_hi=hi, completeness=comp, field_n=npred, truth_n=ntruth))
            thresholds.setdefault(b, {})[c] = chosen
    r = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out / "natural_purity.csv", index=False)
    # field totals over bins (estimated true counts as weights)
    tot = []
    for c in C:
        for t in THR:
            g = r[(r.cls == c) & (r.thr == t)]
            w = g.field_n.fillna(0)
            tp = (g.purity.fillna(0) * w).sum()
            tot.append(dict(cls=c, thr=t, purity=tp / w.sum() if w.sum() else np.nan, field_n=w.sum()))
    tot = pd.DataFrame(tot)
    tot.to_csv(a.out / "natural_purity_total.csv", index=False)
    pd.set_option("display.width", 200)
    print("true class mix per bin:", {b: np.round(e["pi"], 3).tolist() for b, e in est.items()})
    print(r.round(4).to_string(index=False))
    print(tot.round(4).to_string(index=False))
    print("high-confidence thresholds:", json.dumps(thresholds))
    if a.write:
        doc = {
            "description": "Confidence threshold per magnitude bin and class above which the estimated real-sky purity is "
            f">= {TARGET} (bootstrap 84 % one-sided); null = no photometric high-confidence objects. "
            "Built by v2/benchmark/natural_purity.py (2.36.0).",
            "target_purity": TARGET,
            "magnitude_columns": list(MAG_COLUMNS),
            "edges": [None if not np.isfinite(x) else x for x in EDGES],
            "labels": LABELS,
            "thresholds": thresholds,
            "purity_lower_bound": lower,
        }
        (B.parent / "Classifier" / "high_confidence.json").write_text(json.dumps(doc, indent=1) + "\n")


if __name__ == "__main__":
    main()

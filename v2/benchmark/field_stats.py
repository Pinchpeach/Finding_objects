"""Statistics for field-level scores (2.51.0).

The scientific review (SCIENTIFIC_REVIEW_2026-11-11.md 3.4 and 6.6) found the
reported numbers had no uncertainties, no paired test and no trivial
baselines.  Objects in one field share the field's depth, extinction and
crowding, so they are not independent: the confidence interval resamples
whole fields (cluster bootstrap; Field 2001, Davison & Hinkley 1997 sec. 3.8).
Paired variants on the same truth objects are compared with the exact
McNemar test on the discordant pairs (McNemar 1947; Dietterich 1998 for
classifier comparison).  Balanced accuracy is the mean per-class recall
(Brodersen et al. 2010), which a STAR-dominated field mix cannot inflate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest

C = ["STAR", "GALAXY", "QSO"]


def _acc(ok):
    return float(np.mean(ok)) if len(ok) else np.nan


def _bal(pred, truth):
    r = [float(np.mean(pred[truth == c] == c)) for c in C if (truth == c).any()]
    return float(np.mean(r)) if r else np.nan


def field_bootstrap(m, stat, n=1000, seed=0):
    """95 % percentile interval of stat(frame) over fields resampled with replacement."""
    if m.empty:
        return (np.nan, np.nan)
    groups = [g for _, g in m.groupby("field", sort=False)]
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        vals.append(stat(pd.concat([groups[k] for k in pick], ignore_index=True)))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))


def mcnemar(ok_a, ok_b):
    """Exact two-sided McNemar p for paired correctness vectors (b = a right / b wrong)."""
    a, b = np.asarray(ok_a, bool), np.asarray(ok_b, bool)
    n01, n10 = int((a & ~b).sum()), int((~a & b).sum())
    if n01 + n10 == 0:
        return 1.0, n01, n10
    return float(binomtest(n01, n01 + n10, 0.5).pvalue), n01, n10


def dsc_label(m):
    g = lambda c: pd.to_numeric(m[c], errors="coerce") if c in m else pd.Series(np.nan, index=m.index)
    ps = sum(g(f"gaia_dr3__classprob_dsc_combmod_{k}").fillna(0) for k in ("star", "whitedwarf", "binarystar"))
    d = pd.DataFrame({"STAR": ps, "GALAXY": g("gaia_dr3__classprob_dsc_combmod_galaxy"), "QSO": g("gaia_dr3__classprob_dsc_combmod_quasar")})
    return d.fillna(-1).idxmax(axis=1).where(g("gaia_dr3__classprob_dsc_combmod_quasar").notna())


def summary(m, nboot=1000):
    """Accuracy with field-bootstrap CI, balanced accuracy, per-class recall and
    precision, and the majority-class and Gaia DSC baselines.  m needs columns
    field, t_truth, ours."""
    if m.empty:
        return {}
    pred, truth = m.ours.astype(str), m.t_truth.astype(str)
    ok = (pred == truth).to_numpy()
    r = dict(n_fields=int(m.field.nunique()), acc=round(100 * _acc(ok), 3), bal_acc=round(100 * _bal(pred, truth), 2))
    lo, hi = field_bootstrap(m, lambda d: _acc(d.ours.astype(str) == d.t_truth.astype(str)), nboot)
    r.update(acc_lo=round(100 * lo, 2), acc_hi=round(100 * hi, 2))
    lo, hi = field_bootstrap(m, lambda d: _bal(d.ours.astype(str), d.t_truth.astype(str)), nboot, seed=1)
    r.update(bal_lo=round(100 * lo, 2), bal_hi=round(100 * hi, 2))
    for c in C:
        p = pred == c
        r[f"precision_{c}"] = round(100 * float((truth[p] == c).mean()), 2) if p.any() else None
    maj = truth.value_counts().idxmax()
    r["baseline_majority"] = f"{maj} {100 * float((truth == maj).mean()):.2f}"
    d = dsc_label(m)
    has = d.notna()
    if has.any():
        r["baseline_dsc"] = round(100 * float((d[has] == truth[has]).mean()), 2)
        r["ours_on_dsc"] = round(100 * float((pred[has] == truth[has]).mean()), 2)
        r["dsc_coverage"] = round(100 * float(has.mean()), 1)
    return r

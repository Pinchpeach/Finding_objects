#!/usr/bin/env python3
"""Is the association posterior a probability?  Reliability of three scores against COSMOS2020 (2.60.9, step 3).

    python posterior_calibration.py --rows rows_diag.csv.gz --assoc-dir DIR --out DIR

``rows`` is the per-row table of ``measure_association.py`` (columns ``lr`` = likelihood ratio of the joined candidate,
``lr_sum`` = sum over the accepted candidates, ``outcome`` correct / false / unknown, ``conf`` = the pipeline's
``association_confidence``).  Scores compared, for every low-resolution row that joined an object whose truth is known:

  current   L / (L + 1)                       the 2.48.0 posterior (Budavari & Szalay 2008; the ``match-time`` value)
  conf      association_confidence            what the pipeline stores: max(match-time posterior, posterior against the
                                              object's final anchor)
  fleuren   L / (sum L_i + 1 - Q0)            Fleuren et al. 2012 (MNRAS 423, 2407, eq. 6); Q0 by blank counting
  fleuren_q Q0 L / (Q0 sum L_i + 1 - Q0)      the same with L scaled by Q0: q(m) of eq. 4 is normalised to Q0, and with
                                              q(m)/n(m) taken as Q0/rho the prior odds of "a counterpart exists" are Q0/(1-Q0)
  fleuren1  L / sum L_i                       the same with Q0 = 1 (every row has a counterpart)

Q0 (Fleuren et al. 2012, sec. 3.3: ``1 - Q0 = (blank source circles) / (blank random circles)``): for a catalogue X the
share of its rows with no resolving-catalogue row within r, divided by the same share of random positions in the field.
r is where the ratio is flat enough to read: it is printed for several radii and the median of r >= 2'' is used.

Per catalogue and half: reliability table (bins of the score: rows, observed correct fraction, mean score, Wilson
interval), Brier score, expected calibration error, and the self-consistency of Budavari & Szalay (2008): the sum of the
scores of the joined rows against the number of correct associations (sum P = N*).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_association as M  # noqa: E402

BINS = [0.0, 0.5, 0.8, 0.9, 0.95, 0.99, 0.999, 1.0001]
RADII = (1.5, 2.0, 3.0, 4.0, 5.0, 6.0)


def q0_per_field(assoc: pd.DataFrame, field_radius_arcmin: float, centre, n_random=20000, seed=7) -> dict:
    """{catalogue: (Q0, {r: 1 - Q0 at r})} by blank counting against the resolving catalogues of the field."""
    res = assoc[assoc.catalog.isin(M.RESOLVING)]
    sky = M.Sky(res.ra.to_numpy(float), res.dec.to_numpy(float))
    rng = np.random.default_rng(seed)
    # random positions inside the field, kept 0.5' from the edge so that no circle is cut by the boundary
    rr = (field_radius_arcmin - 0.5) * np.sqrt(rng.random(n_random))
    th = 2 * np.pi * rng.random(n_random)
    ra0, dec0 = centre
    rdec = dec0 + rr / 60.0 * np.sin(th)
    rra = ra0 + rr / 60.0 * np.cos(th) / np.cos(np.radians(dec0))
    out = {}
    for cat in M.LOWRES:
        x = assoc[assoc.catalog == cat]
        if x.empty:
            continue
        # keep to the same inner region as the random points
        sep = np.hypot((x.ra - ra0) * np.cos(np.radians(dec0)), x.dec - dec0) * 60.0
        x = x[sep <= field_radius_arcmin - 0.5]
        vals = {}
        for r in RADII:
            blank_src = np.mean([len(i) == 0 for i, _ in sky.within(x.ra.to_numpy(float), x.dec.to_numpy(float), r)])
            blank_rnd = np.mean([len(i) == 0 for i, _ in sky.within(rra, rdec, r)])
            vals[r] = float(blank_src / blank_rnd) if blank_rnd > 0.02 else np.nan
        ok = [v for r, v in vals.items() if r >= 2.0 and np.isfinite(v)]
        out[cat] = (float(np.clip(1.0 - np.median(ok), 0.0, 1.0)) if ok else np.nan, vals)
    return out


def reliability(p: np.ndarray, y: np.ndarray, label: str) -> pd.DataFrame:
    rows = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p >= lo) & (p < hi)
        if not m.any():
            continue
        k, n = int(y[m].sum()), int(m.sum())
        lo_w, hi_w = M.wilson(k, n)
        rows.append(dict(score=label, bin=f"[{lo:g},{min(hi, 1):g})", n=n, correct=k, observed_pct=round(100 * k / n, 2),
                         mean_score_pct=round(100 * float(p[m].mean()), 2), wilson=f"{lo_w:.1f}-{hi_w:.1f}"))  # fmt: skip
    return pd.DataFrame(rows)


def summarise(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.clip(p, 0.0, 1.0)
    brier = float(np.mean((p - y) ** 2))
    ece = 0.0
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p >= lo) & (p < hi)
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return dict(n=len(p), brier=round(brier, 5), ece_pct=round(100 * float(ece), 3), sum_p=round(float(p.sum()), 1),
                n_correct=int(y.sum()), sum_p_over_n=round(float(p.sum() / max(y.sum(), 1)), 4))  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--assoc-dir", type=Path, required=True)
    ap.add_argument("--fields-root", type=Path, required=True, help="for field.json (centre)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--include-no-counterpart",
        action="store_true",
        help="also the joined rows that have no truth counterpart (counted as wrong); COSMOS2020 lacks the saturated "
        "stars, so these include real stars: the default (off) conditions on a counterpart in the truth",
    )
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(HERE / "fields_split.csv").set_index("name")
    d = pd.read_csv(a.rows)
    q0s = {}
    import json

    for name in split.index:
        info = json.loads((a.fields_root / name / "field.json").read_text())
        assoc = pd.read_csv(a.assoc_dir / name / "source_association.csv", low_memory=False)
        q0s[name] = q0_per_field(assoc, info["radius_arcmin"], (info["ra"], info["dec"]))
    q0rows = [dict(field=n, split=split.split[n], catalog=c, q0=v[0], **{f"one_minus_q0_r{r}": v[1][r] for r in RADII})
              for n, cats in q0s.items() for c, v in cats.items()]  # fmt: skip
    pd.DataFrame(q0rows).to_csv(a.out / "q0_by_field.csv", index=False)
    d["split"] = d.field.map(split.split)
    d["q0"] = [q0s[f].get(c, (np.nan,))[0] for f, c in zip(d.field, d.catalog)]
    kinds = ["correct", "false"] + (["no_counterpart"] if a.include_no_counterpart else [])
    k = d[d.joined & d.outcome.isin(kinds) & d.lr.notna() & d.lr_sum.notna()].copy()
    k["y"] = (k.outcome == "correct").astype(float)
    k["current"] = k.lr / (1.0 + k.lr)
    k["fleuren"] = k.lr / (k.lr_sum + (1.0 - k.q0.fillna(1.0)))
    k["fleuren1"] = k.lr / k.lr_sum
    q = k.q0.fillna(1.0)
    k["fleuren_q"] = q * k.lr / (q * k.lr_sum + (1.0 - q))  # prior odds Q0/(1-Q0): L scaled by the counterpart share
    k["conf_"] = k.conf.astype(float)
    tabs, sums = [], []
    for cat in M.LOWRES:
        for half in ("calibration", "test", "all"):
            x = k[(k.catalog == cat) & ((k.split == half) | (half == "all"))]
            if len(x) < 30:
                continue
            for sc in ("current", "conf_", "fleuren", "fleuren_q", "fleuren1"):
                t = reliability(x[sc].to_numpy(), x.y.to_numpy(), sc)
                t.insert(0, "half", half)
                t.insert(0, "catalog", cat)
                tabs.append(t)
                sums.append(dict(catalog=cat, half=half, score=sc, **summarise(x[sc].to_numpy(), x.y.to_numpy())))
    tag = "unconditional" if a.include_no_counterpart else "conditional"  # 2.60.11: the names of results_2026-11-25/
    pd.concat(tabs).to_csv(a.out / f"reliability_tables_{tag}.csv", index=False)
    s = pd.DataFrame(sums)
    s.to_csv(a.out / f"calibration_summary_{tag}.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(pd.DataFrame(q0rows).groupby("catalog")[["q0"] + [f"one_minus_q0_r{r}" for r in RADII]].median().round(3))
        print(s[s.half != "calibration"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Acceptance threshold at a target false-association rate (NWAY p_any
calibration, Salvato et al. 2018, MNRAS 473, 4937, sec. 2.4 and the
nway-calibrate-cutoff.py script).

NWAY shifts the secondary catalogue so that no true counterpart remains and
reads the false-match rate as the fraction of shifted sources that still pass
a cut.  The A/B workflow (experiment-ab-fields.yml) dumps, for AllWISE and
2MASS PSC, every row's association posterior in the real run and in a copy
moved by 2' (assoc_pairs.csv.gz).  For each catalogue this script reports

  false(t) = shifted rows matched with posterior >= t / shifted rows
  kept(t)  = real rows matched with posterior >= t / real rows matched

and the smallest t with false(t) <= TARGET.  Output: Preprocess/assoc_min_posterior.csv.

2.49.0: AllWISE and 2MASS are moved together, so a shifted WISE row still
finds its own shifted 2MASS row; only matches to an unshifted anchor
(object_anchor_catalog not AllWISE / 2MASS) count as false.  The membership
posterior saturates near 1 for AllWISE (its 6" PSF makes the positional
density small against the sky density), so the cut is on the normalised
separation instead: the largest k with false(sep/sigma <= k) <= TARGET.

    calibrate_assoc_threshold.py PAIRS_CSV [--variant base] [--target 0.05]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "Preprocess" / "assoc_max_nsep.csv"
SHIFTED = ("AllWISE", "2MASS PSC")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", type=Path)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--target", type=float, default=0.05)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    d = pd.read_csv(a.pairs, low_memory=False)
    d = d[d.variant == a.variant]
    grid = np.round(np.arange(0.25, 6.01, 0.25), 2)
    rows = []
    for cat, g in d.groupby("catalog"):
        real, sh = g[g.run == "real"], g[g.run == "shifted"]
        rm = pd.to_numeric(real[real.association_status == "matched"].normalized_separation, errors="coerce")
        m = sh[(sh.association_status == "matched") & ~sh.object_anchor_catalog.isin(SHIFTED)]
        sm = pd.to_numeric(m.normalized_separation, errors="coerce")
        best = None
        print(f"\n{cat}: real rows {len(real)} (matched {len(rm)}), shifted rows {len(sh)} (false matches {len(sm)})")
        for k in grid:
            false = (sm <= k).sum() / max(len(sh), 1)
            kept = (rm <= k).sum() / max(len(rm), 1)
            print(f"  sep/sigma <= {k:4.2f}  false {100 * false:5.1f} %  kept real matches {100 * kept:5.1f} %")
            if false <= a.target:
                best = (k, false, kept)
        if best:
            print(f"  -> largest cut with false <= {100 * a.target:.0f} %: {best[0]}  (false {100 * best[1]:.1f} %, kept {100 * best[2]:.1f} %)")
            rows.append(dict(catalog=cat, max_nsep=float(best[0]), false_rate=round(float(best[1]), 4),
                             kept_real=round(float(best[2]), 4), target=a.target))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    if a.write and len(t):
        t.to_csv(OUT, index=False)
        print("wrote", OUT)


if __name__ == "__main__":
    main()

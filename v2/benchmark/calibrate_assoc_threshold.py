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

    calibrate_assoc_threshold.py PAIRS_CSV [--variant base] [--target 0.05]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "Preprocess" / "assoc_min_posterior.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", type=Path)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--target", type=float, default=0.05)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    d = pd.read_csv(a.pairs, low_memory=False)
    d = d[d.variant == a.variant]
    grid = np.r_[0.0, np.logspace(-4, 0, 81)]
    rows = []
    for cat, g in d.groupby("catalog"):
        real, sh = g[g.run == "real"], g[g.run == "shifted"]
        rm = real[real.association_status == "matched"].association_confidence.astype(float)
        sm = sh[sh.association_status == "matched"].association_confidence.astype(float)
        best = None
        print(f"\n{cat}: real rows {len(real)} (matched {len(rm)}), shifted rows {len(sh)} (matched {len(sm)})")
        for t in grid:
            false = (sm >= t).sum() / max(len(sh), 1)
            kept = (rm >= t).sum() / max(len(rm), 1)
            if t in (0.0,) or abs(np.log10(t) % 0.5) < 1e-9:
                print(f"  t={t:.4g}  false={100 * false:.1f} %  kept real matches={100 * kept:.1f} %")
            if best is None and false <= a.target:
                best = (t, false, kept)
        if best:
            print(f"  -> threshold {best[0]:.4g}: false {100 * best[1]:.1f} %, kept {100 * best[2]:.1f} %")
            rows.append(dict(catalog=cat, min_posterior=round(float(best[0]), 6), false_rate=round(float(best[1]), 4),
                             kept_real=round(float(best[2]), 4), target=a.target))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    if a.write and len(t):
        t.to_csv(OUT, index=False)
        print("wrote", OUT)


if __name__ == "__main__":
    main()

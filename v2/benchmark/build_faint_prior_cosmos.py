#!/usr/bin/env python3
"""Faint star:galaxy number counts from COSMOS2020 truth (2.52.0).

The 2.46.0 faint prior (faint_class_prior.csv) counted our own labels in the
200 validation regions.  Two biases follow: the regions are centred on
stellar targets, and at r > 24 our labels call many faint point-like
galaxies stars.  At |b| = 40-60 deg the table gives 16 % stars at r = 24 and
58 % at r = 25; COSMOS2020 truth gives 4 % and 9 % (ab_2_51_ls rescore).

This script counts STAR and GALAXY truth objects (COSMOS2020 ACS morphology
+ SED class, Weaver et al. 2022, ApJS 258, 11) matched to our objects in
the calibration COSMOS fields only (prior_layer_study.split: odd-numbered
deep_cosmos fields), per 0.5 mag of Legacy Surveys r, so the even fields
stay a clean test.  These are the number counts dN_t/dm of the objects we
detect, the prior of Henrion et al. (2011) measured instead of modelled.
Position enters separately through the local Gaia density prior
(qso_options.density_prior): galaxy counts are isotropic, star counts scale
with the local stellar density.

    python v2/benchmark/build_faint_prior_cosmos.py \
        --truth-probs v2/benchmark/experiments/ab_2_51_ls_rescore/truth_probs_base.csv.gz
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
sys.path.insert(0, str(B))
import prior_layer_study as S  # noqa: E402

OUT = B.parent / "Preprocess" / "faint_class_prior_cosmos.csv"
EDGES = np.arange(20.0, 26.01, 0.5)  # last bin: r >= 26


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth-probs", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    t = pd.read_csv(a.truth_probs, low_memory=False)
    t = t[t.field.str.startswith("deep") & t.t_truth.isin(["STAR", "GALAXY"])]
    t = t[S.split(t.field) == "cal"]
    r = pd.to_numeric(t.std_mag__ls_r, errors="coerce")
    rows = []
    for lo, hi in zip(EDGES, list(EDGES[1:]) + [np.inf]):
        m = (r >= lo) & (r < hi)
        rows.append({"r_lo": lo, "r_hi": hi, "n_star": int((t.t_truth[m] == "STAR").sum()),
                     "n_galaxy": int((t.t_truth[m] == "GALAXY").sum())})
    d = pd.DataFrame(rows)
    d["fields"] = " ".join(sorted(t.field.unique()))
    d.to_csv(a.out, index=False)
    d["star_fraction"] = ((d.n_star + 1) / (d.n_star + d.n_galaxy + 2)).round(4)
    print(d.drop(columns="fields").to_string(index=False))
    print(f"[OK] {len(t)} truth objects in {t.field.nunique()} calibration fields -> {a.out}")


if __name__ == "__main__":
    main()

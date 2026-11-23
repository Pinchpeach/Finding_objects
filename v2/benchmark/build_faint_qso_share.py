#!/usr/bin/env python3
"""QSO share of the faint prior from the COSMOS calibration fields (2.57.0).

faint_class_prior_cosmos.csv (2.52.0) counts COSMOS2020 stars and galaxies per r bin in the odd-numbered
(calibration) deep fields.  This adds the missing class: the Chandra COSMOS Legacy type-1 AGN (Marchesi et
al. 2016; X-ray selection does not depend on optical colour, so they are the faint quasars without a colour
pre-selection) among the same detected truth objects, per 1 mag of LS r in 22 <= r < 24.  ``n_other`` is the
detected truth objects that are not type 1 (stars, galaxies, type-2 AGN).  The share is a lower bound: a quasar
without an X-ray detection is counted among the others.

    python v2/benchmark/build_faint_qso_share.py --matched OUT/matched_base.csv.gz   # written by
    faint_qso_candidates.py tables; calibration fields only; writes Preprocess/faint_qso_share_cosmos.csv

Only calibration fields are read; the test fields never enter (the same rule as the 2.52.0 table).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[1]
BINS = [(22.0, 23.0), (23.0, 24.0)]


def build(matched: pd.DataFrame) -> pd.DataFrame:
    cal = matched[matched.split == "cal"]
    rows = []
    for lo, hi in BINS:
        x = cal[(cal.o_std_mag__ls_r >= lo) & (cal.o_std_mag__ls_r < hi)]
        n1 = int((x.truth == "TYPE1").sum())
        rows.append(
            {
                "r_lo": lo,
                "r_hi": hi,
                "n_type1": n1,
                "n_other": int(len(x)) - n1,
                "fields": " ".join(sorted(cal.field.unique())),
            }
        )
    return pd.DataFrame(rows)


def from_census(census: pd.DataFrame) -> pd.DataFrame:
    """The share table with every detected object as the denominator (2.59.0; faint_qso_candidates.py census)."""
    cal = census[(census.split == "cal") & (census.r_lo >= 22) & (census.r_hi <= 24)]
    return pd.DataFrame(
        {
            "r_lo": cal.r_lo.astype(float),
            "r_hi": cal.r_hi.astype(float),
            "n_type1": cal.n_type1,
            "n_other": cal.n_objects - cal.n_type1,
            "fields": cal.fields,
        }
    ).reset_index(drop=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--matched", type=Path, help="matched_<variant>.csv.gz: truth-matched objects as the denominator (2.58.0)"
    )
    p.add_argument("--census", type=Path, help="pi_qso_census.csv: every detected object as the denominator (2.59.0)")
    p.add_argument("--out", type=Path, default=V2 / "Preprocess" / "faint_qso_share_cosmos.csv")
    a = p.parse_args()
    if bool(a.matched) == bool(a.census):
        p.error("give one of --matched and --census")
    t = build(pd.read_csv(a.matched, low_memory=False)) if a.matched else from_census(pd.read_csv(a.census))
    t.to_csv(a.out, index=False)
    print(t.drop(columns="fields").to_string(index=False), "->", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

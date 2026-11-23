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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--matched", type=Path, required=True)
    p.add_argument("--out", type=Path, default=V2 / "Preprocess" / "faint_qso_share_cosmos.csv")
    a = p.parse_args()
    t = build(pd.read_csv(a.matched, low_memory=False))
    t.to_csv(a.out, index=False)
    print(t.drop(columns="fields").to_string(index=False), "->", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

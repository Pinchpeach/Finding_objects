#!/usr/bin/env python3
"""Reference set for the photometric quasar redshift class (2.28.0).

Dereddened Legacy Surveys DR10 colours (g-r, r-z, z-W1, W1-W2) and r of the
DESI DR1 quasars in the fusion training set (desi_fusion: train only, RA
windows disjoint from the DESI external test set and the validation fields),
with their spectroscopic redshift.  Used by Classifier/subclass.py qso_photoz.

    python v2/benchmark/build_qso_photoz_reference.py
"""

from __future__ import annotations
import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[1]
BENCH = V2 / "benchmark"
LS = "desi_legacy_surveys_dr10__"


def main() -> None:
    s = importlib.util.spec_from_file_location("v2_subclass", V2 / "Classifier" / "subclass.py")
    sc = importlib.util.module_from_spec(s)
    s.loader.exec_module(sc)
    t = pd.read_csv(BENCH / "desi_fusion" / "truth.csv")
    t = t[t.truth_class.eq("QSO") & t.z.gt(0)]
    ls = pd.read_csv(BENCH / "desi_fusion" / "catalog_features" / "desi_legacy_trd.csv.gz", low_memory=False)
    ls = ls.drop_duplicates("benchmark_id").set_index("benchmark_id")
    rows = []
    for r in t.itertuples():
        if r.benchmark_id not in ls.index:
            continue
        x = sc.qso_photoz_features({LS + k: v for k, v in ls.loc[r.benchmark_id].items()})
        if x is not None:
            rows.append([round(v, 4) for v in x] + [round(r.z, 4)])
    out = pd.DataFrame(rows, columns=[*sc.QSO_PZ_COLUMNS, "z"])
    out.to_csv(sc.QSO_PZ_REFERENCE, index=False, compression="gzip")
    print(f"{len(out)} of {len(t)} quasars -> {sc.QSO_PZ_REFERENCE}")


if __name__ == "__main__":
    main()

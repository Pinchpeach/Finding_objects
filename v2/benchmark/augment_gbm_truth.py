#!/usr/bin/env python3
"""Add the Tractor fit-quality columns to the LS-GBM training set (2.44.0).

desi_gbm_truth/train.csv.gz (build_desi_gbm_truth.py) holds the DESI DR1
photometry DESI targeted on (LS DR9).  ``desi_dr1.photometry`` also carries
the chi^2 gains of the five Tractor models (dchisq_psf ... dchisq_ser), the
half-light-radius inverse variance and the neighbour flux fractions; they
are fetched by TARGETID, 1000 per query, and stored under the same p_ prefix.
Existing columns and rows are unchanged.

    python v2/benchmark/augment_gbm_truth.py
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
FILE = BENCH / "desi_gbm_truth" / "train.csv.gz"
TAP = "https://datalab.noirlab.edu/tap"
COLS = [
    "dchisq_psf", "dchisq_rex", "dchisq_dev", "dchisq_exp", "dchisq_ser",
    "shape_r_ivar", "fiberflux_r", "fracflux_g", "fracflux_r", "fracflux_z",
]


def main() -> None:
    sys.path.insert(0, str(BENCH.parent / "Get_data"))
    import throttle

    throttle.install()  # 3-5 s before every archive request (2.33.0)
    import pyvo

    s = pyvo.dal.TAPService(TAP)
    d = pd.read_csv(FILE, low_memory=False, dtype={"targetid": str})
    ids = sorted({x for x in d.targetid.dropna().astype(str) if x.isdigit()})
    parts = []
    for i in range(0, len(ids), 1000):
        chunk = ids[i : i + 1000]
        q = f"SELECT targetid, {', '.join(COLS)} FROM desi_dr1.photometry WHERE targetid IN ({','.join(chunk)})"
        for attempt in range(4):
            try:
                parts.append(s.search(q, maxrec=2000).to_table().to_pandas())
                break
            except Exception as exc:
                print("retry", attempt, str(exc)[:150], flush=True)
                time.sleep(15 * (attempt + 1))
        else:
            raise RuntimeError("Data Lab query failed")
        print(f"{i + len(chunk)}/{len(ids)}", flush=True)
    extra = pd.concat(parts, ignore_index=True)
    extra["targetid"] = extra["targetid"].astype("int64").astype(str)
    extra = extra.drop_duplicates("targetid").rename(columns={c: f"p_{c}" for c in COLS})
    d = d.drop(columns=[f"p_{c}" for c in COLS if f"p_{c}" in d.columns]).merge(extra, on="targetid", how="left")
    print(FILE.name, len(d), {c: int(d[f"p_{c}"].notna().sum()) for c in COLS}, flush=True)
    d.to_csv(FILE, index=False, compression={"method": "gzip", "compresslevel": 9, "mtime": 0})


if __name__ == "__main__":
    sys.exit(main())

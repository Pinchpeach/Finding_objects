#!/usr/bin/env python3
"""Add the Legacy Surveys DR10 columns the production collector now returns
(sersic, shape_r, flux_ivar_w1, flux_ivar_w2) to the preserved benchmark
features, by ls_id (2.11.0).

Re-collecting every benchmark object by cone search took longer than the 4 h
Actions limit; the objects are already matched, so their Tractor rows are
fetched directly: ``SELECT ... FROM ls_dr10.tractor WHERE ls_id IN (...)``,
500 IDs per query.  Existing columns are kept; only missing ones are added.

    python v2/benchmark/augment_ls_columns.py
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
FILES = [BENCH / "catalog_features" / "desi_legacy_trd.csv.gz",
         BENCH / "desi_external" / "catalog_features" / "desi_legacy_trd.csv.gz"]
COLS = ["sersic", "shape_r", "flux_ivar_w1", "flux_ivar_w2"]
TAP = "https://datalab.noirlab.edu/tap"


def fetch(ids: list[str]) -> pd.DataFrame:
    import pyvo
    s = pyvo.dal.TAPService(TAP)
    parts = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = f"SELECT ls_id, {', '.join(COLS)} FROM ls_dr10.tractor WHERE ls_id IN ({','.join(chunk)})"
        for attempt in range(4):
            try:
                parts.append(s.search(q).to_table().to_pandas())
                break
            except Exception as exc:
                print("retry", attempt, str(exc)[:150], flush=True)
                time.sleep(15 * (attempt + 1))
        else:
            raise RuntimeError("Data Lab query failed")
        print(f"{i + len(chunk)}/{len(ids)}", flush=True)
    out = pd.concat(parts, ignore_index=True)
    out["ls_id"] = out["ls_id"].astype("int64").astype(str)
    return out.drop_duplicates("ls_id")


def main() -> None:
    for f in FILES:
        d = pd.read_csv(f, low_memory=False, dtype={"ls_id": str})
        ids = sorted({x for x in d.ls_id.dropna().astype(str) if x.isdigit()})
        extra = fetch(ids)
        d = d.drop(columns=[c for c in COLS if c in d.columns]).merge(extra, on="ls_id", how="left")
        print(f.name, len(d), {c: int(d[c].notna().sum()) for c in COLS}, flush=True)
        d.to_csv(f, index=False, compression={"method": "gzip", "compresslevel": 9, "mtime": 0})


if __name__ == "__main__":
    sys.exit(main())

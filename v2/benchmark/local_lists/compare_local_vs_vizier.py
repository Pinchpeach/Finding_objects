#!/usr/bin/env python3
"""Local cone answers against live VizieR cones (2.60.7, ``Get_data/local_lists.py``).

    python v2/benchmark/local_lists/compare_local_vs_vizier.py --out OUT.csv [--hits 16] [--empty 4] [--seed N]

For each list (Suh 2021 AGB, Roma-BZCAT 5) the whole tables are downloaded once into a temporary store (the first-use
download of the feature itself), then random cones are asked both from that copy and from VizieR (through the usual
mirror failover): cones centred near catalogue rows (radius 2, 6, 10 or 30 arcmin; the centre is offset by up to
0.05 deg so that no row sits exactly in the middle) and cones on empty sky.  Per cone and per table the two answers are
compared as ``to_pandas`` frames: the tables returned, the columns and their order, the dtypes, the number of rows and
every cell (NaN equal to NaN).  The ``_r`` distance column is compared separately: VizieR computes it from positions
more precise than the 5-decimal degree columns of the tables, so it differs by up to about 6e-4 arcmin; no code reads it.
Needs the network.  The result of the run of 2026-11-25 is ``local_vs_vizier_2026-11-25.csv``.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))


def frames(tl) -> dict:
    return {k: tl[k].to_pandas() for k in tl.keys()}


def compare_frames(remote: dict, local: dict) -> dict:
    same_tables = list(remote) == list(local)
    out = {"same_tables": same_tables, "rows": sum(len(v) for v in remote.values()), "cells_differing": 0, "dtype_diffs": 0,
           "columns_same": True, "max_dr_arcmin": 0.0}  # fmt: skip
    if not same_tables:
        return out
    for k, x in remote.items():
        y = local[k]
        if list(x.columns) != list(y.columns):
            out["columns_same"] = False
            continue
        out["dtype_diffs"] += sum(str(x[c].dtype) != str(y[c].dtype) for c in x.columns)
        if len(x) != len(y):
            out["cells_differing"] += abs(len(x) - len(y))
            continue
        xs, ys = x.drop(columns="_r"), y.drop(columns="_r")
        xo, yo = xs.astype(object).where(xs.notna(), "<NA>"), ys.astype(object).where(ys.notna(), "<NA>")
        out["cells_differing"] += int((xo != yo).sum().sum())
        if len(x):
            out["max_dr_arcmin"] = max(out["max_dr_arcmin"], float(np.abs(x["_r"] - y["_r"]).max()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hits", type=int, default=16)
    ap.add_argument("--empty", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261125)
    a = ap.parse_args()
    os.environ["V2_CACHE_DIR"] = tempfile.mkdtemp(prefix="local_lists_cmp_")
    os.environ.pop("V2_CACHE", None)
    import local_lists as L
    from _catalog_utils import vizier_query

    rng = random.Random(a.seed)
    rows = []
    for key, spec in L.SPECS.items():
        t0 = time.time()
        man = L._download(spec)
        tables = L._load(spec, man)
        print(f"{key}: downloaded in {time.time() - t0:.0f} s", flush=True)
        pos = pd.concat(
            [pd.DataFrame(dict(zip(("ra", "dec"), L.positions(spec, t)))) for t in tables.values()]
        ).dropna().reset_index(drop=True)  # fmt: skip
        cones = []
        for _ in range(a.hits):
            r = pos.iloc[rng.randrange(len(pos))]
            cones.append(
                (
                    float(r.ra) + rng.uniform(-0.05, 0.05),
                    float(r.dec) + rng.uniform(-0.05, 0.05),
                    rng.choice([2.0, 6.0, 10.0, 30.0]),
                )
            )
        for _ in range(a.empty):
            cones.append((rng.uniform(0, 360), rng.uniform(-80, 80), rng.choice([2.0, 6.0])))
        for ra, dec, r in cones:
            try:
                t0 = time.time()
                rem = vizier_query(list(spec.tables) if len(spec.tables) > 1 else spec.tables[0], ra, dec, r)
                remote_s = time.time() - t0
            except Exception as exc:
                rows.append(
                    {
                        "list": key,
                        "ra": round(ra, 5),
                        "dec": round(dec, 5),
                        "radius_arcmin": r,
                        "status": f"remote failed: {type(exc).__name__}",
                    }
                )
                continue
            loc = L.cone_from(spec, tables, ra, dec, r)
            res = compare_frames(frames(rem), frames(loc))
            rows.append(
                {
                    "list": key,
                    "ra": round(ra, 5),
                    "dec": round(dec, 5),
                    "radius_arcmin": r,
                    "remote_seconds": round(remote_s, 1),
                    "status": "ok",
                    **res,
                }
            )
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    ok = df[df.status == "ok"]
    print(
        f"\n{len(ok)} cones compared ({int((df.status != 'ok').sum())} remote failures), {int(ok.rows.sum())} rows; "
        f"differing cells outside _r: {int(ok.cells_differing.sum())}; tables/columns different: "
        f"{int((~ok.same_tables).sum())}/{int((~ok.columns_same).sum())}; dtype differences: {int(ok.dtype_diffs.sum())}; "
        f"max |dr| = {ok.max_dr_arcmin.max():.6f} arcmin"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

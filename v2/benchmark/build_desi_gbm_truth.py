#!/usr/bin/env python3
"""Large DESI DR1 training set for the Legacy Surveys gradient-boosting
coarse classifier (2.11.0, Preprocess/ls_gbm.py).

Truth: DESI DR1 Redrock SPECTYPE (STAR / GALAXY / QSO) with the benchmark's
quality cut (ZWARN = 0, DELTACHI2 > 25, primary spectrum, science target).
Features: the Legacy Surveys Tractor photometry and morphology that DESI
targeted on (Data Lab ``desi_dr1.photometry``, LS DR9): g, r, z, W1, W2
fluxes and inverse variances, E(B-V), morphological type, Sersic index,
half-light radius.  Random subsample by ``random_id``, the same number per
class.  Every object of the existing benchmarks (DESI external truth by
TARGETID, SDSS ground truth within 1.5") is removed, so their test splits
stay independent.

Output: v2/benchmark/desi_gbm_truth/train.csv.gz
"""

from __future__ import annotations
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
OUT = BENCH / "desi_gbm_truth"
TAP = "https://datalab.noirlab.edu/tap"
WANT = [
    "targetid",
    "target_ra",
    "target_dec",
    "ra",
    "dec",
    "flux_g",
    "flux_r",
    "flux_z",
    "flux_w1",
    "flux_w2",
    "flux_ivar_g",
    "flux_ivar_r",
    "flux_ivar_z",
    "flux_ivar_w1",
    "flux_ivar_w2",
    "ebv",
    "morphtype",
    "sersic",
    "shape_r",
    "maskbits",
    "release",
    "photsys",
]


def columns(s, table: str) -> list[str]:
    t = s.search(f"SELECT column_name FROM tap_schema.columns WHERE table_name = '{table}'").to_table()
    return [str(x) for x in t["column_name"]]


def query(s, q: str, tries: int = 3):
    for i in range(tries):
        try:
            job = s.submit_job(q)
            job.run()
            job.wait(phases=["COMPLETED", "ERROR", "ABORTED"], timeout=1800)
            job.raise_if_error()
            return job.fetch_result().to_table().to_pandas()
        except Exception as exc:
            print("query failed:", str(exc)[:200], flush=True)
            time.sleep(20 * (i + 1))
    raise RuntimeError("Data Lab query failed")


def main() -> None:
    import pyvo

    p = argparse.ArgumentParser()
    p.add_argument("--per-class", type=int, default=50000)
    p.add_argument("--step", type=float, default=0.5, help="random_id slice per query (0-100 scale)")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    s = pyvo.dal.TAPService(TAP)
    pc = columns(s, "desi_dr1.photometry")
    zc = columns(s, "desi_dr1.zpix")
    print("photometry columns:", pc, flush=True)
    print("zpix columns:", zc, flush=True)
    sel = [c for c in WANT if c in pc]
    zsel = [c for c in ("targetid", "spectype", "z", "zwarn", "deltachi2", "zcat_primary", "objtype") if c in zc]
    parts = []
    for cls in ("STAR", "GALAXY", "QSO"):
        got, lo = 0, 0.0
        while got < a.per_class and lo < 100:
            hi = lo + a.step
            q = (
                f"SELECT {', '.join('z.' + c for c in zsel)}, {', '.join('p.' + c + ' AS p_' + c for c in sel)} "
                f"FROM desi_dr1.zpix AS z JOIN desi_dr1.photometry AS p ON p.targetid = z.targetid "
                f"WHERE z.spectype = '{cls}' AND z.zwarn = 0 AND z.deltachi2 > 25 "
                f"AND p.random_id >= {lo} AND p.random_id < {hi}"
            )
            d = query(s, q)
            if "zcat_primary" in d:
                d = d[d.zcat_primary.astype(str).str.lower().isin(["true", "t", "1"])]
            if "objtype" in d:
                d = d[d.objtype.astype(str).str.strip().eq("TGT")]
            d = d.drop_duplicates("targetid")
            parts.append(d)
            got += len(d)
            print(f"{cls} random_id [{lo:.1f},{hi:.1f}): +{len(d)} -> {got}", flush=True)
            lo = hi
    d = pd.concat(parts, ignore_index=True).drop_duplicates("targetid")
    d = pd.concat([g.head(a.per_class) for _, g in d.groupby("spectype")], ignore_index=True)
    # Remove every benchmark object (keeps their test splits independent).
    ext = pd.read_csv(BENCH / "desi_external" / "truth.csv", dtype={"desi_targetid": str})
    n0 = len(d)
    d = d[~d.targetid.astype("int64").astype(str).isin(set(ext.desi_targetid.dropna()))]
    gt = pd.read_csv(BENCH / "truth_data" / "ground_truth.csv")
    ra = pd.to_numeric(d.get("p_target_ra", d.get("p_ra")), errors="coerce").to_numpy()
    de = pd.to_numeric(d.get("p_target_dec", d.get("p_dec")), errors="coerce").to_numpy()
    from scipy.spatial import cKDTree

    def xyz(r, dd):
        r, dd = np.radians(r), np.radians(dd)
        return np.c_[np.cos(dd) * np.cos(r), np.cos(dd) * np.sin(r), np.sin(dd)]

    tree = cKDTree(xyz(gt.ra.to_numpy(), gt.dec.to_numpy()))
    ok = np.isfinite(ra) & np.isfinite(de)
    near = np.zeros(len(d), bool)
    dist, _ = tree.query(xyz(ra[ok], de[ok]))
    near[np.where(ok)[0]] = dist < np.radians(1.5 / 3600)
    d = d[~near]
    print(f"removed {n0 - len(d)} benchmark objects; final {d.spectype.value_counts().to_dict()}", flush=True)
    d.to_csv(OUT / "train.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()

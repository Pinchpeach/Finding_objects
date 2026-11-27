#!/usr/bin/env python3
"""The regions of the low-latitude quasar recall measurement, drawn by a rule fixed before any data is collected (2.61.2).

    python select_fields_lowlat.py --truth lowlat_truth.csv.gz --out fields_lowlat.csv

Rule (the SHA-256 of ``fields_lowlat.csv`` is written to ``LOWLAT_QSO.md`` before the workflow runs):

1. Candidates are the unique quasars of ``lowlat_truth.csv.gz``: all Huo et al. 2025 quasars and the Fu et al. 2022 quasars
   that are not also in the Huo table (``also_in`` empty).  The 19 Fu stars and galaxies are candidates of their own
   ``contaminant`` list: all of them are drawn.
2. Four strata in |b|: [0,5), [5,10), [10,15), [15,20] deg, quotas ``QUOTA`` (the first stratum has fewer quasars than its
   quota: all of them).  Inside a stratum the cells are (sample: huo / fu) x (l: [0,60), [60,120), [120,180), [180,360)) x
   (E(B-V): < 0.1, 0.1-0.2, >= 0.2, unknown); the draw takes one quasar from each non-empty cell in turn (cells in sorted
   order) until the quota is met, and inside a cell the quasars in the order of sha1(``SALT`` + name).
3. A quasar whose position is within ``2 R`` of an earlier pick of any list is skipped (so the cones do not overlap).
4. A region is a cone of radius ``R`` = 3 arcmin around the drawn object.  Every quasar of the truth table inside a cone
   is scored, not only the one at its centre.

Everything is deterministic: the same inputs give the same file.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

SALT = "lowlat-qso-2026-11-27"
R_ARCMIN = 3.0
B_EDGES = [0.0, 5.0, 10.0, 15.0, 20.0001]
QUOTA = {0: 20, 1: 50, 2: 40, 3: 40}
L_EDGES = [0.0, 60.0, 120.0, 180.0, 360.0001]
EBV_EDGES = [0.0, 0.1, 0.2, 99.0]


def _key(name: str) -> str:
    return hashlib.sha1((SALT + name).encode()).hexdigest()


def _sep_arcmin(ra1, dec1, ra2, dec2) -> np.ndarray:
    a1, d1, a2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1, 1))) * 60.0


def select(d: pd.DataFrame) -> pd.DataFrame:
    q = d[(d.cls == "qso") & (d.also_in.fillna("") != "huo")].copy()
    q["stratum"] = np.digitize(q.b.abs(), B_EDGES) - 1
    q["lbin"] = np.digitize(q.l, L_EDGES) - 1
    q["ebin"] = np.where(q.ebv.isna(), 3, np.digitize(q.ebv.fillna(0), EBV_EDGES) - 1)
    q["cell"] = list(zip(q["sample"], q.lbin, q.ebin))
    q["k"] = q.name.map(_key)
    picked = []  # rows of the result, in the order of the draw

    def free(row) -> bool:
        return all(_sep_arcmin(row.ra, row.dec, p["ra"], p["dec"]) > 2 * R_ARCMIN for p in picked)

    for s in range(4):
        cells = {c: g.sort_values("k").itertuples() for c, g in q[q.stratum == s].groupby("cell")}
        queues = {c: list(it) for c, it in cells.items()}
        n = 0
        while n < QUOTA[s] and any(queues.values()):
            for c in sorted(queues):
                while queues[c]:
                    row = queues[c].pop(0)
                    if free(row):
                        picked.append(dict(name=f"lq{s}_{n:03d}", stratum=f"b{int(B_EDGES[s])}-{int(B_EDGES[s + 1])}",
                                           kind="qso", center_name=row.name, center_sample=row.sample, ra=row.ra,
                                           dec=row.dec, l=row.l, b=row.b, ebv=row.ebv, imag=row.imag, z=row.z))  # fmt: skip
                        n += 1
                        break
                if n >= QUOTA[s]:
                    break
    c = d[d.cls.isin(["star", "galaxy"])].copy()
    c["k"] = c.name.map(_key)
    for j, row in enumerate(c.sort_values("k").itertuples()):
        if free(row):
            picked.append(dict(name=f"lc_{j:03d}", stratum="contaminant", kind=row.cls, center_name=row.name,
                               center_sample=row.sample, ra=row.ra, dec=row.dec, l=row.l, b=row.b, ebv=row.ebv,
                               imag=row.imag, z=row.z))  # fmt: skip
    return pd.DataFrame(picked)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    f = select(pd.read_csv(a.truth))
    f["ra"], f["dec"] = f.ra.round(5), f.dec.round(5)
    f.to_csv(a.out, index=False)
    print(f.groupby(["stratum", "kind"]).size().to_string())
    print("regions", len(f), "sha256", hashlib.sha256(a.out.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""How precise are the NED / SIMBAD positions in a deep field?  Offset of every literature row to the nearest COSMOS2020 source (2.63.3).

    python literature_position_accuracy.py --raw RAWDIR --truth TRUTH.csv.gz --out OUT

COSMOS2020 (Weaver et al. 2022) positions are good to ~0.1''; a literature row that is that source has an offset of that order, an unrelated
row has the offset of a random neighbour (COSMOS2020 holds ~0.1 sources / arcsec^2 at all magnitudes, so a random position has one within 0.3'' in 3 % of cases).
The same offsets for the positions moved 15-40'' (random control) are in the ``control_*`` columns.  Rows are grouped by catalogue and, for SIMBAD, by
``coo_wavelength`` and by the bibcode that gave the coordinates.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
import measure_association as MA  # noqa: E402

BINS = (0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0)


def offsets(sky, ra, dec):
    _, sep = sky.nearest(np.asarray(ra, float), np.asarray(dec, float), 5.0)
    return sep


def table(name, sep, ctl):
    row = dict(group=name, n=len(sep), median_arcsec=round(float(np.median(sep[np.isfinite(sep)])), 3) if np.isfinite(sep).any() else np.nan)
    for b in BINS:
        row[f"within_{b}"] = round(float(np.mean(sep <= b)) * 100, 1)
        row[f"control_{b}"] = round(float(np.mean(ctl <= b)) * 100, 1)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t = MA.load_truth(a.truth)
    sky = MA.Sky(t.ra.to_numpy(float), t.dec.to_numpy(float))
    rng = np.random.default_rng(2)
    rows = []
    for cat, pat in (("SIMBAD", "simbad_*.csv"), ("NED", "ned_*.csv")):
        f = glob.glob(str(a.raw / pat))[0]
        d = pd.read_csv(f, low_memory=False)
        d = d.assign(ra=pd.to_numeric(d.ra, errors="coerce"), dec=pd.to_numeric(d.dec, errors="coerce")).dropna(subset=["ra", "dec"])
        sep = offsets(sky, d.ra, d.dec)
        ang, rr = rng.uniform(0, 2 * np.pi, len(d)), rng.uniform(15, 40, len(d)) / 3600.0
        ctl = offsets(sky, d.ra + rr * np.cos(ang) / np.cos(np.radians(d.dec)), d.dec + rr * np.sin(ang))
        rows.append(table(cat, sep, ctl))
        if cat == "SIMBAD":
            for key in ("coo_wavelength", "coo_bibcode"):
                for v, g in d.groupby(key):
                    if len(g) >= 25:
                        ix = g.index.to_numpy()
                        pos = d.index.get_indexer(ix)
                        rows.append(table(f"SIMBAD {key}={v}", sep[pos], ctl[pos]))
        else:
            for v, g in d.groupby("Type"):
                if len(g) >= 25:
                    pos = d.index.get_indexer(g.index.to_numpy())
                    rows.append(table(f"NED Type={v}", sep[pos], ctl[pos]))
    out = pd.DataFrame(rows)
    out.to_csv(a.out / "literature_position_accuracy.csv", index=False)
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

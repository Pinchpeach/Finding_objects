#!/usr/bin/env python3
"""The label of the nearest survey object of every literature-only object, by distance (2.62.4).

    python nearest_neighbour_label.py --assoc source_association.csv --classified classified_objects.csv --out CSV

Literature-only = every row NED / SIMBAD.  The nearest survey object is the object (holding a non-NED/SIMBAD row) whose anchor position is nearest; its primary class
is that of the classified object at the same position (within 0.3'').  Written to answer "what is next to the literature-only objects": where the nearest survey
object is a galaxy, a star or a quasar, and how far.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assoc", type=Path, required=True)
    ap.add_argument("--classified", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    s = pd.read_csv(a.assoc, low_memory=False)
    cl = pd.read_csv(a.classified, low_memory=False)
    s["lit"] = s.catalog.isin(["NED", "SIMBAD"])
    o = s.groupby("object_id").agg(ra=("object_ra", "first"), dec=("object_dec", "first"), lit_only=("lit", "all"))
    c = np.cos(np.radians(float(o.dec.mean())))
    xy = lambda d: np.c_[d.ra.to_numpy() * c * 3600, d.dec.to_numpy() * 3600]  # noqa: E731
    surv, lit = o[~o.lit_only], o[o.lit_only]
    d, i = cKDTree(xy(surv)).query(xy(lit))
    dc, ic = cKDTree(xy(cl)).query(xy(surv.iloc[i]))
    cls = np.where(dc <= 0.3, cl.primary_class.to_numpy()[ic], "none")
    t = pd.DataFrame(dict(distance=d, neighbour_class=cls))
    t["bin"] = pd.cut(t.distance, [0, 0.5, 1, 2, 3, 5, 1e9], labels=["<=0.5", "0.5-1", "1-2", "2-3", "3-5", ">5"])
    out = pd.crosstab(t.bin, t.neighbour_class)
    out["n"] = out.sum(axis=1)
    out.to_csv(a.out)
    print(out.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

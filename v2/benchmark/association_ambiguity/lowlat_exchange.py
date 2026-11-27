#!/usr/bin/env python3
"""False QSO labels gained and lost by an association variant at low latitude, objects matched by position (2.61.7).

    python lowlat_exchange.py --table qso_labelled_not_sample_by_variant.csv.gz --base base --variants same_nearest all --out OUT [--tol 1.0]

``lowlat_qso/ab_variants.py`` pairs the objects of two variants by ``object_id@region``.  Object ids are sequential in the order the groups
are made, so a variant that changes an association renumbers everything after it and that exchange (``false_removed_vs_control``,
``false_added_vs_control``, ``removed_per_deg2``) counts renumbering.  Here the QSO-labelled objects that are not the sample quasar
of a region (the table ``ab_variants.py`` writes, one row per object id, one boolean column per variant) are matched between two variants by
position within a region: mutual nearest anchors within ``--tol`` arcsec.  Per variant against the base: objects kept, lost (QSO in the base,
no QSO object at that position in the variant), gained (the reverse), with the PS1 i < 19.5 and the >= 2 catalogues counts of each.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def xyz(ra, dec):
    a, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.c_[np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)]


def match(a: pd.DataFrame, b: pd.DataFrame, tol_arcsec: float):
    """Mutual nearest pairs within the tolerance: (positions in a, positions in b)."""
    if not len(a) or not len(b):
        return np.array([], int), np.array([], int)
    chord = 2 * math.sin(math.radians(tol_arcsec / 3600.0) / 2)
    ta, tb = cKDTree(xyz(a.ra, a.dec)), cKDTree(xyz(b.ra, b.dec))
    d1, i1 = tb.query(ta.data, distance_upper_bound=chord)
    _, i2 = ta.query(tb.data, distance_upper_bound=chord)
    ia = np.flatnonzero(np.isfinite(d1))
    keep = np.array([i1[i] < len(b) and i2[i1[i]] == i for i in ia], bool) if len(ia) else np.array([], bool)
    return ia[keep], i1[ia[keep]]


def exchange(t: pd.DataFrame, base: str, variant: str, tol: float) -> dict:
    kept = lost = gained = 0
    lost_i195 = gained_i195 = lost_multi = gained_multi = 0
    for _, g in t.groupby("region"):
        a, b = g[g[base].astype(bool)].reset_index(drop=True), g[g[variant].astype(bool)].reset_index(drop=True)
        ia, ib = match(a, b, tol)
        kept += len(ia)
        la = a.drop(index=ia)
        gb = b.drop(index=ib)
        lost += len(la)
        gained += len(gb)
        lost_i195 += int((la.ps1_i < 19.5).sum())
        gained_i195 += int((gb.ps1_i < 19.5).sum())
        lost_multi += int((la.n_catalogs >= 2).sum())
        gained_multi += int((gb.n_catalogs >= 2).sum())
    return dict(variant=variant, base_objects=kept + lost, variant_objects=kept + gained, kept=kept, lost=lost, gained=gained, lost_i_lt_195=lost_i195,
                gained_i_lt_195=gained_i195, lost_multi_catalog=lost_multi, gained_multi_catalog=gained_multi)  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tol", type=float, default=1.0)
    a = ap.parse_args()
    t = pd.read_csv(a.table, low_memory=False)
    r = pd.DataFrame([exchange(t, a.base, v, a.tol) for v in a.variants])
    a.out.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out / "lowlat_exchange.csv", index=False)
    print(r.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

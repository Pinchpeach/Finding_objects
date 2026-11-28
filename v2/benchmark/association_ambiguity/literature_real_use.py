#!/usr/bin/env python3
"""The literature switches on the three real-use fields (NGC 4522, COSMOS 2', Galactic plane): counts and label changes against the base run (2.62.6).

    python literature_real_use.py --runs DIR --out OUT

``DIR/run_<combo>/<field>/classified_objects.csv`` (slim, from the full pipeline; the survey-count switches ran with V2_LOWLAT_QSO_ABSB=90 so that they act at
every latitude).  Object ids are not comparable between runs (merging changes them), so a combo's objects are paired with the base objects by position (nearest
within 0.5'').  Per field and combo: objects, literature-only objects (every catalogue NED / SIMBAD), QSO labels, QSO labels held by the survey-count
switch (``lowlat_qso_hold``), QSO labels among the literature-only objects, and for the objects that exist in both runs the primary labels that differ.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

LIT = {"NED", "SIMBAD"}


def lit_only(cat: pd.Series) -> pd.Series:
    return cat.fillna("").map(lambda s: bool(s) and set(s.split("|")) <= LIT)


def pair(a: pd.DataFrame, b: pd.DataFrame, radius=0.5):
    """For each row of ``a`` the index of its partner in ``b`` (-1: none): among the objects of ``b`` within ``radius`` arcsec, the nearest one with the same
    ``catalogs`` string, else the nearest.  Two objects at the very same position (a duplicate NED entry) would be swapped by a plain nearest-neighbour pairing."""
    c = np.cos(np.radians(float(a.dec.mean())))
    xb = np.c_[b.ra.to_numpy() * c * 3600, b.dec.to_numpy() * 3600]
    xa = np.c_[a.ra.to_numpy() * c * 3600, a.dec.to_numpy() * 3600]
    t = cKDTree(xb)
    cats_b = b.catalogs.fillna("").to_numpy()
    cats_a = a.catalogs.fillna("").to_numpy()
    out = np.full(len(a), -1)
    for k, near in enumerate(t.query_ball_point(xa, radius)):
        if not near:
            continue
        d = np.hypot(*(xb[near] - xa[k]).T)
        same = [j for j in range(len(near)) if cats_b[near[j]] == cats_a[k]]
        pool = same or list(range(len(near)))
        out[k] = near[min(pool, key=lambda j: d[j])]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows, changes = [], []
    combos = sorted(p.name[4:] for p in a.runs.glob("run_*"))
    combos.remove("base")
    for field in ("ngc", "cosmos", "plane"):
        base = pd.read_csv(a.runs / "run_base" / field / "classified_objects.csv", low_memory=False)
        for combo in ["base"] + combos:
            d = pd.read_csv(a.runs / f"run_{combo}" / field / "classified_objects.csv", low_memory=False)
            lo = lit_only(d.catalogs)
            held = d.get("lowlat_qso_hold", pd.Series("", index=d.index)).fillna("").astype(str).ne("")
            r = dict(field=field, combo=combo, objects=len(d), lit_only=int(lo.sum()), qso=int((d.primary_class == "QSO").sum()), qso_held=int(held.sum()),
                     qso_lit_only=int(((d.primary_class == "QSO") & lo).sum()), qso_lit_only_held=int((held & lo).sum()))  # fmt: skip
            if combo != "base":
                i = pair(d, base)
                ok = i >= 0
                bb = base.iloc[i[ok]]
                dd = d[ok]
                diff = dd.primary_class.to_numpy() != bb.primary_class.to_numpy()
                r["paired_objects"] = int(ok.sum())
                r["unpaired_objects"] = int((~ok).sum())
                r["label_changes_paired"] = int(diff.sum())
                for x, y in zip(bb.primary_class.to_numpy()[diff], dd.primary_class.to_numpy()[diff]):
                    changes.append(dict(field=field, combo=combo, base_label=x, label=y))
            rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(a.out / "real_use_combos.csv", index=False)
    pd.DataFrame(changes).value_counts().rename("n").reset_index().to_csv(a.out / "real_use_label_transitions.csv", index=False)
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

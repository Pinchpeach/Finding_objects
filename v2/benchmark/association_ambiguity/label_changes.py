#!/usr/bin/env python3
"""Primary-label changes of a variant against the baseline, objects matched by position (2.61.7).

    python label_changes.py --base DIR_BASE --variant DIR_VARIANT --fields deep_cosmos_1,... --out OUT [--tol 0.2]

``DIR_*/<field>/classified_objects.csv`` of two full pipeline runs.  Object ids are NOT comparable between runs: an association change
shifts the sequential ``OBJ`` numbers of everything created after it.  An object of the variant and an object of the baseline are the same
object when their anchors (``ra``, ``dec``) agree within ``--tol`` arcsec (nearest pair, mutual).  Reported per r magnitude bin
(``std_mag__ls_r``): objects, the pairs, pairs whose ``primary_class`` changed (and the direction to/from QSO), and the objects that
exist in only one run (an object created or removed by a different association).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

BINS = [(-np.inf, 21.0), (21.0, 22.0), (22.0, 23.0), (23.0, 24.0), (24.0, np.inf)]


def xyz(ra, dec):
    a, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.c_[np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)]


def pair(a: pd.DataFrame, b: pd.DataFrame, tol_arcsec: float):
    """Mutual nearest anchors within the tolerance: (index in a, index in b)."""
    chord = 2 * math.sin(math.radians(tol_arcsec / 3600.0) / 2)
    ta, tb = cKDTree(xyz(a.ra, a.dec)), cKDTree(xyz(b.ra, b.dec))
    d1, i1 = tb.query(ta.data, distance_upper_bound=chord)
    d2, i2 = ta.query(tb.data, distance_upper_bound=chord)
    ia = np.flatnonzero(np.isfinite(d1))
    ok = np.array([i1[i] < len(b) and i2[i1[i]] == i for i in ia], bool) if len(ia) else np.array([], bool)
    return ia[ok], i1[ia[ok]]


def one(base: Path, var: Path, field: str, tol: float) -> pd.DataFrame:
    use = ["object_id", "ra", "dec", "primary_class", "std_mag__ls_r", "catalogs", "classification_status"]
    a = pd.read_csv(base / field / "classified_objects.csv", usecols=lambda c: c in use, low_memory=False).dropna(subset=["ra", "dec"]).reset_index(drop=True)
    b = pd.read_csv(var / field / "classified_objects.csv", usecols=lambda c: c in use, low_memory=False).dropna(subset=["ra", "dec"]).reset_index(drop=True)
    ia, ib = pair(a, b, tol)
    cat = lambda d, i: d.catalogs.to_numpy()[i] if "catalogs" in d else [""] * len(i)  # noqa: E731
    m = pd.DataFrame(dict(field=field, ra=a.ra.to_numpy()[ia], dec=a.dec.to_numpy()[ia], r=a.std_mag__ls_r.to_numpy()[ia], cls_b=a.primary_class.to_numpy()[ia], cls_v=b.primary_class.to_numpy()[ib],
                          catalogs_b=cat(a, ia), catalogs_v=cat(b, ib), object_b=a.object_id.to_numpy()[ia], object_v=b.object_id.to_numpy()[ib]))  # fmt: skip
    only_b = np.ones(len(a), bool)
    only_b[ia] = False
    only_v = np.ones(len(b), bool)
    only_v[ib] = False
    m.attrs["only_base"], m.attrs["only_variant"] = int(only_b.sum()), int(only_v.sum())
    m.attrs["only_base_r"], m.attrs["only_variant_r"] = a.std_mag__ls_r.to_numpy()[only_b], b.std_mag__ls_r.to_numpy()[only_v]
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--variant", type=Path, required=True)
    ap.add_argument("--fields", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tol", type=float, default=0.2)
    a = ap.parse_args()
    parts, ob, ov = [], [], []
    for f in [x for x in a.fields.split(",") if x]:
        m = one(a.base, a.variant, f, a.tol)
        parts.append(m)
        # popped, not read: pd.concat compares the ``attrs`` of its parts and raises on two numpy arrays of different lengths (2.62.2)
        ob.append(m.attrs.pop("only_base_r"))
        ov.append(m.attrs.pop("only_variant_r"))
    m = pd.concat(parts, ignore_index=True)
    ob, ov = np.concatenate(ob), np.concatenate(ov)
    m["changed"] = m.cls_b != m.cls_v
    rows = []
    for lo, hi in BINS + [(np.nan, np.nan)]:
        sel = m[m.r.isna()] if np.isnan(lo) else m[(m.r >= lo) & (m.r < hi)]
        selb = ob[np.isnan(ob)] if np.isnan(lo) else ob[(ob >= lo) & (ob < hi)]
        selv = ov[np.isnan(ov)] if np.isnan(lo) else ov[(ov >= lo) & (ov < hi)]
        rows.append(dict(r="no r" if np.isnan(lo) else f"{lo:g}-{hi:g}", pairs=len(sel), changed=int(sel.changed.sum()), to_QSO=int(((sel.cls_v == "QSO") & sel.changed).sum()),
                         from_QSO=int(((sel.cls_b == "QSO") & sel.changed).sum()), only_in_base=len(selb), only_in_variant=len(selv)))  # fmt: skip
    t = pd.DataFrame(rows)
    tot = t[["pairs", "changed", "to_QSO", "from_QSO", "only_in_base", "only_in_variant"]].sum()
    t = pd.concat([t, pd.DataFrame([dict(r="all", **tot.to_dict())])], ignore_index=True)
    a.out.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out / "label_changes.csv", index=False)
    pd.crosstab(m.cls_b, m.cls_v).to_csv(a.out / "label_transitions.csv")
    # which objects changed and what they are (2.62.2): the objects without a Legacy Surveys r magnitude are one-survey fragments, listed with their catalogues in both runs
    ch = m[m.changed].copy()
    ch["n_catalogs_b"] = ch.catalogs_b.fillna("").map(lambda c: len([x for x in str(c).split("|") if x]))
    ch["n_catalogs_v"] = ch.catalogs_v.fillna("").map(lambda c: len([x for x in str(c).split("|") if x]))
    ch.to_csv(a.out / "changed_pairs.csv", index=False)
    nr = m[m.r.isna()]
    pd.crosstab(nr.cls_b, nr.cls_v).to_csv(a.out / "label_transitions_no_r.csv")
    print("objects without an LS r magnitude, primary class before -> after (all pairs / changed):")
    print(pd.crosstab(nr.cls_b, nr.cls_v).to_string())
    print(t.to_string(index=False))
    print(pd.crosstab(m.cls_b, m.cls_v).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

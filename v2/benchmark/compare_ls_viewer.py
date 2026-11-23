#!/usr/bin/env python3
"""Legacy Surveys: the viewer catalogue (second path, 2.57.0) against the Data Lab TAP.

``desi_legacy.fetch`` asks the Legacy Surveys viewer's ``cat.fits`` when the
Data Lab TAP is slow or failing (request hedging).  2.57.0 compared the two on
DR10-South cones only (NGC 4522, COSMOS); the DR9-North part of ``ls_dr10``
(Dec >= 32.375 in the north Galactic cap) and the north/south boundary were not
compared because the Data Lab was down.  This runs ``fetch`` twice per cone,
once through the TAP only and once through the viewer only, through the same
post-processing the pipeline uses, and compares the rows:

* the ``ls_id`` sets (rows only in one path, by release and Dec);
* every TAP column on the common rows: largest relative difference, NaN
  positions, ``type`` strings.

    python v2/benchmark/compare_ls_viewer.py [--out v2/benchmark/ls_viewer_check/metrics.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH.parent / "Get_data"))
import desi_legacy as dl  # noqa: E402

# name, ra, dec, radius (arcmin), why
CONES = [
    ("ngc4522_south", 188.4155, 9.1751, 2.0, "DR10 South, compared in 2.57.0 (control)"),
    ("north_245p43", 245.0, 43.0, 2.0, "DR9 North, deep inside"),
    ("north_150p50", 150.0, 50.0, 2.0, "DR9 North"),
    ("ngc_split_north", 180.0, 32.45, 2.0, "NGC, just north of Dec 32.375 (both surveys observed)"),
    ("ngc_split_south", 180.0, 32.30, 2.0, "NGC, just south of Dec 32.375 (both surveys observed)"),
    ("sgc_dec33p5", 20.0, 33.5, 2.0, "SGC above Dec 32.375 (DR10 South only)"),
]


def _tap_only(ra, dec, r):
    orig = dl._query_with_retries
    dl._query_with_retries = lambda run, hedge=None: orig(run, None)
    try:
        return dl.fetch(ra, dec, r)
    finally:
        dl._query_with_retries = orig


def _viewer_only(ra, dec, r):
    orig = dl._query_with_retries
    dl._query_with_retries = lambda run, hedge=None: dl._viewer_fetch(ra, dec, r)
    try:
        return dl.fetch(ra, dec, r)
    finally:
        dl._query_with_retries = orig


def _timed(fn, *a):
    t0 = time.monotonic()
    try:
        return fn(*a), round(time.monotonic() - t0, 1), None
    except Exception as exc:  # noqa: BLE001 - reported
        return None, round(time.monotonic() - t0, 1), repr(exc)[:300]


def compare(tap: pd.DataFrame, view: pd.DataFrame) -> dict:
    if tap.empty or view.empty or "ls_id" not in tap or "ls_id" not in view:
        n_t, n_v = (0 if d.empty or "ls_id" not in d else len(d) for d in (tap, view))
        return {"rows_tap": n_t, "rows_viewer": n_v, "identical": n_t == n_v == 0}
    t = tap.set_index(tap.ls_id.astype("int64"))
    v = view.set_index(view.ls_id.astype("int64"))
    only_t, only_v = t.index.difference(v.index), v.index.difference(t.index)
    common = t.index.intersection(v.index)

    def rows(d, ids):
        if not len(ids):
            return {}
        s = d.loc[ids]
        return {
            "n": int(len(ids)),
            "release": s.release.astype(int).value_counts().to_dict(),
            "dec_range": [round(float(s.dec.min()), 4), round(float(s.dec.max()), 4)],
        }

    cols = {}
    for c in dl.TAP_COLUMNS:
        if c not in t or c not in v:
            cols[c] = "missing in " + ("tap" if c not in t else "viewer")
            continue
        a, b = t.loc[common, c], v.loc[common, c]
        if c == "type":
            cols[c] = {"differ": int((a.astype(str).str.strip() != b.astype(str).str.strip()).sum())}
            continue
        x, y = pd.to_numeric(a, errors="coerce").to_numpy(float), pd.to_numeric(b, errors="coerce").to_numpy(float)
        nan_diff = int((np.isnan(x) != np.isnan(y)).sum())
        ok = ~np.isnan(x) & ~np.isnan(y)
        rel = np.abs(x[ok] - y[ok]) / np.maximum(np.abs(x[ok]), 1e-30)
        rel = np.where(np.abs(x[ok] - y[ok]) == 0, 0.0, rel)
        cols[c] = {"max_rel": float(rel.max()) if rel.size else 0.0, "nan_differ": nan_diff}
    bad = {
        c: s
        for c, s in cols.items()
        if isinstance(s, str) or s.get("differ", 0) or s.get("nan_differ", 0) or s.get("max_rel", 0) > 1e-5
    }
    diag = {}
    if len(only_t) or len(only_v):  # same sources under other ids?  match the leftovers by position
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        a, b = t.loc[only_t], v.loc[only_v]
        if len(a) and len(b):
            i, sep, _ = SkyCoord(a.ra.to_numpy() * u.deg, a.dec.to_numpy() * u.deg).match_to_catalog_sky(
                SkyCoord(b.ra.to_numpy() * u.deg, b.dec.to_numpy() * u.deg)
            )
            m = sep.arcsec < 0.01
            bb = b.iloc[i[m]]
            aa = a[m]
            diag = {
                "matched_by_position_0p01arcsec": int(m.sum()),
                "same_brickid": int((aa.brickid.to_numpy() == bb.brickid.to_numpy()).sum()),
                "same_objid": int((aa.objid.to_numpy() == bb.objid.to_numpy()).sum()),
                "same_release": int((aa.release.to_numpy() == bb.release.to_numpy()).sum()),
                "examples_tap_viewer": [
                    [
                        {k: int(x[k]) for k in ("release", "brickid", "objid")} | {"ls_id": int(ia)},
                        {k: int(y[k]) for k in ("release", "brickid", "objid")} | {"ls_id": int(ib)},
                    ]
                    for (ia, x), (ib, y) in list(zip(aa.iterrows(), bb.iterrows()))[:3]
                ],
            }
    return {
        "rows_tap": int(len(t)),
        "rows_viewer": int(len(v)),
        "common": int(len(common)),
        "release_tap": t.release.astype(int).value_counts().to_dict() if len(t) else {},
        "release_viewer": v.release.astype(int).value_counts().to_dict() if len(v) else {},
        "only_tap": rows(t, only_t),
        "only_viewer": rows(v, only_v),
        "columns_compared": len(cols),
        "columns_differing": bad,
        "identical": not len(only_t) and not len(only_v) and not bad,
        "leftovers_by_position": diag,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=BENCH / "ls_viewer_check" / "metrics.json")
    a = p.parse_args()
    out = {"checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cones": {}}
    for name, ra, dec, r, why in CONES:
        view, tv, ev = _timed(_viewer_only, ra, dec, r)
        tap, tt, et = _timed(_tap_only, ra, dec, r)
        res = {"ra": ra, "dec": dec, "radius_arcmin": r, "why": why, "viewer_s": tv, "tap_s": tt}
        if ev or et:
            res.update({"viewer_error": ev, "tap_error": et})
        else:
            res.update(compare(tap, view))
        out["cones"][name] = res
        print(name, json.dumps(res, default=str), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()

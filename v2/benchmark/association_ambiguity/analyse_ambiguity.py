#!/usr/bin/env python3
"""How many detections become a new object because the association is ambiguous, and how many of those had a clear nearest candidate (2.61.7).

    python analyse_ambiguity.py --stage1 DIR --out OUT

``DIR`` holds ``<set>/<region>.csv.gz`` of ``run_stage1.py`` written with ``V2_ASSOC_DIAG=1``.  A detection is ``ambiguous_new``
when its second best candidate scores at least 0.67 of the best (01_source_association.AMBIG_SCORE_RATIO) and it is not a radio or
annotation row that the rules resolve: it then anchors an object of its own.  Per set and catalogue:

  detections, ambiguous (n, %)       the rows, and those that became a new object only because of the ambiguity
  clear_distance                     the nearest candidate is closer than 0.1'' and the second nearest at least 5 times further
  clear_nsep                         the nearest candidate is within 1 sigma and the second nearest more than 3 sigma away (a
                                     likelihood ratio of the two of at least 90 at equal sigma)
  same_object                        the anchors of the two best candidates agree within the sigma of their pair (nsep < 1):
                                     the candidates are the same physical object seen as two groups
  nearest_not_best                   the nearest candidate is not the one the score ranks first

and by the local density of objects (within 20'') for the same rows.  ``profiles.csv`` lists every catalogue that occurs in the raw
folders with its profile (or the default one), the median assumed position error of its rows and the rows that become ambiguous.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

V2 = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("association_model_amb", V2 / "Preprocess" / "association_model.py")
AM = importlib.util.module_from_spec(spec)
sys.modules["association_model_amb"] = AM  # dataclasses look the module up by name
spec.loader.exec_module(AM)

DENSITY_RADIUS = 20.0  # arcsec
DENSITY_EDGES = [0, 30, 100, math.inf]  # objects per arcmin^2
DENSITY_NAMES = ["< 30", "30-100", ">= 100"]


def xyz(ra, dec):
    a, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.c_[np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)]


def local_density(d: pd.DataFrame) -> np.ndarray:
    """Objects (anchors) per arcmin^2 within DENSITY_RADIUS of every detection, its own object left out."""
    obj = d.drop_duplicates("object_id")[["object_id", "object_ra", "object_dec"]]
    tree = cKDTree(xyz(obj.object_ra, obj.object_dec))
    r = 2 * math.sin(math.radians(DENSITY_RADIUS / 3600.0) / 2)
    counts = np.array([len(x) for x in tree.query_ball_point(xyz(d.object_ra, d.object_dec), r)]) - 1
    return counts / (math.pi * (DENSITY_RADIUS / 60.0) ** 2)


def split(s: str):
    return [float(x) for x in str(s).split("|")] if isinstance(s, str) and s else []


def load(stage1: Path) -> pd.DataFrame:
    parts = []
    for f in sorted(stage1.glob("*/*.csv.gz")):
        d = pd.read_csv(f, low_memory=False)
        if not len(d):
            continue
        d["set"], d["region"] = f.parent.name, f.name[: -len(".csv.gz")]
        d["density"] = local_density(d)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


FLAG_COLUMNS = ["nearest_sep", "second_sep", "nearest_nsep", "second_nsep", "clear_distance", "clear_nsep", "same_object", "nearest_not_best"]


def flags(d: pd.DataFrame) -> pd.DataFrame:
    """Per ambiguous detection: the distances and the clear / same-object flags."""
    amb = d[d.association_status == "ambiguous_new"].copy()
    rows = []
    for r in amb.itertuples():
        sep, nsep, score = split(r.diag_all_sep), split(r.diag_all_nsep), split(r.diag_all_score)
        o = np.argsort(sep)
        s1, s2 = (sep[o[0]], sep[o[1]]) if len(sep) > 1 else (math.nan, math.nan)
        n1, n2 = (nsep[o[0]], nsep[o[1]]) if len(sep) > 1 else (math.nan, math.nan)
        rows.append(dict(nearest_sep=s1, second_sep=s2, nearest_nsep=n1, second_nsep=n2,
                         clear_distance=bool(s1 < 0.1 and s2 >= 5 * s1) if len(sep) > 1 else False,
                         clear_nsep=bool(n1 <= 1.0 and n2 > 3.0) if len(sep) > 1 else False,
                         same_object=bool(getattr(r, "diag_c12_nsep", math.inf) < 1.0),
                         nearest_not_best=bool(o[0] != 0)))  # fmt: skip
    # the columns also when nothing is ambiguous (V2_ASSOC_AMBIG=best resolves every case), so that tables() writes zeros (Codex review of 2.61.8)
    return pd.concat([amb.reset_index(drop=True), pd.DataFrame(rows, columns=FLAG_COLUMNS)], axis=1)


def tables(d: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fl = flags(d)
    total = d.groupby(["set", "catalog"]).size().rename("detections")
    a = fl.groupby(["set", "catalog"]).agg(ambiguous=("object_id", "size"), clear_distance=("clear_distance", "sum"),
                                           clear_nsep=("clear_nsep", "sum"), same_object=("same_object", "sum"),
                                           nearest_not_best=("nearest_not_best", "sum"),
                                           median_candidates=("candidate_count", "median"))  # fmt: skip
    t = pd.concat([total, a], axis=1).fillna(0).reset_index()
    t["ambiguous_pct"] = (100 * t.ambiguous / t.detections).round(2)
    for c in ("clear_distance", "clear_nsep", "same_object", "nearest_not_best"):
        t[c + "_pct_of_ambiguous"] = (100 * t[c].astype(float) / t.ambiguous.astype(float).where(t.ambiguous > 0)).round(1)
    t.to_csv(out / "ambiguous_by_catalog.csv", index=False)
    # all catalogues of a set together
    s = (t.groupby("set")[["detections", "ambiguous", "clear_distance", "clear_nsep", "same_object", "nearest_not_best"]].sum().reset_index())
    s["ambiguous_pct"] = (100 * s.ambiguous / s.detections).round(2)
    for c in ("clear_distance", "clear_nsep", "same_object"):
        s[c + "_pct_of_ambiguous"] = (100 * s[c].astype(float) / s.ambiguous.astype(float).where(s.ambiguous > 0)).round(1)
    s.to_csv(out / "ambiguous_by_set.csv", index=False)
    # by local density
    d["density_class"] = pd.cut(d.density, DENSITY_EDGES, labels=DENSITY_NAMES, right=False)
    fl["density_class"] = pd.cut(fl.density, DENSITY_EDGES, labels=DENSITY_NAMES, right=False)
    dd = d.groupby(["set", "density_class"], observed=True).size().rename("detections")
    da = fl.groupby(["set", "density_class"], observed=True).agg(ambiguous=("object_id", "size"), clear_distance=("clear_distance", "sum"),
                                                                  clear_nsep=("clear_nsep", "sum"), same_object=("same_object", "sum"))  # fmt: skip
    q = pd.concat([dd, da], axis=1).fillna(0).reset_index()
    q["ambiguous_pct"] = (100 * q.ambiguous / q.detections).round(2)
    q.to_csv(out / "ambiguous_by_density.csv", index=False)
    # profiles
    rows = []
    for cat, g in d.groupby("catalog"):
        prof = AM.PROFILES.get(cat)
        rows.append(dict(catalog=cat, rows=len(g), has_profile=prof is not None or cat == "Suh 2021 AGB Catalog",
                         profile_poserr=prof.fallback_poserr_arcsec if prof else AM.DEFAULT_PROFILE.fallback_poserr_arcsec,
                         profile_psf=prof.psf_fwhm_arcsec if prof else None, profile_max_radius=prof.max_radius_arcsec if prof else AM.DEFAULT_PROFILE.max_radius_arcsec,
                         median_poserr_of_rows=round(float(g.poserr_arcsec.median()), 4), p10_poserr=round(float(g.poserr_arcsec.quantile(0.1)), 4),
                         p90_poserr=round(float(g.poserr_arcsec.quantile(0.9)), 4),
                         ambiguous=int((g.association_status == "ambiguous_new").sum()),
                         ambiguous_pct=round(100 * float((g.association_status == "ambiguous_new").mean()), 2)))  # fmt: skip
    pd.DataFrame(rows).sort_values("rows", ascending=False).to_csv(out / "profiles.csv", index=False)
    fl.drop(columns=[c for c in fl.columns if c.startswith("diag_c1_members") or c.startswith("diag_c2_members")]).to_csv(out / "ambiguous_rows.csv.gz", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(s.to_string(index=False))
        print(q.to_string(index=False))
        print(pd.DataFrame(rows).sort_values("rows", ascending=False).to_string(index=False))


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage1", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    tables(load(a.stage1), a.out)
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

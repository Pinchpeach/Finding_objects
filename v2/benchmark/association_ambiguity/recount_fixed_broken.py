#!/usr/bin/env python3
"""Fixed / broken labels of an association variant against the base, counted over EVERY truth object that has a matched object (2.61.10).

    python recount_fixed_broken.py --deep DIR [DIR ...] --names calibration confirmation --fields fields_all26.csv --base base --variant same_nearest --out OUT

``DIR/run_<variant>/<field>/classified_objects.csv`` and ``DIR/<field>/truth`` as ``benchmark/faint_qso_candidates.py`` reads them.  Why this exists:
``faint_qso_candidates.py compare`` (used by the 2.61.8 report) builds the truth pairs from the r-magnitude bins of Legacy Surveys, so a truth object
without an LS r magnitude (132 of 30 609 in the 17 confirmation fields: objects only a PS1 / SDSS row sees) is left out of the pairs, and 18 of the 20
labels the variant fixed were among them.  Here every matched truth object counts, with two readings of "the label of a truth object":

  nearest   the primary class of the object nearest to the truth position (``faint_qso_candidates.matched``): what a user gets from a cone search
  present   whether ANY object within ``--radius`` arcsec of the truth position carries the expected class (``EXPECTED``): it does not care which of
            two fragments is the nearest, so it separates "the evidence now sits in one nearer object" from "a class is now found that was not"

Also per truth object the number of objects within the radius (fragments), and ``broken.csv``: for every truth object the nearest reading breaks, the
objects within 3 arcsec in both runs (class, status, catalogues, separation), which is how the five broken confirmation objects were explained.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import faint_qso_candidates as FQ  # noqa: E402


def _xy(ra, dec, ra0, dec0):
    c = math.cos(math.radians(dec0))
    return np.c_[(np.asarray(ra, float) - ra0) * c * 3600.0, (np.asarray(dec, float) - dec0) * 3600.0]


def count_part(deep: Path, base: str, variant: str, fields: list[str], radius: float, near: float = 3.0):
    mb, mv = FQ.matched(deep, base), FQ.matched(deep, variant)
    mb, mv = mb[mb.field.isin(fields)], mv[mv.field.isin(fields)]
    m = mb.merge(mv, on=["field", "ra", "dec", "truth"], suffixes=("_b", "_v"))
    m["want"] = m.truth.map(FQ.EXPECTED)
    m["ok_b"], m["ok_v"] = m.o_primary_class_b == m.want, m.o_primary_class_v == m.want
    m["has_r"] = m.o_std_mag__ls_r_b.notna() if "o_std_mag__ls_r_b" in m else True
    present = {}
    listing = []
    for f, g in m.groupby("field"):
        runs = {}
        for tag, v in (("b", base), ("v", variant)):
            d = pd.read_csv(deep / f"run_{v}" / f / "classified_objects.csv", low_memory=False,
                            usecols=lambda c: c in {"object_id", "ra", "dec", "primary_class", "classification_status", "catalogs"})  # fmt: skip
            runs[tag] = d
        ra0, dec0 = float(g.ra.mean()), float(g.dec.mean())
        q = _xy(g.ra, g.dec, ra0, dec0)
        for tag in ("b", "v"):
            d = runs[tag]
            t = cKDTree(_xy(d.ra, d.dec, ra0, dec0))
            idx = t.query_ball_point(q, radius)
            wide = t.query_ball_point(q, near)
            cls = d.primary_class.to_numpy()
            present[(f, tag)] = (np.array([len(i) for i in idx]), np.array([bool(len(i)) and bool((cls[i] == w).any()) for i, w in zip(idx, g.want)]))
            if tag == "v":
                broken = (g.ok_b & ~g.ok_v).to_numpy()
                for k in np.flatnonzero(broken):
                    row = g.iloc[k]
                    for tg, dd, ww in (("base", runs["b"], t_b_wide(runs["b"], q[k], ra0, dec0, near)), ("variant", d, wide[k])):
                        for j in ww:
                            x = dd.iloc[j]
                            sep = float(np.hypot(*(_xy([x.ra], [x.dec], ra0, dec0)[0] - q[k])))
                            listing.append(dict(field=f, truth=row.truth, ra=row.ra, dec=row.dec, run=tg, object_id=x.object_id, sep_arcsec=round(sep, 2),
                                                primary_class=x.primary_class, status=x.classification_status, catalogs=x.catalogs))  # fmt: skip
        g_idx = g.index
        m.loc[g_idx, "n_b"], m.loc[g_idx, "any_b"] = present[(f, "b")]
        m.loc[g_idx, "n_v"], m.loc[g_idx, "any_v"] = present[(f, "v")]
    return m, pd.DataFrame(listing)


def t_b_wide(d: pd.DataFrame, q, ra0, dec0, near):
    t = cKDTree(_xy(d.ra, d.dec, ra0, dec0))
    return t.query_ball_point(q, near)


def mcnemar(fixed: int, broken: int) -> float:
    return 1.0 if fixed + broken == 0 else float(binomtest(min(fixed, broken), fixed + broken, 0.5).pvalue)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deep", type=Path, nargs="+", required=True)
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--fields", type=Path, required=True)
    ap.add_argument("--base", default="base")
    ap.add_argument("--variant", default="same_nearest")
    ap.add_argument("--radius", type=float, default=0.5)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    FQ.FIELDS = FQ.load_fields(a.fields)
    rows, lists, parts = [], [], []
    for deep, name in zip(a.deep, a.names):
        fields = sorted(f for f in FQ.FIELDS if (deep / f).exists() and (deep / f"run_{a.variant}" / f / "classified_objects.csv").exists())
        m, lst = count_part(deep, a.base, a.variant, fields, a.radius)
        m["part"] = name
        parts.append(m)
        lists.append(lst.assign(part=name))
    allm = pd.concat(parts)
    for name, g in [*allm.groupby("part"), ("all", allm)]:
        fx, br = int((~g.ok_b & g.ok_v).sum()), int((g.ok_b & ~g.ok_v).sum())
        fx2, br2 = int((~g.any_b & g.any_v).sum()), int((g.any_b & ~g.any_v).sum())
        no_r = g[~g.has_r]
        rows.append(dict(part=name, truth_matched=len(g), without_ls_r=len(no_r), fixed_nearest=fx, broken_nearest=br, p_nearest=round(mcnemar(fx, br), 5),
                         fixed_nearest_only_with_r=int((~g[g.has_r].ok_b & g[g.has_r].ok_v).sum()), broken_nearest_only_with_r=int((g[g.has_r].ok_b & ~g[g.has_r].ok_v).sum()),
                         fixed_nearest_without_r=int((~no_r.ok_b & no_r.ok_v).sum()), broken_nearest_without_r=int((no_r.ok_b & ~no_r.ok_v).sum()),
                         fixed_present=fx2, broken_present=br2, p_present=round(mcnemar(fx2, br2), 5),
                         objects_within_radius_base=round(float(g.n_b.mean()), 4), objects_within_radius_variant=round(float(g.n_v.mean()), 4)))  # fmt: skip
    pd.DataFrame(rows).to_csv(a.out / "fixed_broken_all_matched.csv", index=False)
    pd.concat(lists).to_csv(a.out / "broken.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(pd.DataFrame(rows).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

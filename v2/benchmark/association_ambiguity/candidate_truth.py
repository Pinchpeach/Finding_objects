#!/usr/bin/env python3
"""For every ``ambiguous_new`` row of the deep COSMOS fields: which candidate was the right object? (2.61.7)

    python candidate_truth.py --stage1 DIR --truth-flux DIR --out OUT [--fields-split CSV]

``--stage1`` holds ``<set>/<field>.csv.gz`` of ``run_stage1.py`` written with ``V2_ASSOC_DIAG=1`` (``diag_all_object`` = the
accepted candidates in best-score order).  The truth definitions are those of ``association_truth/measure_association.py``
(COSMOS2020, 2.60.9): a resolving row (Legacy Surveys, PS1, SDSS, Gaia, SGA) has the truth source within 0.6'' of it; the
truth ids of an object are those of its resolving rows; a low-resolution row (AllWISE, 2MASS, GALEX) has the acceptable set
A(d) of the sources that put at least a quarter of the flux of the dominant one into its PSF.

A candidate is *right* when its object holds the row's truth source (resolving row) or a source of A(d) (low-resolution row),
*wrong* when the object has truth ids and none of them fits, *unknown* when the object has no truth id.  Per row:

  best_score  the first candidate in score order (what the 0.67 rule compares with the second)
  nearest     the candidate closest to the row
  any         some candidate is right

and, for the rule "join the nearest candidate when its separation is below ``s0`` and the second nearest is at least ``k`` times
as far" (and the likelihood-ratio form ``exp((n2^2 - n1^2) / 2) >= L`` of the normalised separations), how many rows it would
join, and how many of those joins are right / wrong / unknown.  These are the numbers the thresholds of the variants are set from.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sp = importlib.util.spec_from_file_location("measure_association", V2 / "benchmark" / "association_truth" / "measure_association.py")
MA = importlib.util.module_from_spec(sp)
sys.modules["measure_association"] = MA
sp.loader.exec_module(MA)

S0 = [0.05, 0.1, 0.2, 0.3, 0.5]
K = [2, 3, 5, 10]
LR = [3, 10, 30, 100]


def split(s):
    return [x for x in str(s).split("|")] if isinstance(s, str) and s else []


def field_rows(assoc: pd.DataFrame, truth: pd.DataFrame, name: str) -> list[dict]:
    ref = truth[truth["HSCimagAuto"] < MA.REF_MAG]
    ref_ids = ref.index.to_numpy()
    ref_sky = MA.Sky(ref.ra, ref.dec)
    full_sky = MA.Sky(truth.ra, truth.dec)
    a = assoc.copy()
    res = a.catalog.isin(MA.RESOLVING)
    a["truth_id"] = -1
    i, _ = ref_sky.nearest(a.loc[res, "ra"].to_numpy(float), a.loc[res, "dec"].to_numpy(float), MA.ID_RADIUS)
    a.loc[res, "truth_id"] = np.where(i >= 0, ref_ids[np.maximum(i, 0)], -1)
    T = {oid: set(int(x) for x in g.truth_id[g.catalog.isin(MA.RESOLVING) & (g.truth_id >= 0)]) for oid, g in a.groupby("object_id")}
    anchors = a.drop_duplicates("object_id").set_index("object_id")[["object_ra", "object_dec"]]
    empty = [o for o, ids in T.items() if not ids]
    if empty:
        i, _ = ref_sky.nearest(anchors.loc[empty, "object_ra"].to_numpy(float), anchors.loc[empty, "object_dec"].to_numpy(float), MA.ID_RADIUS)
        for o, k in zip(empty, i):
            if k >= 0:
                T[o] = {int(ref_ids[k])}
    amb = a[a.association_status == "ambiguous_new"]
    out = []
    accept = {}
    for cat, (col, fwhm) in MA.LOWRES.items():
        d = amb[amb.catalog == cat]
        if len(d) and col in truth:
            dom, acc = MA.expected_counterparts(d, truth, full_sky, col, fwhm)
            accept.update({r: set(ac) for r, ac in zip(d.index, acc)})
    for idx, r in amb.iterrows():
        objs, sep, nsep = split(r.diag_all_object), [float(x) for x in split(r.diag_all_sep)], [float(x) for x in split(r.diag_all_nsep)]
        if len(objs) < 2:
            continue
        if r.catalog in MA.RESOLVING:
            want = {int(r.truth_id)} if r.truth_id >= 0 else set()
        elif idx in accept:
            want = accept[idx]
        else:
            want = None
        verdict = []
        for o in objs:
            ids = T.get(o, set())
            verdict.append("unknown" if want is None or not want or not ids else ("right" if ids & want else "wrong"))
        near = int(np.argmin(sep))
        order = np.argsort(sep)
        s1, s2 = sep[order[0]], sep[order[1]]
        n1, n2 = nsep[order[0]], nsep[order[1]]
        out.append(dict(field=name, detection_id=r.detection_id, catalog=r.catalog, ra=r.ra, dec=r.dec, n_candidates=len(objs),
                        has_truth=bool(want), best_score=verdict[0], nearest=verdict[near], any_right="right" in verdict,
                        n_right=verdict.count("right"), nearest_is_best=near == 0, sep1=s1, sep2=s2, nsep1=n1, nsep2=n2,
                        lr_pos=math.exp(min(50.0, 0.5 * (n2 * n2 - n1 * n1))),
                        same_truth=bool(len({frozenset(T.get(o, set())) for o in objs[:2]}) == 1 and T.get(objs[0])),
                        c12_nsep=getattr(r, "diag_c12_nsep", np.nan), c12_sep=getattr(r, "diag_c12_sep", np.nan),
                        density=r.source_density_arcsec2))  # fmt: skip
    return out


def summarise(df: pd.DataFrame, out: Path) -> None:
    d = df[df.has_truth].copy()
    rows = []
    for cat, g in list(d.groupby("catalog")) + [("all resolving", d[d.catalog.isin(MA.RESOLVING)]), ("all low-res", d[d.catalog.isin(MA.LOWRES)])]:
        n = len(g)
        rows.append(dict(catalog=cat, ambiguous_with_truth=n, best_right=int((g.best_score == "right").sum()), nearest_right=int((g.nearest == "right").sum()),
                         nearest_wrong=int((g.nearest == "wrong").sum()), any_right=int(g.any_right.sum()), both_top2_same_truth=int(g.same_truth.sum()),
                         nearest_is_best=int(g.nearest_is_best.sum())))  # fmt: skip
    t = pd.DataFrame(rows)
    for c in ("best_right", "nearest_right", "nearest_wrong", "any_right", "both_top2_same_truth", "nearest_is_best"):
        t[c + "_pct"] = (100 * t[c] / t.ambiguous_with_truth.where(t.ambiguous_with_truth > 0)).round(1)
    t.to_csv(out / "candidate_truth_by_catalog.csv", index=False)
    grid = []
    groups = {"resolving": d[d.catalog.isin(MA.RESOLVING)], "AllWISE": d[d.catalog == "AllWISE"], "GALEX AIS": d[d.catalog == "GALEX AIS"], "2MASS PSC": d[d.catalog == "2MASS PSC"]}
    for gname, g in groups.items():
        for s0 in S0:
            for k in K:
                m = g[(g.sep1 < s0) & (g.sep2 >= k * g.sep1.clip(lower=1e-3))]
                grid.append(dict(group=gname, rule=f"sep<{s0} and second>={k}x", rows=len(m), right=int((m.nearest == "right").sum()), wrong=int((m.nearest == "wrong").sum()),
                                 unknown=int((m.nearest == "unknown").sum()), of_group=len(g)))  # fmt: skip
        for L in LR:
            m = g[g.lr_pos >= L]
            grid.append(dict(group=gname, rule=f"LR_pos>={L}", rows=len(m), right=int((m.nearest == "right").sum()), wrong=int((m.nearest == "wrong").sum()),
                             unknown=int((m.nearest == "unknown").sum()), of_group=len(g)))  # fmt: skip
    # the two best candidates: are they one object?  (truth: the same COSMOS2020 source) by the distance of their anchors
    same = []
    for gname, g in {"resolving": d[d.catalog.isin(MA.RESOLVING)], "low-res": d[d.catalog.isin(MA.LOWRES)]}.items():
        g = g[g.c12_sep.notna()]
        for lo, hi in [(0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 0.8), (0.8, 1.2), (1.2, 2.0), (2.0, 99)]:
            m = g[(g.c12_sep >= lo) & (g.c12_sep < hi)]
            same.append(dict(group=gname, c12_sep=f"{lo}-{hi}", rows=len(m), same_truth=int(m.same_truth.sum()), best_right=int((m.best_score == "right").sum()),
                             best_wrong=int((m.best_score == "wrong").sum())))  # fmt: skip
        for lo, hi in [(0, 0.5), (0.5, 1), (1, 2), (2, 3), (3, 5), (5, 99)]:
            m = g[(g.c12_nsep >= lo) & (g.c12_nsep < hi)]
            same.append(dict(group=gname, c12_sep=f"nsep {lo}-{hi}", rows=len(m), same_truth=int(m.same_truth.sum()), best_right=int((m.best_score == "right").sum()),
                             best_wrong=int((m.best_score == "wrong").sum())))  # fmt: skip
    st = pd.DataFrame(same)
    st["same_truth_pct"] = (100 * st.same_truth / st.rows.where(st.rows > 0)).round(1)
    st.to_csv(out / "same_object_by_c12.csv", index=False)
    print(st.to_string(index=False))
    gr = pd.DataFrame(grid)
    gr["wrong_pct_of_known"] = (100 * gr.wrong / (gr.right + gr.wrong).where((gr.right + gr.wrong) > 0)).round(1)
    gr.to_csv(out / "nearest_rule_grid.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 300):
        print(t.to_string(index=False))
        print(gr[gr.rows > 0].to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage1", type=Path, required=True)
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sets", default="cosmos_orig9,cosmos_new17")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    fs = pd.read_csv(V2 / "benchmark" / "association_truth" / "fields_split.csv").set_index("name")
    rows = []
    for s in a.sets.split(","):
        for f in sorted((a.stage1 / s).glob("*.csv.gz")):
            name = f.name[: -len(".csv.gz")]
            truth = MA.load_truth(a.truth_flux / f"{name}.csv.gz", (fs.ra[name], fs.dec[name]))
            assoc = pd.read_csv(f, low_memory=False, dtype={"catalog_object_id": "string"})
            for r in field_rows(assoc, truth, name):
                r["set"] = s
                rows.append(r)
            print(name, len(rows), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out / "candidate_truth_rows.csv.gz", index=False)
    summarise(df, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

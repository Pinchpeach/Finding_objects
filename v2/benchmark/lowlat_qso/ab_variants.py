#!/usr/bin/env python3
"""The recall / false-QSO-density trade of the low-latitude switches, one row per variant (2.61.3).

    python ab_variants.py --variants base=ROOT1 surveys2=ROOT2 ... --regions fields_lowlat.csv --truth lowlat_truth.csv.gz --out DIR

``ROOT`` of a variant: ``<region>/objects.csv.gz`` (+ ``raw`` for the PS1 magnitudes), made by ``score_lowlat_qso.py compact``.  Per variant:

  recall                 QSO labels among the sample quasars (n = 150), Wilson 95 % interval, and by |b| stratum
  false density          objects labelled QSO that are not a sample quasar, per square degree of the cones: all, with PS1 i < 19.5,
                         and the ones with two or more catalogues; the interval is a bootstrap over the regions (the false labels
                         cluster in a few regions, so the Poisson interval is too narrow: 30 of 170 sit in one cone)
  non-quasars            how many of the 19 known stars and galaxies are labelled QSO
  exchange               false objects removed and sample quasars lost against the first variant (the control)

Every variant is scored on the same regions (2.61.3 review): a region without a record in any variant's root is left out of all of
them (recall, density and the paired exchange alike), listed in ``coverage.json`` and announced as INCOMPLETE, so an interrupted run
cannot look like quasars lost or a smaller false density.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_lowlat_qso as S  # noqa: E402


def region_counts(res: dict) -> pd.DataFrame:
    others = res["qso_other"]
    reg = res["per_region"]
    reg = reg[(reg.status == "ok") & (reg.kind == "qso")][["name", "area_deg2"]].copy()
    if len(others):
        o = others[others.stratum != "contaminant"].copy()
        o["i195"] = o.ps1_i < 19.5
        o["multi"] = o.n_catalogs >= 2
        o["multi_i195"] = o.multi & o.i195
        g = o.groupby("region").agg(all=("object_id", "size"), i195=("i195", "sum"), multi=("multi", "sum"), multi_i195=("multi_i195", "sum"))
        reg = reg.merge(g, left_on="name", right_index=True, how="left")
    for c in ("all", "i195", "multi", "multi_i195"):
        if c not in reg:
            reg[c] = 0
    return reg.fillna(0)


def boot_density(reg: pd.DataFrame, col: str, n_boot=4000, seed=1):
    rng = np.random.default_rng(seed)
    x, a = reg[col].to_numpy(float), reg.area_deg2.to_numpy(float)
    est = x.sum() / a.sum()
    idx = rng.integers(0, len(x), (n_boot, len(x)))
    b = x[idx].sum(1) / a[idx].sum(1)
    return est, float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", nargs="+", required=True, help="NAME=ROOT, the first is the control")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--radius", type=float, default=3.0)
    ap.add_argument("--only", help="comma list of region names (the calibration or the confirmation set)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    regions, truth = pd.read_csv(a.regions), pd.read_csv(a.truth)
    if a.only:
        regions = regions[regions.name.isin(a.only.split(","))]
    # one common set of regions: a region missing from any variant is left out of every variant
    specs = [v.split("=", 1) for v in a.variants]
    missing = {nm: sorted(n for n in regions.name if not (Path(root) / n / "objects.csv.gz").exists()) for nm, root in specs}
    excluded = sorted(set().union(*missing.values()))
    if excluded:
        print(f"INCOMPLETE: {len(excluded)} region(s) lack a record in at least one variant and are left out of every variant: "
              + ", ".join(excluded))  # fmt: skip
        regions = regions[~regions.name.isin(excluded)]
    (a.out / "coverage.json").write_text(json.dumps(dict(regions_compared=int(len(regions)), regions_excluded=excluded,
                                                         missing_by_variant=missing, complete=not excluded), indent=1) + "\n")  # fmt: skip
    rows, strata, control = [], [], None
    per_object, per_quasar = None, None  # one table each, one column per variant (the labels the numbers come from)
    for spec in a.variants:
        name, root = spec.split("=", 1)
        res = S.score_regions(regions, truth, Path(root), a.radius)
        T = res["per_truth"]
        q = T[T.cls == "qso"].set_index("region")
        n, k = len(q), int((q.label == "QSO").sum())
        lo, hi = S.wilson(k, n)
        reg = region_counts(res)
        r = dict(variant=name, quasars=n, recall_qso=k, recall=round(k / n, 4), recall_lo=round(lo, 4), recall_hi=round(hi, 4))
        for col, lab in (("all", "false_all"), ("i195", "false_i_lt_195"), ("multi", "false_multi_survey"), ("multi_i195", "false_multi_survey_i_lt_195")):
            est, l, h = boot_density(reg, col)
            r.update({f"{lab}_n": int(reg[col].sum()), f"{lab}_per_deg2": round(est, 2), f"{lab}_lo": round(l, 2), f"{lab}_hi": round(h, 2)})
        c = T[T.cls.isin(["star", "galaxy"])]
        r["nonquasars_labelled_qso"] = f"{int((c.label == 'QSO').sum())}/{len(c)}"
        for s, g in q.groupby("stratum"):
            kk = int((g.label == "QSO").sum())
            l2, h2 = S.wilson(kk, len(g))
            sr = regions[(regions.stratum == s) & regions.name.isin(reg.name)]
            area = float(reg[reg.name.isin(sr.name)].area_deg2.sum())
            nfalse = int(len(res["qso_other"][(res["qso_other"].stratum == s)]))
            strata.append(dict(variant=name, stratum=s, n=len(g), qso=kk, recall=round(kk / len(g), 4), lo=round(l2, 4), hi=round(h2, 4),
                               regions=len(sr), area_deg2=round(area, 4), false_n=nfalse, false_per_deg2=round(nfalse / area, 2) if area else float("nan")))  # fmt: skip
        oth = res["qso_other"][res["qso_other"].stratum != "contaminant"].copy()
        oth["key"] = oth.object_id.astype(str) + "@" + oth.region
        now = set(oth.key)
        if control is None:
            control = (set(q.name[q.label == "QSO"]), set(oth.key), oth)
        lost = len(control[0] - set(q.name[q.label == "QSO"]))  # per quasar (a cone can hold several)
        r["quasars_lost_vs_control"] = lost
        r["false_removed_vs_control"] = len(control[1] - now)
        r["false_added_vs_control"] = len(now - control[1])
        # the objects a switch removes are a subset of the control's: a paired bootstrap over the regions of the removed density
        if control is not None and name != a.variants[0].split("=", 1)[0]:
            ctl = control[2]
            removed = ctl[~ctl.key.isin(now)].groupby("region").size()
            rr = reg[["name", "area_deg2"]].copy()
            rr["removed"] = rr.name.map(removed).fillna(0)
            est, l, h = boot_density(rr, "removed")
            r.update(removed_per_deg2=round(est, 2), removed_lo=round(l, 2), removed_hi=round(h, 2))
        rows.append(r)
        o = oth.drop(columns=["key"]).assign(**{name: True})
        key = ["region", "object_id"]
        per_object = o if per_object is None else per_object.merge(o[key + [name]], on=key, how="outer")
        t = q.reset_index()[["region", "name", "sample", "stratum", "b", "l", "imag", "z", "n_catalogs", "label"]].rename(columns={"label": name})
        per_quasar = t if per_quasar is None else per_quasar.merge(t[["name", name]], on="name", how="outer")
    for c in [v.split("=", 1)[0] for v in a.variants]:
        per_object[c] = per_object[c].where(per_object[c].notna(), False).astype(bool)
    per_object.to_csv(a.out / "qso_labelled_not_sample_by_variant.csv.gz", index=False)
    per_quasar.to_csv(a.out / "sample_quasars_by_variant.csv", index=False)
    d = pd.DataFrame(rows)
    d.to_csv(a.out / "ab_variants.csv", index=False)
    pd.DataFrame(strata).to_csv(a.out / "ab_variants_by_stratum.csv", index=False)
    with pd.option_context("display.width", 260, "display.max_columns", 40):
        print(d.to_string(index=False))
        print(pd.DataFrame(strata).pivot(index="variant", columns="stratum", values="recall").to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

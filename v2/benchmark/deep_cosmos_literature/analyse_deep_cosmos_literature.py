#!/usr/bin/env python3
"""What the NED / SIMBAD rows of the deep COSMOS fields say about literature-only objects and the literature switches (2.62.7, task "더"; predictions: PREDICTIONS_2026-11-28.md).

    python analyse_deep_cosmos_literature.py --runs DIR --merged-root DIR --truth-flux DIR --out OUT [--variants base typed_close err qual_ned_unc] [--fields deep_cosmos_1 ...]

``--runs``         ``DIR/<variant>/<field>/source_association.csv``: Stage 1 on the MERGED raw folders (``association_truth/run_variant.py --fields-root MERGED --env ...``), the first
                   variant being the control.
``--merged-root``  the output of ``merge_deep_cosmos_literature.py`` (the raw rows: fill rates of the error columns).
``--truth-flux``   ``DIR/<field>.csv.gz`` of ``association_truth/collect_truth_flux.py`` (COSMOS2020); the same truth ``association_ambiguity/literature_variants.py`` used on the real-use cone.

Written per field and pooled:

* ``share.csv``            objects, literature-only objects (every row NED / SIMBAD) and their share, literature rows (``literature_only.py``'s reading);
* ``nearest_survey.csv``   the distance of every literature-only object to the nearest object that holds a survey row, in bins, against a control of random positions of the same number in
                           the same cone (the real-use cone found the 1-2'' bin equal to the control: the objects are genuinely absent from the surveys, not unmatched);
* ``joins.csv``            for each variant after the first: the new joins against the control with the bridge of ``literature_variants.py`` (right / wrong / unknown, the predeclared
                           and the extended bridge), literature-only objects, label-free QSO objects attached, lit-lit merges, the share of joins beyond 0.6'' of the object;
* ``fill_rates.csv``       SIMBAD ``coo_err_maj`` and ``coo_qual`` and NED ``ned_unc_maj_arcsec`` filled, the grade distribution and the NED name / position matching.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH / "association_truth"))
sys.path.insert(0, str(BENCH / "association_ambiguity"))
import literature_variants as LV  # noqa: E402
import measure_association as MA  # noqa: E402
import run_info as RI  # noqa: E402

BINS = [0.0, 0.6, 1.13, 2.0, 3.0, 5.0, 10.0, np.inf]
LIT = LV.LIT


def field_frame(runs: Path, variant: str, field: str) -> pd.DataFrame:
    return LV.load(runs / variant / field)


def nearest_distances(a: pd.DataFrame, rng: np.random.Generator, radius_arcmin: float = 6.0, centre=None) -> tuple[np.ndarray, np.ndarray]:
    """(observed, control) distances in arcsec of the literature-only objects to the nearest survey object; the control draws the same number of random positions in the cone."""
    o = LV.objects(a)
    surv, lit = o[~o.lit_only], o[o.lit_only]
    if not len(surv) or not len(lit):
        return np.array([]), np.array([])
    ra0, de0 = centre if centre is not None else (float(o.ra.mean()), float(o.dec.mean()))
    c = np.cos(np.radians(de0))
    tree = cKDTree(np.c_[(surv.ra.to_numpy() - ra0) * c * 3600.0, (surv.dec.to_numpy() - de0) * 3600.0])
    obs, _ = tree.query(np.c_[(lit.ra.to_numpy() - ra0) * c * 3600.0, (lit.dec.to_numpy() - de0) * 3600.0])
    r = radius_arcmin * 60.0 * np.sqrt(rng.random(len(lit)))
    th = 2 * np.pi * rng.random(len(lit))
    ctrl, _ = tree.query(np.c_[r * np.cos(th), r * np.sin(th)])
    return obs, ctrl


def binned(x: np.ndarray) -> list[int]:
    return [int(((x >= lo) & (x < hi)).sum()) for lo, hi in zip(BINS[:-1], BINS[1:])]


def fill_rates(merged: Path, field: str) -> dict:
    raw = next(iter((merged / field / "raw").glob("*")))
    out = {"field": field}
    s = pd.read_csv(next(raw.glob("simbad_*.csv")), low_memory=False)
    out["simbad_rows"] = len(s)
    out["simbad_coo_err_maj_filled"] = int(pd.to_numeric(s.get("coo_err_maj"), errors="coerce").notna().sum()) if "coo_err_maj" in s else 0
    out["simbad_coo_qual_filled"] = int(s["coo_qual"].notna().sum()) if "coo_qual" in s else 0
    if "coo_qual" in s:
        for g, n in s["coo_qual"].value_counts().items():
            out[f"simbad_grade_{g}"] = int(n)
    n = pd.read_csv(next(raw.glob("ned_*.csv")), low_memory=False)
    out["ned_rows"] = len(n)
    out["ned_unc_filled"] = int(pd.to_numeric(n.get("ned_unc_maj_arcsec"), errors="coerce").notna().sum()) if "ned_unc_maj_arcsec" in n else 0
    for src in ("name", "position"):
        out[f"ned_unc_by_{src}"] = int((n.get("ned_unc_source") == src).sum()) if "ned_unc_source" in n else 0
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--merged-root", type=Path, required=True)
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", default=["base", "typed_close", "err", "qual_ned_unc"])
    ap.add_argument("--fields", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    base = a.variants[0]
    fields = a.fields or sorted(p.name for p in (a.runs / base).iterdir() if p.is_dir())
    rng = np.random.default_rng(a.seed)
    share, near, joins, fills = [], [], [], []
    for f in fields:
        b = field_frame(a.runs, base, f)
        o = LV.objects(b)
        share.append(dict(field=f, objects=len(o), lit_only=int(o.lit_only.sum()), lit_only_share_pct=round(100 * float(o.lit_only.mean()), 1), lit_rows=int(b.is_lit.sum())))
        meta = json.loads((a.merged_root / f / "field.json").read_text()) if (a.merged_root / f / "field.json").exists() else {}
        centre = (meta["ra"], meta["dec"]) if "ra" in meta else None
        obs, ctrl = nearest_distances(b, rng, radius_arcmin=float(meta.get("radius_arcmin", 6.0)), centre=centre)
        near.append(dict(field=f, kind="observed", n=len(obs), **dict(zip([f"d{lo:g}-{hi:g}" for lo, hi in zip(BINS[:-1], BINS[1:])], binned(obs)))))
        near.append(dict(field=f, kind="control", n=len(ctrl), **dict(zip([f"d{lo:g}-{hi:g}" for lo, hi in zip(BINS[:-1], BINS[1:])], binned(ctrl)))))
        truth = MA.load_truth(a.truth_flux / f"{f}.csv.gz")
        qso = set()
        for v in a.variants[1:]:
            res, new = LV.compare(b, field_frame(a.runs, v, f), truth, qso)
            sep = new.separation if len(new) else pd.Series(dtype=float)
            joins.append(dict(field=f, variant=v, **res, joins_beyond_0p6_arcsec=int((sep > 0.6).sum()), joins_beyond_0p6_unknown=int(((sep > 0.6) & (new.verdict_ext == "unknown")).sum()) if len(new) else 0))
        fills.append(fill_rates(a.merged_root, f))
    pd.DataFrame(share).to_csv(a.out / "share.csv", index=False)
    nd = pd.DataFrame(near)
    nd.to_csv(a.out / "nearest_survey.csv", index=False)
    pd.DataFrame(joins).to_csv(a.out / "joins.csv", index=False)
    pd.DataFrame(fills).to_csv(a.out / "fill_rates.csv", index=False)
    pooled = nd.groupby("kind").sum(numeric_only=True)
    pooled["excess_vs_control_pct"] = np.nan
    obs, ctrl = pooled.loc["observed"], pooled.loc["control"]
    pd.DataFrame({"observed": obs, "control": ctrl, "observed_over_control": (obs / ctrl.replace(0, np.nan)).round(2)}).to_csv(a.out / "nearest_survey_pooled.csv")
    sh = pd.DataFrame(share)
    print(f"{len(fields)} fields: literature-only share median {sh.lit_only_share_pct.median():.1f} % (min {sh.lit_only_share_pct.min():.1f}, max {sh.lit_only_share_pct.max():.1f})")
    print(pd.DataFrame({"observed": obs, "control": ctrl}).T.to_string())
    RI.write_args(a, ["runs", "merged_root", "truth_flux"], t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

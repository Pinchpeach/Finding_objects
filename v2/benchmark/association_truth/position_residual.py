#!/usr/bin/env python3
"""How far is the position of an object from the true position of its source? (2.62.7, task "너": the order of Stage 1 and the anchor position; predictions: PREDICTIONS_POSITION_RESIDUAL_2026-11-28.md)

    python position_residual.py --runs ROOT --variants new=DIR file=DIR ... --truth-flux DIR --out OUT [--fields deep_cosmos_1 ...]

``--variants NAME=DIR``  ``DIR/<field>/source_association.csv`` of one Stage-1 run (``run_variant.py``); the FIRST variant is the reference of the paired comparison.
``--truth-flux``        ``DIR/<field>.csv.gz`` of ``collect_truth_flux.py`` (COSMOS2020; ``HSCimagAuto``).

Definition (fixed before the first run): an object is the group of Stage 1 and its position is ``object_ra`` / ``object_dec`` (the anchor's).  It reaches the truth when a row of a resolving
catalogue (``measure_association.RESOLVING``) lies within 0.6'' of a COSMOS2020 source with HSC i < 25 (the identification of ``measure_association.py``); an object whose resolving rows reach
exactly ONE truth source is a *clean* object, and its residual is the distance between the object position and that source.  Not defined for the others (no resolving row, or several sources).

Written (``OUT``):
* ``residual_summary.csv``  per variant and slice (all, by HSC i bin, by anchor catalogue): objects, median, 90 / 99 percentile, share beyond 0.3 / 0.5 / 0.7 / 1.0'';
* ``residual_paired.csv``   per variant against the first one, for the truth sources that have a clean single object in both: median and mean difference, how many got worse / better by more than 0.1'',
                            how many crossed 0.5'' either way, and the anchor transitions of the sources that got worse;
* ``design_summary.csv``    the output position as a design choice, on the groups of the first variant: ``anchor`` (as it is), ``best_member`` (the member with the smallest
                            ``effective_sigma_arcsec``, the position of the most precise list), ``ivw_mean`` (inverse-variance weighted mean of the resolving members, weights 1 / sigma^2).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "Preprocess"))
import measure_association as MA  # noqa: E402
import run_info as RI  # noqa: E402

THRESHOLDS = (0.3, 0.5, 0.7, 1.0)
IBINS = [(-np.inf, 20.0, "i<20"), (20.0, 22.0, "20-22"), (22.0, 24.0, "22-24"), (24.0, 25.0, "24-25")]


def sep_arcsec(ra1, dec1, ra2, dec2) -> np.ndarray:
    d = np.radians(dec2)
    dra = (np.asarray(ra1) - np.asarray(ra2)) * np.cos(d)
    return np.hypot(dra, np.asarray(dec1) - np.asarray(dec2)) * 3600.0


def eff_sigma(a: pd.DataFrame) -> np.ndarray:
    """``association_model.effective_sigma_arcsec`` without the proper-motion term, vectorised (checked against the function in the tests of this tool's author)."""
    pos = np.maximum(pd.to_numeric(a.poserr_arcsec, errors="coerce").fillna(99.0).to_numpy(float), 0.02)
    psf = pd.to_numeric(a.psf_fwhm_arcsec, errors="coerce").to_numpy(float)
    return np.where(np.isfinite(psf), np.maximum(pos, psf / 6.0), pos)


def clean_objects(a: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """One row per clean object: object_id, truth id, residual of the anchor position, anchor catalogue, HSC i of the truth source."""
    ref = truth[truth["HSCimagAuto"] < MA.REF_MAG]
    sky = MA.Sky(ref.ra.to_numpy(float), ref.dec.to_numpy(float))
    res = a[a.catalog.isin(MA.RESOLVING)]
    i, _ = sky.nearest(res.ra.to_numpy(float), res.dec.to_numpy(float), MA.ID_RADIUS)
    ok = i >= 0
    pairs = pd.DataFrame({"object_id": res.object_id.to_numpy()[ok], "tid": ref.index.to_numpy()[i[ok]]}).drop_duplicates()
    n = pairs.groupby("object_id").tid.nunique()
    pairs = pairs[pairs.object_id.isin(n[n == 1].index)]
    o = a.drop_duplicates("object_id").set_index("object_id")[["object_ra", "object_dec", "object_anchor_catalog"]]
    out = pairs.join(o, on="object_id")
    out["truth_ra"], out["truth_dec"] = truth.ra.reindex(out.tid).to_numpy(), truth.dec.reindex(out.tid).to_numpy()
    out["imag"] = truth["HSCimagAuto"].reindex(out.tid).to_numpy()
    out["residual"] = sep_arcsec(out.object_ra, out.object_dec, out.truth_ra, out.truth_dec)
    return out


def summarise(r: pd.Series) -> dict:
    r = r.dropna()
    d = dict(objects=len(r), median=float(r.median()) if len(r) else np.nan, p90=float(r.quantile(0.9)) if len(r) else np.nan, p99=float(r.quantile(0.99)) if len(r) else np.nan)
    for t in THRESHOLDS:
        d[f"beyond_{t}_pct"] = round(100 * float((r > t).mean()), 2) if len(r) else np.nan
    return d


def slices(c: pd.DataFrame):
    yield "all", "all", c
    for lo, hi, name in IBINS:
        yield "imag", name, c[(c.imag >= lo) & (c.imag < hi)]
    for cat, g in c.groupby("object_anchor_catalog"):
        if len(g) >= 50:
            yield "anchor", str(cat), g


def designs(a: pd.DataFrame, clean: pd.DataFrame, truth: pd.DataFrame) -> dict[str, np.ndarray]:
    """Residuals of the clean objects of ``a`` when the output position is the anchor / the most precise member / the inverse-variance mean of the resolving members."""
    m = a[a.object_id.isin(clean.object_id)].copy()
    m["sigma"] = eff_sigma(m)
    t = clean.set_index("object_id")
    best = m.sort_values(["object_id", "sigma"], kind="mergesort").drop_duplicates("object_id").set_index("object_id")
    b = sep_arcsec(best.ra.reindex(t.index), best.dec.reindex(t.index), t.truth_ra, t.truth_dec)
    r = m[m.catalog.isin(MA.RESOLVING)].copy()
    r["w"] = 1.0 / r.sigma**2
    r["x"], r["y"] = (r.ra - r.object_ra) * np.cos(np.radians(r.object_dec)) * 3600.0, (r.dec - r.object_dec) * 3600.0
    g = r.groupby("object_id")
    wx, wy = (r.w * r.x).groupby(r.object_id).sum() / g.w.sum(), (r.w * r.y).groupby(r.object_id).sum() / g.w.sum()
    ra = t.object_ra + wx.reindex(t.index).fillna(0.0) / 3600.0 / np.cos(np.radians(t.object_dec))
    dec = t.object_dec + wy.reindex(t.index).fillna(0.0) / 3600.0
    iv = sep_arcsec(ra, dec, t.truth_ra, t.truth_dec)
    return {"anchor": t.residual.to_numpy(float), "best_member": np.asarray(b, float), "ivw_mean": np.asarray(iv, float)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", nargs="+", required=True, help="NAME=DIR, the first is the reference")
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields", nargs="*", default=[])
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    runs = [(kv.split("=", 1)[0], Path(kv.split("=", 1)[1])) for kv in a.variants]
    fields = a.fields or sorted(p.name for p in runs[0][1].iterdir() if p.is_dir())
    clean: dict[str, list[pd.DataFrame]] = {n: [] for n, _ in runs}
    des: dict[str, list[np.ndarray]] = {"anchor": [], "best_member": [], "ivw_mean": []}
    des_i: list[np.ndarray] = []
    for f in fields:
        truth = MA.load_truth(a.truth_flux / f"{f}.csv.gz")
        for k, (name, d) in enumerate(runs):
            asc = pd.read_csv(d / f / "source_association.csv", low_memory=False)
            c = clean_objects(asc, truth)
            c["field"] = f
            clean[name].append(c)
            if k == 0:
                for key, v in designs(asc, c, truth).items():
                    des[key].append(v)
                des_i.append(c.imag.to_numpy(float))
    C = {n: pd.concat(v, ignore_index=True) for n, v in clean.items()}
    rows = []
    for n, c in C.items():
        for kind, name, g in slices(c):
            rows.append(dict(variant=n, slice_kind=kind, slice=name, **summarise(g.residual)))
    pd.DataFrame(rows).to_csv(a.out / "residual_summary.csv", index=False)
    ref_name = runs[0][0]
    ref = C[ref_name].set_index(["field", "tid"])
    ref = ref[~ref.index.duplicated(keep=False)]
    prow = []
    for n, c in C.items():
        if n == ref_name:
            continue
        v = c.set_index(["field", "tid"])
        v = v[~v.index.duplicated(keep=False)]
        idx = ref.index.intersection(v.index)
        r0, r1 = ref.loc[idx, "residual"], v.loc[idx, "residual"]
        dlt = r1 - r0
        worse, better = dlt > 0.1, dlt < -0.1
        cross_out = (r0 <= 0.5) & (r1 > 0.5)
        cross_in = (r0 > 0.5) & (r1 <= 0.5)
        tr = pd.Series(list(zip(ref.loc[idx, "object_anchor_catalog"][worse], v.loc[idx, "object_anchor_catalog"][worse]))).value_counts().head(5)
        tb = pd.Series(list(zip(ref.loc[idx, "object_anchor_catalog"][better], v.loc[idx, "object_anchor_catalog"][better]))).value_counts().head(5)
        prow.append(dict(variant=n, reference=ref_name, paired_sources=len(idx), median_diff=round(float(dlt.median()), 4), mean_diff=round(float(dlt.mean()), 4), worse_gt_0p1=int(worse.sum()),
                         better_gt_0p1=int(better.sum()), crossed_out_of_0p5=int(cross_out.sum()), crossed_into_0p5=int(cross_in.sum()),
                         worse_anchor_transitions="; ".join(f"{a_}->{b_}: {k}" for (a_, b_), k in tr.items()),
                         better_anchor_transitions="; ".join(f"{a_}->{b_}: {k}" for (a_, b_), k in tb.items())))  # fmt: skip
    pd.DataFrame(prow).to_csv(a.out / "residual_paired.csv", index=False)
    imag = np.concatenate(des_i)
    drows = []
    for key, parts in des.items():
        r = pd.Series(np.concatenate(parts))
        drows.append(dict(design=key, slice_kind="all", slice="all", **summarise(r)))
        for lo, hi, name in IBINS:
            drows.append(dict(design=key, slice_kind="imag", slice=name, **summarise(r[(imag >= lo) & (imag < hi)])))
    pd.DataFrame(drows).to_csv(a.out / "design_summary.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        s = pd.read_csv(a.out / "residual_summary.csv")
        print(s[(s.slice_kind == "all")].to_string(index=False))
        print(pd.read_csv(a.out / "residual_paired.csv").to_string(index=False))
        print(pd.read_csv(a.out / "design_summary.csv").query("slice_kind == 'all'").to_string(index=False))
    RI.write_args(a, ["truth_flux", "variants"], t0=t0, note="variants: " + " ".join(a.variants))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

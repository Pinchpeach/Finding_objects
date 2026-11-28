#!/usr/bin/env python3
"""What ``V2_OBJECT_POSITION=best`` changes in the final tables of the 26 deep COSMOS fields, and what it does not (task "버"; predictions: PREDICTIONS_2026-11-28.md).

    python measure_object_position.py --runs DIR --truth-flux DIR --out OUT [--fields deep_cosmos_1 ...]

``--runs``        ``DIR/{anchor,best}/<field>/`` the work folders of ``run_pipeline_both.sh`` (the full pipeline, switch off / on)
``--truth-flux``  ``DIR/<field>.csv.gz`` of ``association_truth/collect_truth_flux.py`` (COSMOS2020)

Written (``OUT``):
* ``invariance.csv``        per field: rows, the columns of ``classified_objects.csv`` that differ between the two runs (must be only ``ra`` / ``dec``), the new columns, the rows whose label columns
                            (primary / secondary class, sub-class, p_*, confidence, status), ``designation``, ``object_id`` or ``separation_arcmin`` differ (must be 0), and the same for ``objects_summary.csv``;
* ``residual_summary.csv``  the residual of the clean objects (their resolving rows reach exactly ONE COSMOS2020 source with HSC i < 25; the definition of ``position_residual.py``) to that source, read
                            from the FINAL tables: median, 90 / 99 percentile, share beyond 0.3 / 0.5 / 0.7 / 1.0'', for the anchor run and the best run, in all, by HSC i bin, by the catalogue of the
                            anchor, by the catalogue of the printed position, and for the two halves (fields 1-9 / 10-26);
* ``shift.csv``             the distance between the two positions of an object (``position_shift_arcsec``): shares and percentiles, by half, by printed catalogue, and for stars with a Gaia proper
                            motion above 100 mas/yr;
* ``labels_anchor.csv.gz`` / ``labels_best.csv.gz``  ``regroup.score_accuracy`` of the two final tables (pick / exists / every of the truth sources) for ``rescore_labels.py``;
* ``timing.csv``            the pipeline seconds of both runs and the seconds of ``object_position.apply`` alone.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
AT = V2 / "benchmark" / "association_truth"
sys.path.insert(0, str(AT))
sys.path.insert(0, str(V2 / "benchmark"))
sys.path.insert(0, str(V2 / "Preprocess"))
import measure_association as MA  # noqa: E402
import position_residual as PR  # noqa: E402
import regroup as RG  # noqa: E402
import run_info as RI  # noqa: E402

LABEL_COLUMNS = ("primary_class", "secondary_class", "subclass", "subclass_provenance", "primary_confidence", "classification_status", "p_star", "p_galaxy", "p_qso", "primary_provenance",
                 "designation", "object_id", "separation_arcmin", "high_confidence", "parent_object_id", "component_role")  # fmt: skip
THRESHOLDS = (0.3, 0.5, 0.7, 1.0)
IBINS = [(-np.inf, 20.0, "i<20"), (20.0, 22.0, "20-22"), (22.0, 24.0, "22-24"), (24.0, 25.0, "24-25")]


def load_op():
    spec = importlib.util.spec_from_file_location("v2_object_position_m", V2 / "object_position.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def differ(a: pd.Series, b: pd.Series) -> int:
    return int((~((a == b) | (a.isna() & b.isna()))).sum())


def invariance(field: str, ra_: Path, rb: Path) -> dict:
    a, b = pd.read_csv(ra_ / "classified_objects.csv", low_memory=False), pd.read_csv(rb / "classified_objects.csv", low_memory=False)
    rec = dict(field=field, rows_anchor=len(a), rows_best=len(b), same_row_order=bool(a.object_id.equals(b.object_id)))
    common = [c for c in a.columns if c in b.columns]
    bad = {c: differ(a[c], b[c]) for c in common} if rec["same_row_order"] else {c: -1 for c in common}
    rec["columns_that_differ"] = "|".join(c for c, n in bad.items() if n)
    rec["new_columns_in_best"] = "|".join(c for c in b.columns if c not in a.columns)
    rec["missing_columns_in_best"] = "|".join(c for c in a.columns if c not in b.columns)
    rec["label_rows_changed"] = max((bad.get(c, 0) for c in LABEL_COLUMNS), default=0)
    rec["label_columns_changed"] = "|".join(c for c in LABEL_COLUMNS if bad.get(c, 0))
    sa, sb = pd.read_csv(ra_ / "objects_summary.csv", low_memory=False), pd.read_csv(rb / "objects_summary.csv", low_memory=False)
    sc = [c for c in sa.columns if c in sb.columns]
    rec["summary_columns_that_differ"] = "|".join(c for c in sc if differ(sa[c], sb[c])) if len(sa) == len(sb) else "row count differs"
    rec["summary_new_columns"] = "|".join(c for c in sb.columns if c not in sa.columns)
    return rec


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
    for half, g in c.groupby("half"):
        yield "half", half, g
    for cat, g in c.groupby("object_anchor_catalog"):
        if len(g) >= 50:
            yield "anchor_catalog", str(cat), g
    for cat, g in c.groupby("position_source"):
        if len(g) >= 50:
            yield "printed_catalog", str(cat), g


def process_field(f: str, runs: Path, truth_dir: Path, OP, split: pd.DataFrame) -> dict | None:
    """Everything one field contributes: the invariance record, the clean objects with both residuals, the objects with their shift, the two label tables and the timings."""
    da, db = runs / "anchor" / f, runs / "best" / f
    if not ((da / "classified_objects.csv").exists() and (db / "classified_objects.csv").exists()):
        return None
    half = "fields 1-9" if int(f.rsplit("_", 1)[1]) <= 9 else "fields 10-26"
    rec = invariance(f, da, db)
    truth = MA.load_truth(truth_dir / f"{f}.csv.gz", (split.ra[f], split.dec[f]))
    asc = pd.read_csv(da / "source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"})
    usecols = ["object_id", "ra", "dec", "catalogs", "primary_class", "parent_object_id"]
    oa = pd.read_csv(da / "classified_objects.csv", low_memory=False, usecols=usecols)
    ob = pd.read_csv(db / "classified_objects.csv", low_memory=False, usecols=lambda c: c in usecols + ["position_source", "position_shift_arcsec", "position_epoch", "gaia_dr3__pmra", "gaia_dr3__pmdec"])
    c = PR.clean_objects(asc, truth).drop(columns=["object_ra", "object_dec"])
    pa, pb = oa.drop_duplicates("object_id").set_index("object_id"), ob.drop_duplicates("object_id").set_index("object_id")
    c = c[c.object_id.isin(pa.index)].copy()
    c["residual_anchor"] = PR.sep_arcsec(pa.ra.reindex(c.object_id).to_numpy(), pa.dec.reindex(c.object_id).to_numpy(), c.truth_ra.to_numpy(), c.truth_dec.to_numpy())
    c["residual_best"] = PR.sep_arcsec(pb.ra.reindex(c.object_id).to_numpy(), pb.dec.reindex(c.object_id).to_numpy(), c.truth_ra.to_numpy(), c.truth_dec.to_numpy())
    c["position_source"] = pb.position_source.reindex(c.object_id).to_numpy()
    c["field"], c["half"] = f, half
    s_ = ob.copy()
    s_["field"], s_["half"] = f, half
    labels = []
    for out in (oa, ob):
        acc = RG.score_accuracy(out, truth)
        acc.insert(0, "field", f)
        labels.append(acc)
    full = pd.read_csv(da / "classified_objects.csv", low_memory=False, usecols=["object_id", "ra", "dec"])
    os.environ[OP.ENV] = "best"
    t1 = time.perf_counter()
    OP.apply(full, asc)
    dt = time.perf_counter() - t1
    os.environ.pop(OP.ENV, None)
    sec = lambda d: float(pd.read_csv(d / "pipeline_summary.csv").seconds.sum())  # noqa: E731
    timing = dict(field=f, objects=len(full), detections=len(asc), pipeline_seconds_anchor=round(sec(da), 2), pipeline_seconds_best=round(sec(db), 2), apply_seconds=round(dt, 4))
    print(f"[ok] {f}: {len(c)} clean objects, apply {dt:.3f} s", flush=True)
    return dict(inv=rec, clean=c, shift=s_, labels_anchor=labels[0], labels_best=labels[1], timing=timing)


def aggregate(parts: list[dict], out: Path) -> None:
    pd.DataFrame([p["inv"] for p in parts]).to_csv(out / "invariance.csv", index=False)
    C = pd.concat([p["clean"] for p in parts], ignore_index=True)
    rows = []
    for which in ("anchor", "best"):
        cc = C.assign(residual=C[f"residual_{which}"])
        for kind, name, g in slices(cc):
            rows.append(dict(variant=which, slice_kind=kind, slice=name, **summarise(g.residual)))
    pd.DataFrame(rows).to_csv(out / "residual_summary.csv", index=False)
    d = C.residual_best - C.residual_anchor
    pd.DataFrame([dict(clean_objects=len(C), better_gt_0p1=int((d < -0.1).sum()), worse_gt_0p1=int((d > 0.1).sum()), crossed_into_0p5=int(((C.residual_anchor > 0.5) & (C.residual_best <= 0.5)).sum()),
                       crossed_out_of_0p5=int(((C.residual_anchor <= 0.5) & (C.residual_best > 0.5)).sum()), median_diff=float(d.median()), mean_diff=float(d.mean()))]).to_csv(out / "residual_paired.csv", index=False)
    S = pd.concat([p["shift"] for p in parts], ignore_index=True)

    def shift_row(name, kind, g):
        x = g.position_shift_arcsec.dropna()
        return dict(slice_kind=kind, slice=name, objects=len(x), zero_pct=round(100 * float((x == 0).mean()), 2), over_0p1_pct=round(100 * float((x > 0.1).mean()), 2), over_0p5_pct=round(100 * float((x > 0.5).mean()), 2),
                    median=float(x.median()), p90=float(x.quantile(0.9)), p99=float(x.quantile(0.99)), max=float(x.max()))

    srows = [shift_row("all", "all", S)]
    srows += [shift_row(h, "half", g) for h, g in S.groupby("half")]
    srows += [shift_row(str(k), "printed_catalog", g) for k, g in S.groupby("position_source") if len(g) >= 50]
    pm = np.hypot(pd.to_numeric(S.get("gaia_dr3__pmra"), errors="coerce"), pd.to_numeric(S.get("gaia_dr3__pmdec"), errors="coerce"))
    hp = S[pm > 100]
    srows.append(shift_row("gaia pm > 100 mas/yr", "high_pm", hp))
    moved = hp[hp.position_shift_arcsec > 0.3]
    srows.append(dict(slice_kind="high_pm", slice="gaia pm > 100 mas/yr and shift > 0.3'': printed catalogue", objects=len(moved), **{str(k): int(v) for k, v in moved.position_source.value_counts().items()}))
    pd.DataFrame(srows).to_csv(out / "shift.csv", index=False)
    pd.concat([p["labels_anchor"] for p in parts]).to_csv(out / "labels_anchor.csv.gz", index=False)
    pd.concat([p["labels_best"] for p in parts]).to_csv(out / "labels_best.csv.gz", index=False)
    pd.DataFrame([p["timing"] for p in parts]).to_csv(out / "timing.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(pd.DataFrame([p["inv"] for p in parts])[["field", "rows_anchor", "columns_that_differ", "label_rows_changed", "summary_columns_that_differ"]].to_string(index=False))
        print(pd.read_csv(out / "residual_summary.csv").query("slice_kind in ('all','half','anchor_catalog','printed_catalog')").to_string(index=False))
        print(pd.read_csv(out / "shift.csv").to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields", nargs="*", default=[])
    ap.add_argument("--stage", choices=("all", "field", "aggregate"), default="all",
                    help="field: process the --fields and keep their slim results in OUT/per_field (so the heavy work folders can be deleted); aggregate: the tables from OUT/per_field; all: both")
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    pf = a.out / "per_field"
    pf.mkdir(exist_ok=True)
    OP = load_op()
    split = pd.read_csv(AT / "fields_split.csv").set_index("name")
    if a.stage in ("all", "field"):
        fields = a.fields or sorted((p.name for p in (a.runs / "anchor").iterdir() if p.is_dir() and (p / "classified_objects.csv").exists()), key=lambda f: int(f.rsplit("_", 1)[1]))
        for f in fields:
            part = process_field(f, a.runs, a.truth_flux, OP, split)
            if part is not None:
                pd.to_pickle(part, pf / f"{f}.pkl")
    if a.stage in ("all", "aggregate"):
        parts = [pd.read_pickle(p) for p in sorted(pf.glob("deep_cosmos_*.pkl"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))]
        aggregate(parts, a.out)
    RI.write_args(a, ["runs", "truth_flux"], t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

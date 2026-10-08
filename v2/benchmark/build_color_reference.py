#!/usr/bin/env python3
"""Build the Stage-4 colour-kNN reference set (``LS-CKNN-001``).

Runs the benchmark catalog features through Stage 3 exactly as the pipeline
does and keeps the dereddened Legacy Surveys colours of **train-split**
objects only, so calibration/test objects never appear in the reference.

    python v2/benchmark/build_color_reference.py \\
        --truth v2/benchmark/truth_data/ground_truth.csv v2/benchmark/desi_external/truth.csv \\
        --catalog-root v2/benchmark/catalog_features v2/benchmark/desi_external/catalog_features \\
        --manifest <sdss benchmark_manifest.csv> <desi benchmark_manifest.csv>
"""
from __future__ import annotations
import argparse, tempfile
from pathlib import Path
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
PRE = V2 / "Preprocess"


def main():
    import sys
    sys.path.insert(0, str(PRE))
    import color_knn
    from fit_fusion_weights import load
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=Path, nargs="+", required=True)
    ap.add_argument("--catalog-root", type=Path, nargs="+", required=True)
    ap.add_argument("--manifest", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, default=color_knn.REFERENCE_PATH)
    a = ap.parse_args()
    base = load(Path(__file__).with_name("evaluate_rule_baseline.py"), "rule_baseline")
    base.pre = load(PRE / "02_integrate_objects.py", "integrate")
    s3 = load(PRE / "03_extract_features.py", "s3")
    parts = []
    for t, root, man in zip(a.truth, a.catalog_root, a.manifest):
        raw = base.wide(pd.read_csv(t), base.read_catalogs(root))
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); raw.to_csv(td / "o.csv", index=False)
            s3.run(td / "o.csv", PRE / "classification_rules.csv", td / "f.csv")
            f = pd.read_csv(td / "f.csv", low_memory=False)
        cols = [c for c in color_knn.COLORS if c in f]
        m = pd.read_csv(man)[["benchmark_id", "truth_class", "split"]]
        f = f[["benchmark_id", *cols]].merge(m, on="benchmark_id")
        f = f[f.split.eq("train")]
        f = f[f[cols].notna().sum(axis=1) >= color_knn.MIN_COLORS]
        f["dataset"] = t.parent.name
        parts.append(f.drop(columns="split"))
    ref = pd.concat(parts, ignore_index=True).rename(columns={"benchmark_id": "id"})
    for c in color_knn.COLORS:
        if c not in ref:
            ref[c] = float("nan")
        ref[c] = ref[c].round(4)
    ref = ref[["id", "truth_class", "dataset", *color_knn.COLORS]]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    ref.to_csv(a.out, index=False, compression="gzip")
    print(ref.groupby(["dataset", "truth_class"]).size().to_string())
    print(f"[OK] {len(ref)} reference objects -> {a.out}")


if __name__ == "__main__":
    main()

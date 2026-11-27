#!/usr/bin/env python3
"""Same raw files, two code trees: is the classification identical when Stage 2 stops writing the shared bare columns (2.61.4)?

    python equivalence.py --before-repo /path/to/checkout-before --raw RAW_DIR [RAW_DIR ...] --out DIR [--jobs 3]

``RAW_DIR`` is a folder of collected raw files with its ``search.json`` (ra, dec, radius_arcmin).  Each one is classified offline
(``pipeline.py --raw-dir``, same hash seed, cache off) with the checkout given by ``--before-repo`` and with the checkout this
file is in.  One row per raw folder in ``equivalence.csv``: objects, columns before / after, the columns that disappeared and
appeared, the number of objects whose ``primary_class`` / ``classification_status`` / ``classification_basis`` differs, the largest
change of ``p_star`` / ``p_galaxy`` / ``p_qso``, and how many of the remaining (common) columns differ anywhere.  ``columns_removed.csv``
lists every column that went away with its number of non-empty cells before, ``other_differences.csv`` every common column whose
values changed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
THIS_REPO = HERE.parents[3]
STATIC = frozenset(json.loads((HERE.parent / "shared_candidates.json").read_text()))  # = SHARED_FIELDS of Stage 2
LABELS = ("primary_class", "classification_status", "classification_basis")
PROBS = ("p_star", "p_galaxy", "p_qso")


def classify(repo: Path, raw: Path, work: Path) -> pd.DataFrame:
    s = json.loads((raw / "search.json").read_text())
    env = dict(os.environ, PYTHONHASHSEED="0", V2_CACHE="0")
    for k in ("V2_KEEP_SHARED_BARE", "V2_LOWLAT_QSO"):
        env.pop(k, None)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    cmd = [sys.executable, str(repo / "v2" / "pipeline.py"), "--raw-dir", str(raw), "--ra", str(s["ra"]), "--dec", str(s["dec"]),
           "--radius", str(s["radius_arcmin"]), "--work", str(work)]  # fmt: skip
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = pd.read_csv(work / "classified_objects.csv", low_memory=False)
    shutil.rmtree(work, ignore_errors=True)
    return d.set_index("object_id")


def _same(a: pd.Series, b: pd.Series) -> pd.Series:
    """Element-wise equality where two missing values are equal and numbers are compared as numbers."""
    na, nb = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
    if na.notna().sum() == a.notna().sum() and nb.notna().sum() == b.notna().sum():
        eq = np.isclose(na.to_numpy(float), nb.to_numpy(float), rtol=1e-9, atol=1e-12, equal_nan=True)
        return pd.Series(eq, index=a.index)
    return a.fillna("").astype(str) == b.fillna("").astype(str)


def compare(before: pd.DataFrame, after: pd.DataFrame):
    common_idx = before.index.intersection(after.index)
    a, b = before.loc[common_idx], after.loc[common_idx]
    removed = [c for c in before.columns if c not in after.columns]
    added = [c for c in after.columns if c not in before.columns]
    row = dict(objects_before=len(before), objects_after=len(after), objects_common=len(common_idx),
               columns_before=before.shape[1], columns_after=after.shape[1], columns_removed=len(removed), columns_added=len(added))  # fmt: skip
    for c in LABELS:
        row[f"{c}_differs"] = int((~_same(a[c], b[c])).sum())
    for c in PROBS:
        d = (pd.to_numeric(a[c], errors="coerce") - pd.to_numeric(b[c], errors="coerce")).abs()
        row[f"{c}_max_abs_change"] = float(np.nanmax(d.to_numpy())) if len(d) and d.notna().any() else 0.0
    diffs = []
    for c in [c for c in before.columns if c in after.columns]:
        n = int((~_same(a[c], b[c])).sum())
        if n:
            diffs.append(dict(column=c, objects_differ=n))
    row["other_columns_that_differ"] = len(diffs)
    rem = [dict(column=c, nonempty_cells_before=int(before[c].notna().sum())) for c in removed]
    # names the static list did not know (found in the raw headers of the run) and derived columns that only existed because a
    # bare name stood in for a missing namespace (an all-empty catalog_confidence_ned_type)
    row["removed_outside_static_list"] = ";".join(c for c in removed if c not in STATIC)
    return row, rem, diffs, added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before-repo", type=Path, required=True)
    ap.add_argument("--raw", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    def one(raw: Path):
        if raw.name == "raw":
            name = raw.parent.name
        elif raw.name.startswith("ra") and raw.parent.name == "raw":
            name = raw.parent.parent.name
        else:
            name = raw.name
        w = a.out / "work" / name
        before = classify(a.before_repo, raw, w / "before")
        after = classify(THIS_REPO, raw, w / "after")
        row, rem, diffs, added = compare(before, after)
        shutil.rmtree(w, ignore_errors=True)
        return dict(field=name, **row), [dict(field=name, **r) for r in rem], [dict(field=name, **d) for d in diffs], added

    with ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(one, a.raw))
    rows = pd.DataFrame([r[0] for r in results])
    rem = pd.DataFrame([x for r in results for x in r[1]])
    dif = pd.DataFrame([x for r in results for x in r[2]])
    rows.to_csv(a.out / "equivalence.csv", index=False)
    rem.to_csv(a.out / "columns_removed.csv", index=False)
    dif.to_csv(a.out / "other_differences.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.max_rows", 200):
        print(rows.to_string(index=False))
        if len(rem):
            print(rem.groupby("column").agg(fields=("field", "nunique"), cells=("nonempty_cells_before", "sum")).to_string())
        if len(dif):
            print(dif.groupby("column").agg(fields=("field", "nunique"), objects=("objects_differ", "sum")).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

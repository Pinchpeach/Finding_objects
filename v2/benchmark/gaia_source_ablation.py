#!/usr/bin/env python3
"""What the Gaia VizieR copy changes in a search (2.57.0, Gaia DR4 downtime 2026-11-25..12-02).

Input: a raw folder of a search whose Gaia rows came from the ESA archive
(``gaia_base_query_status = tap``), e.g. the practical-use probe sets on the
``validation-data`` branch (``practical_probe/<run id>/<field>_raw.tar.gz``).
The Gaia file is collected again for the same cone from the VizieR I/355 copy
only (``V2_GAIA_SOURCE=vizier``, no cache); both raw folders, all other
catalogues identical, are classified with the current code, and the script writes

  columns.csv    per Gaia column: fraction of rows filled with the ESA archive / with the copy
  changes.csv    objects whose class, status, subclass or confidence differ
  summary.json   counts: objects, label changes, columns lost, collection times

so that what the copy lacks and what that does to the labels are measured
rather than assumed.  The downstream classification is not touched.

    python v2/benchmark/gaia_source_ablation.py --raw-dir <field raw folder> --out <dir>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[1]
GAIA_FILE = re.compile(r"^gaia_dr3_(ra[^.]*)\.csv$")
TAG = re.compile(r"^ra(?P<ra>m?[0-9p]+)_dec(?P<dec>m?[0-9p]+)_r(?P<r>[0-9p]+)arcmin$")


def _num(token: str) -> float:
    return float(token.replace("m", "-").replace("p", "."))


def cone_from_tag(tag: str) -> tuple[float, float, float]:
    m = TAG.match(tag)
    if not m:
        raise ValueError(f"not a search tag: {tag!r}")
    return _num(m["ra"]), _num(m["dec"]), _num(m["r"])


def _load(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect_from_vizier(ra: float, dec: float, radius: float, target: Path) -> float:
    """Gaia for the cone from the VizieR copy only, written to ``target``; seconds."""
    os.environ["V2_GAIA_SOURCE"] = "vizier"
    os.environ["V2_CACHE"] = "0"
    sys.path.insert(0, str(V2 / "Get_data"))
    try:
        from astroquery import cache_conf

        cache_conf.cache_active = False
    except Exception:
        pass
    gaia = _load(V2 / "Get_data" / "gaia_dr3.py", "ablation_gaia_dr3")
    t = time.monotonic()
    df = gaia.fetch(ra, dec, radius)
    gaia.save(df, target)
    return time.monotonic() - t


def classify(raw: Path, work: Path) -> pd.DataFrame:
    pipeline = _load(V2 / "pipeline.py", f"ablation_pipeline_{work.name}")
    pipeline.run(work, raw_dir=raw)
    return pd.read_csv(work / "classified_objects.csv", low_memory=False)


def fill_table(esa: pd.DataFrame, copy: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in esa.columns if c in copy.columns or True]
    rows = []
    for c in cols:
        rows.append(
            {
                "column": c,
                "filled_esa": float(esa[c].notna().mean()) if len(esa) else 0.0,
                "filled_copy": float(copy[c].notna().mean()) if c in copy and len(copy) else 0.0,
            }
        )
    return pd.DataFrame(rows)


LABELS = ["primary_class", "classification_status", "subclass", "physical_class", "variability_class"]


def compare(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Rows (matched by designation) whose labels differ between the two runs."""
    keep = ["designation", "primary_confidence", *[c for c in LABELS if c in a and c in b]]
    m = a[keep].merge(b[keep], on="designation", suffixes=("_esa", "_copy"))
    changed = pd.Series(False, index=m.index)
    for c in [x for x in LABELS if x in a and x in b]:
        changed |= m[f"{c}_esa"].fillna("").astype(str) != m[f"{c}_copy"].fillna("").astype(str)
    return m[changed].reset_index(drop=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--cone", nargs=3, type=float, metavar=("RA", "DEC", "RADIUS_ARCMIN"), help="when the folder has no search tag"
    )
    a = p.parse_args()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    gaia_files = [f for f in a.raw_dir.glob("gaia_dr3_ra*.csv") if GAIA_FILE.match(f.name)]
    if len(gaia_files) != 1:
        p.error(f"expected one Gaia file in {a.raw_dir}, found {len(gaia_files)}")
    gfile = gaia_files[0]
    ra, dec, radius = tuple(a.cone) if a.cone else cone_from_tag(GAIA_FILE.match(gfile.name)[1])
    esa_raw, copy_raw = out / "raw_esa", out / "raw_copy"
    for d in (esa_raw, copy_raw):
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(a.raw_dir, d)
    esa = pd.read_csv(gfile, low_memory=False)
    status = esa["gaia_base_query_status"].iloc[0] if len(esa) else "empty"
    seconds = collect_from_vizier(ra, dec, radius, copy_raw / gfile.name)
    copy = pd.read_csv(copy_raw / gfile.name, low_memory=False)
    fills = fill_table(esa, copy)
    fills.to_csv(out / "columns.csv", index=False)
    lost = fills[(fills.filled_esa > 0) & (fills.filled_copy == 0)].column.tolist()
    same_ids = sorted(esa.catalog_object_id.astype(str)) == sorted(copy.catalog_object_id.astype(str))
    ca = classify(esa_raw, out / "work_esa")
    cb = classify(copy_raw, out / "work_copy")
    changes = compare(ca, cb)
    changes.to_csv(out / "changes.csv", index=False)
    summary = {
        "cone": [ra, dec, radius],
        "esa_base_status": status,
        "gaia_rows_esa": len(esa),
        "gaia_rows_copy": len(copy),
        "same_source_ids": same_ids,
        "columns_lost_all_rows": lost,
        "copy_collection_seconds": round(seconds, 1),
        "objects_esa": len(ca),
        "objects_copy": len(cb),
        "objects_matched": int(len(ca.merge(cb, on="designation"))),
        "labels_changed": len(changes),
        "primary_class_changed": (
            int((changes.primary_class_esa != changes.primary_class_copy).sum()) if len(changes) else 0
        ),
        "esa_primary_classes": ca.primary_class.value_counts().to_dict(),
        "copy_primary_classes": cb.primary_class.value_counts().to_dict(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

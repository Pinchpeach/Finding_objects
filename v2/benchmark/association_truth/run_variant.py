#!/usr/bin/env python3
"""Run the association stage (stage 1) on the raw data of the 26 deep fields, optionally with shifted catalogues.

    python run_variant.py --fields-root DIR --out DIR [--shift] [--env KEY=VALUE ...]

``--fields-root`` holds ``<field>/raw/<tag>/*.csv`` (collect_deep_cosmos.py).  ``--shift`` writes a copy of the raw
rows in which AllWISE moves +2' in Dec, 2MASS PSC -2' in Dec and GALEX AIS +2' in RA (the shifted-catalogue test of
2.48.0 / 2.49.0, GALEX added) so that no true counterpart remains and a shifted row cannot find another shifted row.
``--env`` sets the variant switches (e.g. V2_ASSOC_...) before the stage is imported.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
SHIFTS = {"AllWISE": ("dec", 2.0 / 60.0), "2MASS PSC": ("dec", -2.0 / 60.0), "GALEX AIS": ("ra", 2.0 / 60.0)}


def shifted_copy(raw: Path, dst: Path) -> None:
    shutil.copytree(raw, dst)
    for f in dst.glob("*.csv"):
        d = pd.read_csv(f, low_memory=False)
        cats = set(d.catalog.astype(str)) if "catalog" in d else set()
        for cat, (axis, step) in SHIFTS.items():
            if cat in cats:
                d[axis] = pd.to_numeric(d[axis], errors="coerce") + step
        d.to_csv(f, index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fields-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shift", action="store_true")
    ap.add_argument("--env", nargs="*", default=[])
    ap.add_argument("--fields", default="")
    a = ap.parse_args()
    for kv in a.env:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    sys.path.insert(0, str(V2 / "Preprocess"))
    spec = importlib.util.spec_from_file_location("assoc_stage", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    names = [n for n in a.fields.split(",") if n] or sorted(p.name for p in a.fields_root.glob("deep_cosmos_*"))
    for name in names:
        raw = next((a.fields_root / name / "raw").glob("*"))
        out = a.out / name / "source_association.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        if a.shift:
            with tempfile.TemporaryDirectory() as tmp:
                shifted_copy(raw, Path(tmp) / "raw")
                mod.run(Path(tmp) / "raw", out)
        else:
            mod.run(raw, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

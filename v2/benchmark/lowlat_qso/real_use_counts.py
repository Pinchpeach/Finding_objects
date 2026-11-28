#!/usr/bin/env python3
"""The per-variant counts of the three real-use fields (NGC 4522 2', COSMOS 2', Galactic plane 1') for the decision table (2.62.7).

    python real_use_counts.py --runs DIR --variants base surveys2 ... --out inputs/real_use_counts.csv [--update]

``DIR/run_<variant>/{ngc,cosmos,plane}/classified_objects.csv`` (slim, with ``primary_class``, ``lowlat_qso_hold``).  One row per variant with, per field, the objects, the QSO
labels, the objects whose QSO reading the survey-count switches held (``lowlat_qso_hold`` set), and the GALAXY and STAR labels: the columns of
``results_2026-11-27h/inputs/real_use_counts.csv``.  ``--update`` replaces the rows of these variants in an existing file and keeps the others.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402

FIELDS = ("ngc", "cosmos", "plane")


def counts(runs: Path, variant: str) -> dict:
    row = {"variant": variant}
    for f in FIELDS:
        d = pd.read_csv(runs / f"run_{variant}" / f / "classified_objects.csv", low_memory=False)
        held = d["lowlat_qso_hold"].fillna("").astype(str).ne("") if "lowlat_qso_hold" in d else pd.Series(False, index=d.index)
        row.update({f"{f}_objects": len(d), f"{f}_QSO": int((d.primary_class == "QSO").sum()), f"{f}_held": int(held.sum()),
                    f"{f}_GALAXY": int((d.primary_class == "GALAXY").sum()), f"{f}_STAR": int((d.primary_class == "STAR").sum())})  # fmt: skip
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    t0 = RI.start()
    new = pd.DataFrame([counts(a.runs, v) for v in a.variants])
    if a.update and a.out.exists():
        old = pd.read_csv(a.out)
        new = pd.concat([old[~old.variant.isin(new.variant)], new], ignore_index=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(a.out, index=False)
    print(new.to_string(index=False))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

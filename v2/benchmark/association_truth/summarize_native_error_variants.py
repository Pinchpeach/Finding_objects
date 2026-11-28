#!/usr/bin/env python3
"""AllWISE ``eeMaj`` / GALEX ``Nerr`` as the position error: what changes against COSMOS2020 (2.62.6).

    python summarize_native_error_variants.py --root DIR --out OUT [--variants base allwise allwise_raw galex]

``--root`` holds, per variant ``V``: ``V/<field>/source_association.csv`` (``run_variant.py --env V2_POSERR_NATIVE=...``) and
``meas_V/false_missed_V.csv`` (``measure_association.py`` with ``--shifted-dir V_shift``).  Writes

* ``native_error_false_missed.csv``  false / missed / shifted-catalogue false per catalogue and half for every variant, with the change against ``base``;
* ``native_error_structure.csv``     objects, objects anchored by each catalogue, and how many objects differ from ``base`` (membership of detection ids; the object
  ids themselves are not comparable between runs).

Reproduce the runs: ``run_native_error_variants.sh``.
"""

from __future__ import annotations

import sys

import argparse
from pathlib import Path

import pandas as pd

CATS = ("AllWISE", "GALEX AIS")


def partition(a: pd.DataFrame) -> set:
    return {tuple(sorted(g)) for _, g in a.groupby("object_id").detection_id}


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", default=["base", "allwise", "allwise_raw", "galex"])
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    fm = pd.concat([pd.read_csv(a.root / f"meas_{v}" / f"false_missed_{v}.csv") for v in a.variants])
    fm = fm[fm.catalog.isin(CATS)]
    keep = ["variant", "half", "catalog", "rows", "with_expected", "matched", "correct", "false", "unknown", "missed", "false_pct_of_matched_known", "false_wilson", "missed_pct_of_expected", "shifted_false_pct"]  # fmt: skip
    fm = fm[keep]
    base = fm[fm.variant == "base"].set_index(["half", "catalog"])
    for col in ("matched", "correct", "false", "missed", "false_pct_of_matched_known", "missed_pct_of_expected", "shifted_false_pct"):
        fm[f"d_{col}"] = [round(r[col] - base.loc[(r.half, r.catalog), col], 2) for _, r in fm.iterrows()]
    fm.sort_values(["catalog", "half", "variant"]).to_csv(a.out / "native_error_false_missed.csv", index=False)

    fields = sorted(p.name for p in (a.root / "base").iterdir() if p.is_dir())
    rows = []
    for v in a.variants:
        n_obj, differ, same_fields, anchors = 0, 0, 0, pd.Series(dtype=float)
        for f in fields:
            x = pd.read_csv(a.root / v / f / "source_association.csv", low_memory=False)
            o = x.groupby("object_id").object_anchor_catalog.first()
            n_obj += len(o)
            anchors = anchors.add(o.value_counts(), fill_value=0)
            if v != "base":
                b = pd.read_csv(a.root / "base" / f / "source_association.csv", low_memory=False)
                pb, px = partition(b), partition(x)
                differ += len(pb ^ px) // 2
                same_fields += pb == px
        rows.append(dict(variant=v, objects=n_obj, anchored_by_AllWISE=int(anchors.get("AllWISE", 0)), anchored_by_GALEX=int(anchors.get("GALEX AIS", 0)),
                         anchored_by_LS=int(anchors.get("DESI Legacy Surveys DR10", 0)), anchored_by_PS1=int(anchors.get("Pan-STARRS1 DR2 MeanObject", 0)),
                         objects_differing_from_base=differ if v != "base" else 0, fields_identical_to_base=same_fields if v != "base" else len(fields)))  # fmt: skip
    pd.DataFrame(rows).to_csv(a.out / "native_error_structure.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(fm[fm.half == "all"].drop(columns=["unknown", "with_expected", "false_wilson"]).sort_values(["catalog", "variant"]).to_string(index=False))
    RI.write_args(a, ('root',), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

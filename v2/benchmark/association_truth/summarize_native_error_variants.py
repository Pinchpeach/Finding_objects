#!/usr/bin/env python3
"""AllWISE ``eeMaj`` / GALEX ``Nerr`` as the position error: what changes against COSMOS2020 (2.62.4).

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

import numpy as np
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
    ap.add_argument("--cats", nargs="+", default=list(CATS), help="catalogues of the false / missed table (2.62.7: the order-key study adds '2MASS PSC')")
    ap.add_argument("--stem", default="native_error", help="output file stem: STEM_false_missed.csv, STEM_structure.csv")
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    fm = pd.concat([pd.read_csv(a.root / f"meas_{v}" / f"false_missed_{v}.csv") for v in a.variants])
    fm = fm[fm.catalog.isin(a.cats)]
    keep = ["variant", "half", "catalog", "rows", "with_expected", "matched", "correct", "false", "unknown", "missed", "rightly_alone", "false_pct_of_matched_known", "false_wilson", "missed_pct_of_expected", "shifted_false_pct"]  # fmt: skip
    split = {"alone_identified", "alone_wrong", "alone_unidentified"} <= set(fm.columns)
    keep += [c for c in ("shifted_any_pct",) if c in fm]  # 2.62.7 (task "러", METRICS.md): the anchor independent chance-join rate; absent in older measurement folders
    fm = fm[keep + (["alone_identified", "alone_wrong", "alone_unidentified"] if split else [])]
    # 2.62.7: the row sits in the object that holds its counterpart, whoever anchors: joined and right (correct) or anchoring an object that holds it
    # (alone_identified).  Review (Codex): rightly_alone also counts rows whose counterpart no object holds, which turn "unknown" when joined, so the first
    # version (correct + rightly_alone) moved with the anchor.  Outputs of measure_association.py before the split have no alone_identified: NaN, re-measure.
    if split:
        fm["right_object"] = fm.correct + fm.alone_identified
        fm["wrong_object"] = fm["false"] + fm.alone_wrong
        fm["unidentified"] = fm.unknown + fm.alone_unidentified
    else:
        print("measure_association outputs without alone_identified / alone_wrong / alone_unidentified: right_object is not computed (re-run measure_association.py)", file=sys.stderr)
        fm["right_object"] = fm["wrong_object"] = fm["unidentified"] = np.nan
    base = fm[fm.variant == "base"].set_index(["half", "catalog"])
    for col in ("matched", "correct", "false", "missed", "rightly_alone", "right_object", "wrong_object", "unidentified", "false_pct_of_matched_known", "missed_pct_of_expected", "shifted_false_pct") + (("shifted_any_pct",) if "shifted_any_pct" in fm else ()):
        fm[f"d_{col}"] = [round(r[col] - base.loc[(r.half, r.catalog), col], 2) for _, r in fm.iterrows()]
    fm.sort_values(["catalog", "half", "variant"]).to_csv(a.out / f"{a.stem}_false_missed.csv", index=False)

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
        if "2MASS PSC" in a.cats:
            rows[-1]["anchored_by_2MASS"] = int(anchors.get("2MASS PSC", 0))
    pd.DataFrame(rows).to_csv(a.out / f"{a.stem}_structure.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(fm[fm.half == "all"].drop(columns=["unknown", "with_expected", "false_wilson"]).sort_values(["catalog", "variant"]).to_string(index=False))
    RI.write_args(a, ('root',), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

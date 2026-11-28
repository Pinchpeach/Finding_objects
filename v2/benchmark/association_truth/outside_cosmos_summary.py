#!/usr/bin/env python3
"""The order-key variants where there is no association truth: join counts, anchors and the shifted-catalogue control (2.62.7, task "너" item 3).

    python outside_cosmos_summary.py --root DIR --sets real cal conf --variants base allwise allwise_order ... --out OUT

``--root`` holds, per set ``S`` and variant ``V``: ``S/V/<field>/source_association.csv`` (``run_variant.py``) and ``S/V_shift/<field>/source_association.csv`` (``--shift``: AllWISE
+2' in Dec, 2MASS -2' in Dec, GALEX +2' in RA, so no true counterpart is left).  Without COSMOS2020 there is no correct / false / missed; what can be counted is

* ``objects`` and ``anchored_by_AllWISE``        how many objects the variant makes, and how many have an AllWISE row as anchor (an AllWISE row that anchors its own object is
                                                  the fragment the order key is meant to prevent); change against ``base``;
* ``allwise_rows_joined``                        AllWISE rows of the real run that joined an object anchored by another catalogue (the joins the variant makes);
* ``shifted_false`` / ``shifted_false_pct``      shifted rows of one catalogue that joined an object anchored by an UNshifted catalogue (``measure_association.py``'s definition,
                                                  the 2.49.0 test): chance joins, since the shifted catalogue has no counterpart left; per catalogue and for all three;
* ``objects_differing_from_base`` / ``fields_identical_to_base``   member sets that differ (object ids are not comparable between runs).

The per-field change of ``objects`` and of ``anchored_by_AllWISE`` is summarised by its median and its 5 / 95 percentiles over the fields (``d_objects_*``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SHIFTED = ("AllWISE", "2MASS PSC", "GALEX AIS")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def partition(a: pd.DataFrame) -> set:
    return {tuple(sorted(g)) for _, g in a.groupby("object_id").detection_id}


def one(root: Path, s: str, v: str, base: str, fields: list[str]) -> dict:
    n_obj = n_aw = joined = differ = same = 0
    sh = {c: [0, 0] for c in SHIFTED}
    d_obj, d_aw = [], []
    for f in fields:
        x = pd.read_csv(root / s / v / f / "source_association.csv", low_memory=False)
        o = x.groupby("object_id").object_anchor_catalog.first()
        n_obj += len(o)
        n_aw += int((o == "AllWISE").sum())
        w = x[x.catalog == "AllWISE"]
        joined += int(((w.association_status == "matched") & (w.object_anchor_catalog != "AllWISE")).sum())
        y = pd.read_csv(root / s / f"{v}_shift" / f / "source_association.csv", low_memory=False)
        for c in SHIFTED:
            d = y[y.catalog == c]
            sh[c][0] += len(d)
            sh[c][1] += int(((d.association_status == "matched") & ~d.object_anchor_catalog.isin(SHIFTED)).sum())
        if v != base:
            b = pd.read_csv(root / s / base / f / "source_association.csv", low_memory=False)
            ob = b.groupby("object_id").object_anchor_catalog.first()
            d_obj.append(len(o) - len(ob))
            d_aw.append(int((o == "AllWISE").sum()) - int((ob == "AllWISE").sum()))
            pb, px = partition(b), partition(x)
            differ += len(pb ^ px) // 2
            same += pb == px
    rec = dict(set=s, variant=v, fields=len(fields), objects=n_obj, anchored_by_AllWISE=n_aw, allwise_rows_joined=joined,
               objects_differing_from_base=differ if v != base else 0, fields_identical_to_base=same if v != base else len(fields))  # fmt: skip
    if v != base:
        q = lambda a, p: float(np.percentile(a, p)) if a else float("nan")  # noqa: E731
        rec.update(d_objects_median=q(d_obj, 50), d_objects_p5=q(d_obj, 5), d_objects_p95=q(d_obj, 95), d_anchored_by_AllWISE_median=q(d_aw, 50),
                   d_anchored_by_AllWISE_p5=q(d_aw, 5), d_anchored_by_AllWISE_p95=q(d_aw, 95))  # fmt: skip
    tot_r = tot_f = 0
    for c, (r, k) in sh.items():
        rec[f"shift_rows_{c.split()[0]}"], rec[f"shift_false_{c.split()[0]}"] = r, k
        rec[f"shifted_false_pct_{c.split()[0]}"] = round(100 * k / r, 2) if r else float("nan")
        tot_r, tot_f = tot_r + r, tot_f + k
    rec["shifted_false_pct_all"] = round(100 * tot_f / tot_r, 2) if tot_r else float("nan")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    base = a.variants[0]
    rows = []
    for s in a.sets:
        fields = sorted(p.name for p in (a.root / s / base).iterdir() if p.is_dir())
        for v in a.variants:
            rows.append(one(a.root, s, v, base, fields))
    t = pd.DataFrame(rows)
    for col in ("objects", "anchored_by_AllWISE", "allwise_rows_joined", "shifted_false_pct_AllWISE", "shifted_false_pct_all"):
        t[f"d_{col}"] = t[col] - t.groupby("set")[col].transform("first")
    t["d_anchored_by_AllWISE_pct"] = (100 * t.d_anchored_by_AllWISE / t.groupby("set").anchored_by_AllWISE.transform("first")).round(2)
    t.to_csv(a.out / "outside_cosmos.csv", index=False)
    with pd.option_context("display.width", 260, "display.max_columns", 40):
        print(t[["set", "variant", "fields", "objects", "d_objects", "anchored_by_AllWISE", "d_anchored_by_AllWISE_pct", "allwise_rows_joined", "d_allwise_rows_joined", "objects_differing_from_base",
                 "shifted_false_pct_AllWISE", "d_shifted_false_pct_AllWISE", "shifted_false_pct_all"]].to_string(index=False))
    RI.write_args(a, ["root"], t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

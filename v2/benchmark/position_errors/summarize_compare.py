#!/usr/bin/env python3
"""The tables of ``compare_by_members.py`` condensed against the predictions of ``PREDICTIONS.md`` (2.62.2).

    python summarize_compare.py --compare results_2026-11-27h/compare --out results_2026-11-27h/summary

Writes ``radio_rows.csv`` (per radio catalogue: rows, joined to a non-radio detection in each mode, separate -> joined, joined -> separate, objects anchored by it),
``anchor_changes.csv`` (the anchor catalogues that change hands and the shift of the object position), ``label_changes.csv`` (per column, and for the primary class split into
``fragment absorbed``: the object of the legacy run had no class evidence (UNKNOWN) and is now part of a classified object, and ``classified object changed class``:
it had a class in both runs) and ``predictions.csv`` (the counts the predictions named, next to the measured ones).
"""

from __future__ import annotations

import sys

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--compare", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    per = pd.read_csv(a.compare / "per_region.csv")
    rad = pd.read_csv(a.compare / "radio_rows.csv")
    lab = pd.read_csv(a.compare / "label_changes.csv")
    anc = pd.read_csv(a.compare / "anchor_changes.csv")
    RADIO = {"VLASS", "NVSS", "FIRST", "TGSS ADR1", "LoTSS DR2"}
    rows = []
    for cat, g in rad.groupby("catalog_a"):
        rows.append(dict(catalog=cat, rows=len(g), joined_legacy=int(g.joined_a.sum()), joined_fixed=int(g.joined_b.sum()), separate_to_joined=int((~g.joined_a & g.joined_b).sum()),
                         joined_to_separate=int((g.joined_a & ~g.joined_b).sum()), anchor_legacy=int((g.anchor_a == cat).sum()), anchor_fixed=int((g.anchor_b == cat).sum())))  # fmt: skip
    pd.DataFrame(rows).to_csv(a.out / "radio_rows.csv", index=False)
    anc.groupby(["anchor_a", "anchor_b"]).shift_arcsec.agg(["size", "median", "max"]).round(2).reset_index().to_csv(a.out / "anchor_changes.csv", index=False)
    cnt = Counter()
    for cols, k in zip(lab["columns"].fillna(""), lab.kind):
        for c in str(cols).split("|"):
            if c:
                cnt[c] += 1
    pc = lab[lab["columns"].fillna("").str.contains("primary_class")]
    absorbed = int((pc.primary_class_a == "UNKNOWN").sum())
    flipped = len(pc) - absorbed
    lrows = [dict(column=c, objects=n) for c, n in sorted(cnt.items())]
    lrows += [dict(column="primary_class: fragment absorbed (UNKNOWN -> class)", objects=absorbed), dict(column="primary_class: classified object changed class", objects=flipped),
              dict(column="radio flux column only", objects=int((lab["columns"].isna() & lab.radio_columns.notna()).sum()))]  # fmt: skip
    pd.DataFrame(lrows).to_csv(a.out / "label_changes.csv", index=False)
    tot = per[["objects_a", "objects_b", "same_members", "changed_a", "changed_b", "radio_anchored_a", "radio_anchored_b"]].sum()
    v, n = rad[rad.catalog_a == "VLASS"], rad[rad.catalog_a == "NVSS"]
    pred = [
        ("catalogues whose position error changes", "VLASS, NVSS only", "VLASS, NVSS only (860 000 rows of 22 catalogues, check_units_from_rows.py)"),
        ("objects anchored by a radio row although they hold an optical row", "falls 20-60 % (from ~100-140)", f"{int(tot.radio_anchored_a)} -> {int(tot.radio_anchored_b)} ({100 * (tot.radio_anchored_b / tot.radio_anchored_a - 1):.0f} %)"),
        ("VLASS rows that change joined / separate", "<= 10 (of 384)", f"{int((~v.joined_a & v.joined_b).sum())} to joined + {int((v.joined_a & ~v.joined_b).sum())} to separate (of {len(v)})"),
        ("NVSS rows that change joined / separate", "<= 2", f"{int((~n.joined_a & n.joined_b).sum())} to joined + {int((n.joined_a & ~n.joined_b).sum())} to separate (of {len(n)})"),
        ("object count change", "within 10", f"{int(tot.objects_b - tot.objects_a):+d} ({int(tot.objects_a)} -> {int(tot.objects_b)})"),
        ("primary-class changes", "0-10", f"{len(pc)} ({absorbed} fragments absorbed, {flipped} classified objects changed class)"),
        ("compact_class changes", "0-2", str(cnt.get("compact_class", 0))),
        ("extragalactic_class / subclass changes", "0-10, inside the same objects", f"{cnt.get('extragalactic_class', 0)} / {cnt.get('subclass', 0)}"),
    ]
    pd.DataFrame(pred, columns=["quantity", "predicted", "measured"]).to_csv(a.out / "predictions.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        for f in ("predictions", "radio_rows", "label_changes", "anchor_changes"):
            print("==", f)
            print(pd.read_csv(a.out / f"{f}.csv").to_string(index=False))
    RI.write_args(a, ('compare',), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The fragment-variant table (one line per variant and half) from the outputs of ``regroup.py`` (2.60.11).

    python fragment_variants_summary.py --regroup DIR [--base replay_base] [--variants hc m15hc ...] --out DIR

``results_2026-11-25/fragment_variants_summary.csv`` of the 2.60.8 report was made by hand; this makes it.  Reads
``regroup_fragments_<v>.csv``, ``regroup_merges_<v>.csv`` and ``regroup_labels_<v>.csv.gz`` of ``regroup.py`` and adds, per
variant against the base replay and per half: the number of truth labels that changed (``labels_changed``), the
one-sided counts of right-only-in-base / right-only-in-variant and the exact two-sided McNemar p.  A variant without
a labels file (an older run) has empty label columns.
"""

from __future__ import annotations

import argparse
from math import comb
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def mcnemar(base_ok: pd.Series, var_ok: pd.Series):
    n10, n01 = int((base_ok & ~var_ok).sum()), int((~base_ok & var_ok).sum())
    n = n10 + n01
    p = min(1.0, 2 * sum(comb(n, k) for k in range(0, min(n10, n01) + 1)) / 2**n) if n else 1.0
    return n10, n01, p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regroup", type=Path, required=True)
    ap.add_argument("--base", default="replay_base")
    ap.add_argument("--variants", nargs="*", default=None, help="default: every variant found in --regroup")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    split = pd.read_csv(HERE / "fields_split.csv").set_index("name").split
    found = sorted(p.name[len("regroup_fragments_") : -len(".csv")] for p in a.regroup.glob("regroup_fragments_*.csv"))
    variants = [a.base] + [v for v in (a.variants if a.variants else found) if v != a.base]
    labels = {}
    for v in variants:
        f = a.regroup / f"regroup_labels_{v}.csv.gz"
        labels[v] = pd.read_csv(f) if f.exists() else None
    b = labels.get(a.base)
    rows = []
    for v in variants:
        f = pd.read_csv(a.regroup / f"regroup_fragments_{v}.csv")
        m = pd.read_csv(a.regroup / f"regroup_merges_{v}.csv")
        for half in ("calibration", "test"):
            ff, mm = f[f.split == half], m[m.split == half]
            fr, ha = mm[mm.role == "fragment"], mm[mm.role == "bright_star_halo"]
            r = dict(variant=v, half=half, truth_sources=int(ff.truth_sources.sum()),
                     truth_with_fragments=int(ff.truth_with_fragments.sum()), extra_objects=int(ff.extra_fragment_objects.sum()),
                     extra_same_truth=int(ff.extra_same_truth.sum()), extra_other_truth=int(ff.extra_other_truth.sum()),
                     extra_no_truth=int(ff.extra_no_truth.sum()), grouped_fragment=int(fr.n.sum()),
                     fragment_same=int(fr.same.sum()), fragment_none=int(fr.none.sum()), fragment_wrong=int(fr.wrong.sum()),
                     grouped_halo=int(ha.n.sum()), halo_wrong=int(ha.wrong.sum()), top_level_objects=int(ff.top_level_objects.sum()))  # fmt: skip
            h = labels[v]
            if h is not None and b is not None:
                msk = (b.field.map(split) == half).to_numpy()
                n10, n01, p = mcnemar((b.pred == b.truth)[msk], (h.pred == h.truth)[msk])
                r.update(labels_changed=int((b.pred[msk].fillna("") != h.pred[msk].fillna("")).sum()), acc_base_only=n10,
                         acc_variant_only=n01, mcnemar_p=round(p, 4))  # fmt: skip
            rows.append(r)
    d = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out / "fragment_variants_summary.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(d.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

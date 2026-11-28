#!/usr/bin/env python3
"""Association variants counted with the metrics of METRICS.md, on any split of the deep COSMOS fields (2.62.7, task "러").

    python right_object_recount.py --root DIR --variants base file position same nearest same_nearest floored --out OUT [--base base]

``--root``  holds, per variant ``V``: ``meas_V/per_field_V.json`` (``measure_association.py``; one record per field, the catalogue counts of ``measure_field``).
Splits (the fields are the 26 deep COSMOS fields; the numbers of a split are SUMS of the field counts, the unit of independence is the field):

* ``cal9`` / ``conf17``  COSMOS fields 1-9 / 10-26: the calibration and the confirmation of the 2.61.8 study (``association_ambiguity``; the +46 / +32 claim is the confirmation);
* ``cal15`` / ``test11`` the split of ``fields_split.csv`` fixed for 2.60.9 (name hash; ``measure_association.py``'s "calibration" and "test");
* ``all26``.

Written (``OUT``):
* ``recount_counts.csv``  per variant, split and catalogue: rows, with_expected, matched, correct, false, unknown, missed, rightly_alone, alone_identified / alone_wrong / alone_unidentified, right_object (= correct + alone_identified), wrong_object (= false + alone_wrong), unidentified (= unknown + alone_unidentified), shared (own object holds a counterpart another object holds too: a fragment), displaced (own object holds none, another does) and the shifted-control counts
                          (``shift_false`` = joined to an object anchored by an unshifted catalogue, the 2.49.0 reading; ``shift_any`` = the object holds any unshifted row, anchor independent);
* ``recount_delta.csv``   the same against the base variant: delta of each count, the share of the change in ``correct`` that is only relabelling (``-d_alone_identified / d_correct``), the rates and
                          their change, and a field-bootstrap 95 % interval (2000 resamples of the fields of the split, seed 1) of the change in ``right_object`` and ``missed`` per 100 rows with an expected counterpart.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_info as RI  # noqa: E402

CATS = ("AllWISE", "GALEX AIS", "2MASS PSC")
# The readings a variant comparison may be concluded from: the ones METRICS.md marks as independent of who anchors an object (a test keeps the two in step).  The tables also carry
# correct / missed / rightly_alone / shifted_false_pct, which DO move with the anchor, only as side columns and for the relabel share.
HEADLINE = ("right_object", "wrong_object", "unidentified", "shared", "displaced", "shifted_any_pct")
COUNTS = ("rows", "no_expected", "matched", "correct", "false", "unknown", "missed", "rightly_alone", "alone_identified", "alone_wrong", "alone_unidentified", "shared", "displaced", "shift_rows", "shift_false", "shift_any")


SHIFT = ("shift_rows", "shift_false", "shift_any")  # only when the shifted-catalogue copy was measured


def field_table(root: Path, variant: str) -> pd.DataFrame:
    """Per field and catalogue the counts of ``measure_association.py``.  A count the measurement does not have is NOT read as 0 (Codex review of 2.62.10): a measurement
    made before ``alone_*`` / ``shared`` / ``displaced`` existed would report no fragments and turn right_object into the anchor-dependent ``correct``.  A missing
    required count stops the tool with the name of the folder to re-measure; the shift counts, which exist only with a shifted copy, stay missing (NaN)."""
    recs = json.loads((root / f"meas_{variant}" / f"per_field_{variant}.json").read_text())
    rows = []
    for r in recs:
        for c in CATS:
            if c in r:
                missing = [k for k in COUNTS if k not in r[c] and k not in SHIFT]
                if missing:
                    raise SystemExit(f"meas_{variant} {r['field']} {c}: the measurement has no {', '.join(missing)}; re-run measure_association.py (2.62.10) on this variant")
                rows.append({"variant": variant, "field": r["field"], "catalog": c, **{k: r[c].get(k, float("nan")) for k in COUNTS}})
    return pd.DataFrame(rows)


def split_fields(fields: list[str], split_csv: Path) -> dict[str, list[str]]:
    num = {f: int(f.rsplit("_", 1)[1]) for f in fields}
    sp = pd.read_csv(split_csv).set_index("name").split
    return {"cal9": [f for f in fields if num[f] <= 9], "conf17": [f for f in fields if num[f] >= 10],
            "cal15": [f for f in fields if sp.get(f) == "calibration"], "test11": [f for f in fields if sp.get(f) == "test"], "all26": list(fields)}  # fmt: skip


def totals(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby(["variant", "catalog"])[list(COUNTS)].sum(min_count=1).reset_index()  # min_count: a count missing in every field stays missing
    g["with_expected"] = g.rows - g.no_expected
    # the anchor independent reading (review of 2.62.7): the row sits in an object that holds an acceptable counterpart, joined (correct) or as the anchor (alone_identified)
    g["right_object"] = g.correct + g.alone_identified
    g["wrong_object"] = g["false"] + g.alone_wrong
    g["unidentified"] = g.unknown + g.alone_unidentified
    return g


def rates(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy()
    g["right_object_pct"] = (100 * g.right_object / g.with_expected).round(2)
    g["missed_pct"] = (100 * g.missed / g.with_expected).round(2)
    g["false_pct_of_matched_known"] = (100 * g.false / (g.correct + g.false)).round(2)
    g["shifted_false_pct"] = (100 * g.shift_false / g.shift_rows).round(2)
    g["shifted_any_pct"] = (100 * g.shift_any / g.shift_rows).round(2)
    return g


def bootstrap(per: pd.DataFrame, base: str, variant: str, cat: str, n: int = 2000, seed: int = 1) -> dict:
    """Field-level bootstrap of the change in right_object and missed (per 100 rows with an expected counterpart) of ``variant`` against ``base``."""
    a = per[(per.variant == base) & (per.catalog == cat)].set_index("field")
    b = per[(per.variant == variant) & (per.catalog == cat)].set_index("field").reindex(a.index)
    we = (a.rows - a.no_expected).to_numpy(float)
    d_ro = ((b.correct + b.alone_identified) - (a.correct + a.alone_identified)).to_numpy(float)
    d_mi = (b.missed - a.missed).to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    den = we[idx].sum(axis=1)
    out = {}
    for name, d in (("right_object", d_ro), ("missed", d_mi)):
        v = 100 * d[idx].sum(axis=1) / np.maximum(den, 1)
        lo, hi = np.percentile(v, [2.5, 97.5])
        out[f"d_{name}_pp"] = round(100 * float(d.sum()) / max(float(we.sum()), 1), 3)
        out[f"d_{name}_ci"] = f"{lo:.3f} to {hi:.3f}"
    out["fields_with_positive_d_right_object"] = int((d_ro > 0).sum())
    out["fields_with_negative_d_right_object"] = int((d_ro < 0).sum())
    return out


def compute(per: pd.DataFrame, splits: dict[str, list[str]], base_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(counts, deltas) of every split; ``per`` is the concatenation of ``field_table`` of the variants."""
    counts, deltas = [], []
    for sname, fields in splits.items():
        p = per[per.field.isin(fields)]
        g = rates(totals(p))
        g.insert(1, "split", sname)
        g.insert(2, "fields", len(fields))
        counts.append(g)
        base = g[g.variant == base_name].set_index("catalog")
        for _, r in g[g.variant != base_name].iterrows():
            b = base.loc[r.catalog]
            d = dict(variant=r.variant, split=sname, catalog=r.catalog, fields=len(fields), with_expected=int(r.with_expected))
            for k in ("matched", "correct", "false", "unknown", "missed", "rightly_alone", "alone_identified", "right_object", "wrong_object", "unidentified", "shared", "displaced", "shift_false", "shift_any"):
                d[f"d_{k}"] = int(r[k] - b[k])
            # the change in correct that is only a row moving from "anchors an object that holds its counterpart" to "joined to it": -d_alone_identified / d_correct
            d["relabel_share_of_d_correct_pct"] = round(100 * (-d["d_alone_identified"]) / d["d_correct"], 1) if d["d_correct"] else np.nan
            for k in ("right_object_pct", "missed_pct", "false_pct_of_matched_known", "shifted_false_pct", "shifted_any_pct"):
                d[f"d_{k}"] = round(float(r[k] - b[k]), 2)
            d.update(bootstrap(p, base_name, r.variant, r.catalog))
            deltas.append(d)
    return pd.concat(counts, ignore_index=True), pd.DataFrame(deltas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--base", default="base")
    ap.add_argument("--split-csv", type=Path, default=HERE / "fields_split.csv")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    per = pd.concat([field_table(a.root, v) for v in a.variants], ignore_index=True)
    splits = split_fields(sorted(per.field.unique(), key=lambda f: int(f.rsplit("_", 1)[1])), a.split_csv)
    counts_df, dd = compute(per, splits, a.base)
    counts_df.to_csv(a.out / "recount_counts.csv", index=False)
    dd.to_csv(a.out / "recount_delta.csv", index=False)
    with pd.option_context("display.width", 260, "display.max_columns", 40, "display.max_rows", 400):
        print(dd[dd.split.isin(["cal9", "conf17", "all26"])].drop(columns=["fields"]).sort_values(["split", "catalog", "variant"]).to_string(index=False))
    RI.write_args(a, ["root", "split_csv"], t0=t0, note="variants: " + " ".join(a.variants))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

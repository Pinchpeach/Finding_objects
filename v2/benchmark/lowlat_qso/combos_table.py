#!/usr/bin/env python3
"""The survey-count switches together with the association rules: low-latitude part of the decision table (2.61.10).

    python combos_table.py --variants base=ROOT surveys2=ROOT same_nearest=ROOT same_nearest_surveys2=ROOT ... \\
        --regions fields_lowlat_confirm.csv --truth lowlat_truth.csv.gz --out OUT.csv [--table-dir DIR]

``ROOT`` of a variant: ``<region>/objects.csv.gz`` (``variant.sh`` / ``score_lowlat_qso.py compact``); the first variant is the control.  Per variant, for one
set of regions (the 169 calibration or the 140 confirmation cones):

  quasars labelled QSO     the sample quasars (Wilson 95 %), and how many the control labels QSO that the variant does not (``quasars_lost_vs_control``;
                           sample quasars are matched by name, so this is valid when the association changes)
  false density            QSO labels that are not on a sample quasar, per deg^2: all cones, cones with Legacy Surveys DR10 objects ("LS"), cones without
                           ("noLS"); interval = bootstrap over the regions (the false labels cluster in a few cones), as ``ab_variants.py``
  exchange vs control      objects labelled QSO (not sample quasars) lost and gained, matched by POSITION inside a region (``lowlat_exchange.py``, 1''): the object
                           ids of ``ab_variants.py`` renumber when the association changes and its ``removed_per_deg2`` is not valid for such a variant

A cone is "LS" when the control has an object of DESI Legacy Surveys DR10 in it (as ``by_depth.py``).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ab_variants as AB  # noqa: E402
import score_lowlat_qso as S  # noqa: E402

_spec = importlib.util.spec_from_file_location("lowlat_exchange_tool", HERE.parent / "association_ambiguity" / "lowlat_exchange.py")
EX = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EX)
LS = "DESI Legacy Surveys DR10"


def ls_cones(control_root: Path, names) -> dict[str, bool]:
    out = {}
    for r in names:
        o = pd.read_csv(control_root / r / "objects.csv.gz", usecols=["catalogs"])
        out[r] = bool(o.catalogs.fillna("").str.contains(LS, regex=False).any())
    return out


def build(variants: list[tuple[str, Path]], regions: pd.DataFrame, truth: pd.DataFrame, radius: float = 3.0, tol: float = 1.0):
    regions, excluded, missing = S.common_regions(regions, [(n, str(r)) for n, r in variants])
    ls = ls_cones(variants[0][1], regions[regions.kind == "qso"].name)
    rows, meta, present, control = [], [], {}, None
    for name, root in variants:
        res = S.score_regions(regions, truth, root, radius)
        q = res["per_truth"]
        q = q[q.cls == "qso"].set_index("region")
        reg = AB.region_counts(res)
        n, k = len(q), int((q.label == "QSO").sum())
        lo, hi = S.wilson(k, n)
        row = dict(variant=name, quasars=n, quasars_qso=k, recall=round(k / n, 4), recall_lo=round(lo, 4), recall_hi=round(hi, 4))
        qso_names = set(q.name[q.label == "QSO"])
        if control is None:
            control = qso_names
        row["quasars_lost_vs_control"] = len(control - qso_names)
        for lab, sel in (("all", reg.name.notna()), ("LS_cones", reg.name.map(ls).fillna(False).astype(bool)), ("noLS_cones", ~reg.name.map(ls).fillna(True).astype(bool))):
            sub = reg[sel]
            est, l, h = AB.boot_density(sub, "all") if len(sub) else (math.nan, math.nan, math.nan)
            row.update({f"false_{lab}_regions": int(len(sub)), f"false_{lab}_n": int(sub["all"].sum()), f"false_{lab}_per_deg2": round(est, 1),
                        f"false_{lab}_lo": round(l, 1), f"false_{lab}_hi": round(h, 1)})  # fmt: skip
        oth = res["qso_other"][res["qso_other"].stratum != "contaminant"].copy()
        meta.append(oth)
        present[name] = set(zip(oth.region.astype(str), oth.object_id.astype(str)))
        row["area_deg2"] = round(float(reg.area_deg2.sum()), 4)
        rows.append(row)
    t = pd.concat(meta, ignore_index=True).drop_duplicates(subset=["region", "object_id"], keep="first")
    ids = list(zip(t.region.astype(str), t.object_id.astype(str)))
    for name, _ in variants:
        t[name] = [k in present[name] for k in ids]
    base = variants[0][0]
    for row in rows:
        if row["variant"] == base:
            continue
        e = EX.exchange(t, base, row["variant"], tol)
        a = row["area_deg2"]
        row.update(exch_lost=e["lost"], exch_gained=e["gained"], exch_lost_per_deg2=round(e["lost"] / a, 1), exch_gained_per_deg2=round(e["gained"] / a, 1),
                   exch_lost_i_lt_195=e["lost_i_lt_195"], exch_gained_i_lt_195=e["gained_i_lt_195"])  # fmt: skip
    return pd.DataFrame(rows), t, dict(regions_compared=int(len(regions)), excluded=excluded, missing_by_variant=missing)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", nargs="+", required=True, help="NAME=ROOT, the first is the control")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--radius", type=float, default=3.0)
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    variants = [(v.split("=", 1)[0], Path(v.split("=", 1)[1])) for v in a.variants]
    d, _, cov = build(variants, pd.read_csv(a.regions), pd.read_csv(a.truth), a.radius, a.tol)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out, index=False)
    print(cov)
    with pd.option_context("display.width", 280, "display.max_columns", 50):
        print(d.T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

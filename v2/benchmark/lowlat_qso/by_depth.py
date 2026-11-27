#!/usr/bin/env python3
"""False QSO density split by the depth of the cone: with / without a Legacy Surveys DR10 object (2.61.3).

    python by_depth.py --variants base=ROOT1 surveys2=ROOT2 ... --regions fields_lowlat_confirm.csv --truth lowlat_truth.csv.gz --out FILE.csv

The review of 2.61.2 (LOWLAT_QSO.md, Section 6) showed that the density of labels that are not on a sample quasar is not by itself a
sign of false labels: where Legacy Surveys reaches r ~ 23.5 the high-latitude quasar density to r < 23 is ~300 deg^-2, outside it
(PS1 + AllWISE depth) there is no quasar density to compare with.  A cone counts as "LS" when the control variant (the first)
has at least one object whose catalogues include DESI Legacy Surveys DR10.  One row per (cone group), columns: quasars, quasars
labelled QSO by the control, and per variant the labels not on a sample quasar (objects and per deg^2).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_lowlat_qso as S  # noqa: E402

LS = "DESI Legacy Surveys DR10"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", nargs="+", required=True, help="NAME=ROOT, the first is the control")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--radius", type=float, default=3.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    regions = pd.read_csv(a.regions)
    regions = regions[regions.kind == "qso"]
    truth = pd.read_csv(a.truth)
    area = math.pi * (a.radius / 60.0) ** 2
    control_root = Path(a.variants[0].split("=", 1)[1])
    has_ls = {}
    for r in regions.name:
        o = pd.read_csv(control_root / r / "objects.csv.gz", usecols=["catalogs"])
        has_ls[r] = bool(o.catalogs.fillna("").str.contains(LS, regex=False).any())
    rows = {flag: dict(ls_region=flag, regions=sum(v == flag for v in has_ls.values())) for flag in (True, False)}
    for flag, row in rows.items():
        row["area_deg2"] = round(row["regions"] * area, 4)
    for spec in a.variants:
        name, root = spec.split("=", 1)
        res = S.score_regions(regions, truth, Path(root), a.radius)
        T = res["per_truth"]
        q = T[T.cls == "qso"]
        o = res["qso_other"]
        o = o[o.stratum != "contaminant"] if len(o) else o
        for flag, row in rows.items():
            names = {r for r, v in has_ls.items() if v == flag}
            qq = q[q.region.isin(names)]
            row["quasars"] = len(qq)
            row[f"{name}_quasars_qso"] = int((qq.label == "QSO").sum())
            n = int(o.region.isin(names).sum()) if len(o) else 0
            row[f"{name}_false"] = n
            row[f"{name}_false_per_deg2"] = round(n / row["area_deg2"], 1) if row["area_deg2"] else math.nan
    d = pd.DataFrame(list(rows.values()))
    d.to_csv(a.out, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(d.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

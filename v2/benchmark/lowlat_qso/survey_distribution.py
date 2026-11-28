#!/usr/bin/env python3
"""The number of surveys of the objects of the low-latitude regions, by magnitude and by Legacy Surveys coverage (2.61.5).

    python survey_distribution.py --sets ROOT1:fields_lowlat.csv ROOT2:fields_lowlat_confirm.csv --out OUT

``ROOT`` is the compact record of the base run of a region set (``<region>/objects.csv.gz`` with its ``raw`` folder, as written by
``score_lowlat_qso.py compact``).  For every top-level object inside a 3' cone (the 169 calibration and 140 confirmation regions: the
310 regions of the two sets) it takes the number of surveys that measure it (``lowlat_qso.n_surveys``: one per survey, annotation
catalogues left out), its Pan-STARRS1 i magnitude from the raw files, whether the cone holds any Legacy Surveys DR10 object, and
whether the base labels it QSO.  ``survey_distribution.csv``: for the whole population and for the objects labelled QSO, by cone group
(LS / no LS) and PS1 i bin, the counts of objects with 1, 2, 3, 4+ surveys and the shares with at least 2 and at least 3.  The shares
with at least 3 surveys at i >= 21 outside Legacy Surveys are the reason ``surveys3`` can hardly label a faint object there.
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
import score_lowlat_qso as S  # noqa: E402

_spec = importlib.util.spec_from_file_location("lowlat_qso_dist", HERE.parents[1] / "Preprocess" / "lowlat_qso.py")
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)

LS = "DESI Legacy Surveys DR10"
BINS = [(-np.inf, 19.0), (19.0, 20.0), (20.0, 21.0), (21.0, 22.0), (22.0, np.inf)]


def collect(root: Path, regions: pd.DataFrame, radius_arcmin: float = 3.0) -> pd.DataFrame:
    parts = []
    for r in regions.itertuples():
        f = root / r.name / "objects.csv.gz"
        if not f.exists():
            continue
        o = pd.read_csv(f, low_memory=False, usecols=lambda c: c in {"object_id", "ra", "dec", "catalogs", "primary_class", "parent_object_id"})
        o = o[o.parent_object_id.isna()] if "parent_object_id" in o else o
        sep = S._sep_arcsec(o.ra.to_numpy(float), o.dec.to_numpy(float), r.ra, r.dec) / 60.0
        o = o[sep <= radius_arcmin].copy()
        o["region"] = r.name
        o["ls_cone"] = bool(o.catalogs.fillna("").str.contains(LS, regex=False).any())
        o["n_surveys"] = LL.n_surveys(o.catalogs)
        o["ps1_i"] = S.ps1_mags(root / r.name / "raw", o.ra.to_numpy(float), o.dec.to_numpy(float))
        parts.append(o.drop(columns=["catalogs", "parent_object_id"], errors="ignore"))
    return pd.concat(parts, ignore_index=True)


def table(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pop, x0 in (("all objects", d), ("labelled QSO", d[d.primary_class == "QSO"])):
        for grp, x1 in (("all", x0), ("LS cones", x0[x0.ls_cone]), ("no-LS cones", x0[~x0.ls_cone])):
            for lo, hi in [*BINS, (None, None)]:
                if lo is None:
                    x, name = x1[x1.ps1_i.isna()], "no PS1"
                else:
                    x = x1[(x1.ps1_i >= lo) & (x1.ps1_i < hi)]
                    name = f"<{hi:g}" if lo == -np.inf else (f">={lo:g}" if hi == np.inf else f"{lo:g}-{hi:g}")
                n = len(x)
                row = dict(population=pop, cones=grp, ps1_i=name, objects=n)
                for k, lab in ((1, "1"), (2, "2"), (3, "3")):
                    row[f"surveys_{lab}"] = int((x.n_surveys == k).sum())
                row["surveys_4plus"] = int((x.n_surveys >= 4).sum())
                row["surveys_0"] = int((x.n_surveys == 0).sum())
                row["share_ge2"] = round(float((x.n_surveys >= 2).mean()), 4) if n else math.nan
                row["share_ge3"] = round(float((x.n_surveys >= 3).mean()), 4) if n else math.nan
                rows.append(row)
    return pd.DataFrame(rows)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="+", required=True, help="ROOT:fields.csv")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    parts = []
    for spec in a.sets:
        root, fields = spec.rsplit(":", 1)
        reg = pd.read_csv(fields)
        reg = reg[reg.kind == "qso"]
        parts.append(collect(Path(root), reg))
    d = pd.concat(parts, ignore_index=True)
    d.to_csv(a.out / "objects_surveys.csv.gz", index=False)
    t = table(d)
    t.to_csv(a.out / "survey_distribution.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(t[t.cones != "all"].to_string(index=False))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

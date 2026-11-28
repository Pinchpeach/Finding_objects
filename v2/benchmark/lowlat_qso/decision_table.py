#!/usr/bin/env python3
"""The decision table of the survey-count switches: what they remove and what they can cost (2.61.5).

    python decision_table.py --results results_2026-11-27c --earlier results_2026-11-27b --out decision_table.csv

One row per variant (``surveys2``, ``surveys3``, ``wise_second``, and the two survey switches with ``spectro_keep``), one column
per number that decides it, each read from a table the other scripts of this folder write:

  removed_*            the false-QSO density the variant removes in the 140 confirmation regions (paired region bootstrap, ``ab_variants.py``)
                       and what is left; the same by Legacy Surveys coverage of the cone (``by_depth.py``)
  bright_lost          sample quasars (PS1 + AllWISE selected, all with >= 3 surveys) the variant stops labelling QSO: confirmation, calibration
  cosmos_lost          deep COSMOS type 1 AGN the base labels QSO and the variant does not (latitude limit lifted, ``faint_cost.py``)
  ceiling_*            the share of objects / quasars that has enough surveys to be labelled QSO at all: low-latitude cones without Legacy
                       Surveys at PS1 i 20-21 and 21-22, COSMOS type 1 AGN at r 22-23 and 23-24, SDSS sky-benchmark quasars at r >= 22
                       (with SDSS imaging as a survey), DESI quasars at r >= 22
  spectroscopic_held   objects with a spectral class QSO (SDSS, DESI, LAMOST) the variant holds back at low latitude
"""

from __future__ import annotations

import sys

import argparse
import math
from pathlib import Path

import pandas as pd


def frac(k, n) -> str:
    return f"{int(k)}/{int(n)}"


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--earlier", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    R, E = a.results, a.earlier
    conf = pd.read_csv(R / "recheck_main_version" / "confirmation_ab_variants.csv").set_index("variant")
    cal = pd.read_csv(R / "recheck_main_version" / "calibration_ab_variants.csv").set_index("variant")
    depth = pd.read_csv(E / "confirmation" / "by_ls_coverage.csv").set_index("ls_region")
    loss = pd.read_csv(R / "faint_cost" / "type1_loss_by_r.csv")
    ceil_cosmos = pd.read_csv(R / "faint_cost" / "type1_ceiling_by_r.csv").set_index("r")
    dist = pd.read_csv(R / "survey_distribution" / "survey_distribution.csv")
    bench = pd.read_csv(R / "benchmark_cost" / "benchmark_cost.csv")
    spec = pd.read_csv(R / "spectro" / "spectroscopic_qso_objects.csv")
    n_spec = int((spec.label_base == "QSO").sum())
    rows = []
    for name, need, key in (("surveys2", 2, "surveys2"), ("surveys3", 3, "surveys3"), ("wise_second", 0, "wise_second"),
                            ("surveys2+spectro_keep", 2, "surveys2"), ("surveys3+spectro_keep", 3, "surveys3")):  # fmt: skip
        keep = name.endswith("spectro_keep")
        c, k = conf.loc[key], cal.loc[key]
        row = dict(variant=name,
                   removed_per_deg2_confirmation=f"{c.removed_per_deg2:.0f} [{c.removed_lo:.0f}-{c.removed_hi:.0f}]",
                   false_per_deg2_before_after=f"{conf.loc['base'].false_all_per_deg2:.0f} -> {c.false_all_per_deg2:.0f}",
                   false_per_deg2_LS_cones=f"{depth.loc[True, 'base_false_per_deg2']:.0f} -> {depth.loc[True, key + '_false_per_deg2']:.0f}",
                   false_per_deg2_noLS_cones=f"{depth.loc[False, 'base_false_per_deg2']:.0f} -> {depth.loc[False, key + '_false_per_deg2']:.0f}",
                   bright_lost_confirmation=frac(c.quasars_lost_vs_control, c.quasars), bright_lost_calibration=frac(k.quasars_lost_vs_control, k.quasars))  # fmt: skip
        if need:
            for lab, rs in (("all", ["all"]), ("r<22", ["<20", "20-21", "21-22"]), ("22-24", ["22-23", "23-24"])):
                x = loss[(loss.variant == key) & (loss.truth == "type1") & loss.r.isin(rs)]
                row[f"cosmos_lost_{lab}"] = frac(x.lost.sum(), x.qso_base.sum())
            for lab, r in (("22-23", "22-23"), ("23-24", "23-24")):
                row[f"ceiling_cosmos_type1_r{lab}"] = round(float(ceil_cosmos.loc[r, "ge2" if need == 2 else "ge3"]), 3)
            d = dist[(dist.population == "all objects") & (dist.cones == "no-LS cones")].set_index("ps1_i")
            for b in ("20-21", "21-22"):
                row[f"ceiling_noLS_cones_i{b}"] = round(float(d.loc[b, "share_ge2" if need == 2 else "share_ge3"]), 3)
            s = bench[(bench.set == "sdss_sky") & (bench.group == "all") & (bench.truth_class == "QSO") & (bench.mag == ">=22")]
            row["ceiling_sdss_sky_r>=22"] = round(1 - float(s["frac_lt2_plus_sdss" if need == 2 else "frac_lt3_plus_sdss"].iloc[0]), 3) if len(s) else math.nan
            s = bench[(bench.set == "desi_external") & (bench.group == "all") & (bench.truth_class == "QSO") & (bench.mag == ">=22")]
            row["ceiling_desi_r>=22"] = round(1 - float(s["frac_lt2" if need == 2 else "frac_lt3"].iloc[0]), 3) if len(s) else math.nan
            held = spec[(spec.label_base == "QSO") & (spec[f"label_{key}{'_keep' if keep else ''}"] != "QSO")]
            row["spectroscopic_held"] = frac(len(held), n_spec)
        rows.append(row)
    d = pd.DataFrame(rows)
    d.to_csv(a.out, index=False)
    with pd.option_context("display.width", 280, "display.max_columns", 40, "display.max_colwidth", 40):
        print(d.T.to_string())
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

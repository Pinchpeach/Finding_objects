#!/usr/bin/env python3
"""What the objects grouped under a parent are in the COSMOS2020 truth, by type (2.60.11).

    python wrong_merge_types.py --runs DIR --truth-flux DIR --variant NAME --out DIR [--env KEY=VALUE ...]

``regroup.py`` counts a grouped object as "wrong" when its truth source differs from the parent's, which is an upper
bound: a parent with no truth source within 0.6'' counts too.  This script replays the same grouping (same arguments as
``regroup.py``) and sorts every grouped object into one type, first match wins:

  same            the child and the parent are the same truth source: a duplicate or shred, the grouping is right
  no_truth        no truth source within 0.6'' of the child: a spurious row or a source COSMOS2020 does not list
  star_or_agn     the child is a truth star (ACSmuClass 2 and SED type 1) or an X-ray AGN / QSO (SED type 2) and the
                  parent is another source: a real star / QSO put under a galaxy
  neighbour       both have a truth source, the sources differ and lie more than 1'' apart: a real neighbouring source
                  swallowed
  close_pair      both have a truth source, the sources differ but lie within 1'': two COSMOS2020 entries of one galaxy
                  (deblending), probably not wrong
  parent_no_truth the child has a truth source, the parent has none within 0.6'': undecided

"Actual" wrong merges are ``star_or_agn + neighbour``; the upper bound (what ``regroup.py`` prints as "wrong") adds
``close_pair + parent_no_truth``.  The pipeline's own label of the child (STAR / QSO under a GALAXY parent) is counted
beside, since most faint PSF shreds are labelled STAR without being a star.

Only the calibration half is listed object by object (``wrong_merge_objects_<variant>_calibration.csv``); the test half
is counted, never listed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_association as M  # noqa: E402
import regroup as R  # noqa: E402

CLOSE_ARCSEC = 1.0


def truth_kind(truth: pd.DataFrame) -> np.ndarray:
    """STAR / AGN / GALAXY / other for every COSMOS2020 source (ACS morphology and SED type, as the score's truth)."""
    mu = pd.to_numeric(truth.get("ACSmuClass"), errors="coerce")
    lp = pd.to_numeric(truth.get("lptype"), errors="coerce")
    kind = np.full(len(truth), "other", dtype=object)
    kind[(mu.eq(1) & lp.eq(0)).to_numpy()] = "GALAXY"
    kind[(mu.eq(2) & lp.eq(1)).to_numpy()] = "STAR"
    kind[lp.eq(2).to_numpy()] = "AGN"
    return kind


def classify(out: pd.DataFrame, truth: pd.DataFrame, field: str, split: str) -> pd.DataFrame:
    role = out.component_role.fillna("").astype(str)
    kids = np.flatnonzero(role.isin(R.GROUP_ROLES).to_numpy())
    if not len(kids):
        return pd.DataFrame()
    full = M.Sky(truth.ra, truth.dec)
    t_obj, _ = full.nearest(out.ra.to_numpy(float), out.dec.to_numpy(float), M.ID_RADIUS)
    kind = truth_kind(truth)
    row_of = pd.Series(np.arange(len(out)), index=out.object_id)
    rows = []
    for i in kids:
        p = row_of.get(out.parent_object_id.iat[i])
        tc, tp = int(t_obj[i]), (int(t_obj[p]) if p is not None else -1)
        sep_tt = np.nan
        if tc >= 0 and tp >= 0 and tc != tp:
            sep_tt = float(
                M.Sky._arcsec(
                    np.linalg.norm(
                        M._xyz(*truth.loc[[tc], ["ra", "dec"]].to_numpy(float).T)
                        - M._xyz(*truth.loc[[tp], ["ra", "dec"]].to_numpy(float).T)
                    )
                )
            )
        if tc < 0:
            typ = "no_truth"
        elif tc == tp:
            typ = "same"
        elif kind[tc] in ("STAR", "AGN"):
            typ = "star_or_agn"
        elif tp >= 0:
            typ = "neighbour" if sep_tt > CLOSE_ARCSEC else "close_pair"
        else:
            typ = "parent_no_truth"
        rows.append(
            dict(field=field, split=split, role=role.iat[i], type=typ,
                 child=out.object_id.iat[i], parent=out.parent_object_id.iat[i],
                 child_class=out.primary_class.iat[i], parent_class=out.primary_class.iat[p] if p is not None else "",
                 child_ra=float(out.ra.iat[i]), child_dec=float(out.dec.iat[i]),
                 child_truth_kind=kind[tc] if tc >= 0 else "", parent_truth_kind=kind[tp] if tp >= 0 else "",
                 child_truth_i=float(truth["HSCimagAuto"].iat[tc]) if tc >= 0 else np.nan,
                 parent_truth_i=float(truth["HSCimagAuto"].iat[tp]) if tp >= 0 else np.nan,
                 truth_truth_sep=sep_tt))  # fmt: skip
    return pd.DataFrame(rows)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--env", nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    for kv in a.env:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    hosts = R.load_module(R.V2 / "host_groups.py", "v2_host_groups_types")
    fields = pd.read_csv(HERE / "fields_split.csv").set_index("name")
    split = fields.split
    a.out.mkdir(parents=True, exist_ok=True)
    parts = []
    for name in split.index:
        out0 = pd.read_csv(a.runs / name / "classified_objects.csv", low_memory=False)
        assoc = pd.read_csv(
            a.runs / name / "source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"}
        )
        truth = M.load_truth(a.truth_flux / f"{name}.csv.gz", (fields.ra[name], fields.dec[name]))
        out = R.apply_steps(R.strip_grouping(out0), assoc, hosts)
        parts.append(classify(out, truth, name, split[name]))
    d = pd.concat(parts, ignore_index=True)
    d[d.split == "calibration"].to_csv(a.out / f"wrong_merge_objects_{a.variant}_calibration.csv", index=False)
    d["child_star_qso_under_galaxy"] = d.child_class.isin(["STAR", "QSO"]) & d.parent_class.eq("GALAXY")
    agg = (
        d.groupby(["split", "role", "type"]).size().unstack("type", fill_value=0)
        .reindex(columns=["same", "no_truth", "star_or_agn", "neighbour", "close_pair", "parent_no_truth"], fill_value=0)
    )  # fmt: skip
    agg["grouped"] = agg.sum(axis=1)
    agg["actual_wrong"] = agg.star_or_agn + agg.neighbour
    agg["upper_bound_wrong"] = agg.actual_wrong + agg.close_pair + agg.parent_no_truth
    labelled = d.groupby(["split", "role"]).child_star_qso_under_galaxy.sum()
    agg["pipeline_star_or_qso_under_galaxy"] = labelled
    agg = agg.reset_index()
    agg.insert(0, "variant", a.variant)
    agg.to_csv(a.out / f"wrong_merge_types_{a.variant}.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(agg.to_string(index=False))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

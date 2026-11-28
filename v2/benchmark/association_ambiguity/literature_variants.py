#!/usr/bin/env python3
"""What the V2_ANNOT_ASSOC variants change for the literature (NED / SIMBAD) rows of one field, judged against COSMOS2020 (2.62.6).

    python literature_variants.py --truth TRUTH.csv.gz --base DIR --variants name=DIR [name=DIR ...] --out OUT [--classified-base CSV]

Each DIR holds the ``source_association.csv`` of one Stage-1 run (``literature_only.py --env V2_ANNOT_ASSOC=...``) on the same raw folder, so a detection
has the same ``detection_id`` in every run.  For every variant against the base run:

* ``lit_only_objects``   objects made only of NED / SIMBAD rows; ``lit_rows_attached`` literature rows that sit in an object holding a survey row;
* new joins              literature rows that are in an object with survey rows in the variant and were not in the base run.  Each is judged by the
  bridge written down in PREDICTIONS_LITERATURE_2026-11-28.md: the reference set R is COSMOS2020 sources with HSC i < 25; the literature row and the
  survey object each take the nearest R source within 0.6'' (the object by its anchor position, only when the anchor is a resolving catalogue; an
  AllWISE / 2MASS / GALEX / radio anchor is "unknown").  ``right`` = same R source, ``wrong`` = different R sources, ``unknown`` = one side has none;
* extended bridge (added AFTER the first run, because the predeclared one left 98 % of the ``density`` joins "unknown": most literature rows are fainter than
  i = 25 and have no R source): the literature row takes the nearest COSMOS2020 source of ANY magnitude within 0.3'' (``literature_position_accuracy.py``: 64 % of
  SIMBAD rows lie that close, a random position 1 %), the object keeps its R id; ``right_ext`` / ``wrong_ext`` / ``unknown_ext`` as above;
* lit-lit merges        literature-only objects of the base run that are no longer separate (rows of two objects that now share one);
* QSO labels            how many of the 16 literature-QSO objects of the base run (``--classified-base``) are attached.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
import measure_association as MA  # noqa: E402

LIT = ("NED", "SIMBAD")


def load(d: Path) -> pd.DataFrame:
    a = pd.read_csv(d / "source_association.csv", low_memory=False)
    a["is_lit"] = a.catalog.isin(LIT)
    return a


def objects(a: pd.DataFrame) -> pd.DataFrame:
    g = a.groupby("object_id")
    o = pd.DataFrame({"n_rows": g.size(), "n_lit": g.is_lit.sum(), "ra": g.object_ra.first(), "dec": g.object_dec.first(), "anchor": g.object_anchor_catalog.first()})
    o["lit_only"] = o.n_lit == o.n_rows
    return o


def r_ids(truth: pd.DataFrame, ra, dec, radius=MA.ID_RADIUS):
    ref = truth[truth["HSCimagAuto"] < MA.REF_MAG]
    sky = MA.Sky(ref.ra.to_numpy(float), ref.dec.to_numpy(float))
    i, sep = sky.nearest(np.asarray(ra, float), np.asarray(dec, float), radius)
    ids = np.where(i >= 0, ref.index.to_numpy()[np.clip(i, 0, None)], -1)
    return ids, sep


def compare(base: pd.DataFrame, var: pd.DataFrame, truth: pd.DataFrame, qso_ids: set) -> tuple[dict, pd.DataFrame]:
    ob, ov = objects(base), objects(var)
    lit = var[var.is_lit].merge(base[["detection_id", "object_id"]].rename(columns={"object_id": "base_object"}), on="detection_id")
    lit["base_attached"] = ~lit.base_object.map(ob.lit_only)
    lit["var_attached"] = ~lit.object_id.map(ov.lit_only)
    new = lit[(~lit.base_attached) & lit.var_attached].copy()
    ids_l, sep_l = r_ids(truth, new.ra, new.dec)
    new["lit_id"], new["lit_sep"] = ids_l, sep_l
    new["obj_ra"], new["obj_dec"] = new.object_id.map(ov.ra), new.object_id.map(ov.dec)
    new["anchor"] = new.object_id.map(ov.anchor)
    new["separation"] = np.hypot((new.ra - new.obj_ra) * np.cos(np.radians(new.dec)), new.dec - new.obj_dec) * 3600.0
    allsky = MA.Sky(truth.ra.to_numpy(float), truth.dec.to_numpy(float))
    j, _ = allsky.nearest(new.ra.to_numpy(float), new.dec.to_numpy(float), 0.3)
    new["lit_id_any"] = np.where(j >= 0, truth.index.to_numpy()[np.clip(j, 0, None)], -1)
    ids_o, _ = r_ids(truth, new.obj_ra, new.obj_dec)
    resolving = new.anchor.isin(MA.RESOLVING)
    new["obj_id"] = np.where(resolving, ids_o, -1)
    new["verdict"] = np.where((new.lit_id >= 0) & (new.obj_id >= 0), np.where(new.lit_id == new.obj_id, "right", "wrong"), "unknown")
    new["verdict_ext"] = np.where((new.lit_id_any >= 0) & (new.obj_id >= 0), np.where(new.lit_id_any == new.obj_id, "right", "wrong"), "unknown")
    # lit-lit merges: base literature-only objects whose rows now share an object with another base literature-only object
    bl = lit[lit.base_object.map(ob.lit_only)]
    merged = bl.groupby("object_id").base_object.nunique()
    res = dict(
        lit_only_objects=int(ov.lit_only.sum()),
        lit_rows_attached=int(lit.var_attached.sum()),
        new_joins_rows=len(new),
        new_joins_objects=int(new.base_object.nunique()),
        right=int((new.verdict == "right").sum()),
        wrong=int((new.verdict == "wrong").sum()),
        unknown=int((new.verdict == "unknown").sum()),
        lit_lit_merged_objects=int((merged[merged > 1] - 1).sum()),
    )
    for k in ("right", "wrong", "unknown"):
        res[k + "_ext"] = int((new.verdict_ext == k).sum())
    res["right_share_of_known_ext_pct"] = round(100.0 * res["right_ext"] / max(1, res["right_ext"] + res["wrong_ext"]), 1)
    res["right_share_of_known_pct"] = round(100.0 * res["right"] / max(1, res["right"] + res["wrong"]), 1)
    qa = lit[lit.base_object.isin(qso_ids)]
    res["qso_objects_attached"] = int(qa[qa.var_attached].base_object.nunique())
    res["qso_objects_total"] = len(qso_ids)
    return res, new


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--classified-base", type=Path, help="literature_only_objects.csv of the base run with cl_primary_class (the QSO objects)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    truth = MA.load_truth(a.truth)
    base = load(a.base)
    qso = set()
    if a.classified_base:
        t = pd.read_csv(a.classified_base)
        qso = set(t[t.cl_primary_class == "QSO"].object_id)
    rows = []
    ob = objects(base)
    rows.append(dict(variant="base", lit_only_objects=int(ob.lit_only.sum()), lit_rows_attached=int((~base[base.is_lit].object_id.map(ob.lit_only)).sum())))
    for kv in a.variants:
        name, d = kv.split("=", 1)
        res, new = compare(base, load(Path(d)), truth, qso)
        rows.append(dict(variant=name, **res))
        new.to_csv(a.out / f"new_joins_{name}.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(a.out / "literature_variants.csv", index=False)
    print(out.T.to_string(header=False))
    RI.write_args(a, ('truth', 'base', 'variants', 'classified_base'), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

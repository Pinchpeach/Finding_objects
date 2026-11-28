#!/usr/bin/env python3
"""Two runs of the same regions compared by what the objects are made of (2.62.2).

    python compare_by_members.py --a DIR_LEGACY --b DIR_FIXED --regions regions_changed.csv --out DIR

``DIR/<set>/<region>/{classified_objects.csv, source_association.csv}`` from ``run_pe.py``.  Object ids are not comparable between runs (an association change
shifts the sequential numbers) and, in this study, neither are the anchor positions: a VLASS row that is the anchor in one run and not in the other moves its
object by the radio-optical offset, so the position matching of ``association_ambiguity/label_changes.py`` (0.2'') would miss the pair.  ``detection_id``
(``<file stem>:<row>``) is the same in every run of the same raw files, so:

  object signature     the set of ``detection_id`` of an object
  same object          the same signature in both runs: only the labels can differ (a pure effect of the inputs of the classifier)
  changed object       a signature present in one run only; paired with the object of the other run that shares most of its detections (Jaccard)
  radio row            a detection of VLASS / NVSS / FIRST / TGSS / LoTSS: ``joined`` when its object holds a detection of another (non-radio) catalogue
  anchor               ``object_anchor_catalog`` of the object (the catalogue whose position the object carries)

Written: ``summary.csv`` (per set and total), ``radio_rows.csv`` (every radio row with its status in both runs), ``label_changes.csv`` (every object whose
primary / axis / subclass label differs, with its radio rows and whether its signature changed), ``anchor_changes.csv``.
"""

from __future__ import annotations

import sys

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RADIO = {"VLASS", "NVSS", "FIRST", "TGSS ADR1", "LoTSS DR2"}
LABELS = ["primary_class", "detailed_class", "physical_class", "variability_class", "compact_class", "extragalactic_class", "extragalactic_subtype",
          "phenomenon_class", "subclass", "subclass_code", "secondary_class", "classification_status", "high_confidence"]  # fmt: skip
RADIO_COLS = ["std_radio_first_mjy", "std_radio_nvss_mjy", "std_radio_lotss_144mhz_mjy", "std_radio_vlass_3ghz_mjy", "std_radio_1p4ghz_mjy"]


def load(d: Path):
    assoc = pd.read_csv(d / "source_association.csv", low_memory=False)
    obj = pd.read_csv(d / "classified_objects.csv", low_memory=False)
    return assoc, obj


def signatures(assoc: pd.DataFrame) -> dict:
    """object_id -> frozenset of detection ids"""
    return {k: frozenset(g) for k, g in assoc.groupby("object_id")["detection_id"]}


def radio_rows(assoc: pd.DataFrame) -> pd.DataFrame:
    cats = assoc.groupby("object_id")["catalog"].agg(lambda s: set(s))
    r = assoc[assoc.catalog.isin(RADIO)].copy()
    r["joined"] = [bool(cats[o] - RADIO) for o in r.object_id]
    r["anchor"] = r.object_anchor_catalog if "object_anchor_catalog" in r else np.nan
    return r[["detection_id", "catalog", "object_id", "joined", "anchor", "association_status", "poserr_arcsec"]]


def radio_anchored_with_optical(assoc: pd.DataFrame) -> int:
    """Objects that carry a radio position (anchor VLASS / NVSS / FIRST / TGSS / LoTSS) although they hold a non-radio detection."""
    g = assoc.groupby("object_id").agg(anchor=("object_anchor_catalog", "first"), cats=("catalog", lambda s: set(s)))
    return int(sum(1 for a, c in zip(g.anchor, g.cats) if a in RADIO and (c - RADIO)))


def compare_region(a: tuple, b: tuple) -> dict:
    """``a`` and ``b`` are ``load()`` results of the two runs of one region."""
    (assoc_a, obj_a), (assoc_b, obj_b) = a, b
    sig_a, sig_b = signatures(assoc_a), signatures(assoc_b)
    by_sig_b = {s: o for o, s in sig_b.items()}
    same = {oa: by_sig_b[s] for oa, s in sig_a.items() if s in by_sig_b}
    only_a = [oa for oa, s in sig_a.items() if s not in by_sig_b]
    owner_b = {d: o for o, s in sig_b.items() for d in s}  # detection -> object of run b
    paired = {}
    for oa in only_a:
        votes = pd.Series([owner_b.get(d) for d in sig_a[oa]]).value_counts()
        if len(votes):
            ob = votes.index[0]
            paired[oa] = (ob, len(sig_a[oa] & sig_b[ob]) / len(sig_a[oa] | sig_b[ob]))
    ra, rb = radio_rows(assoc_a), radio_rows(assoc_b)
    rr = ra.merge(rb, on="detection_id", suffixes=("_a", "_b"))
    top_a = obj_a[obj_a.parent_object_id.isna()].set_index("object_id") if "parent_object_id" in obj_a else obj_a.set_index("object_id")
    top_b = obj_b[obj_b.parent_object_id.isna()].set_index("object_id") if "parent_object_id" in obj_b else obj_b.set_index("object_id")
    changes = []
    for kind, pairs in (("same_members", {oa: ob for oa, ob in same.items()}), ("changed_members", {oa: ob for oa, (ob, _) in paired.items()})):
        for oa, ob in pairs.items():
            if oa not in top_a.index or ob not in top_b.index:
                continue
            xa, xb = top_a.loc[oa], top_b.loc[ob]
            diff = [c for c in LABELS if c in top_a and c in top_b and not (pd.isna(xa[c]) and pd.isna(xb[c])) and xa[c] != xb[c]]
            rad = [c for c in RADIO_COLS if c in top_a and c in top_b and not (pd.isna(xa[c]) and pd.isna(xb[c])) and not np.isclose(xa[c], xb[c], equal_nan=True)]
            if diff or rad:
                changes.append(dict(kind=kind, object_a=oa, object_b=ob, catalogs_a=xa.get("catalogs"), catalogs_b=xb.get("catalogs"),
                                    columns="|".join(diff), radio_columns="|".join(rad), **{f"{c}_a": xa[c] for c in diff}, **{f"{c}_b": xb[c] for c in diff}))  # fmt: skip
    anc_a = assoc_a.drop_duplicates("object_id").set_index("object_id")
    anc_b = assoc_b.drop_duplicates("object_id").set_index("object_id")
    shifts, anchor_changed = [], []
    # every mapped object: the same detections with a new anchor (the VLASS -> optical case of the unit fix) as well as the changed ones (Codex review of 2.62.2)
    mapped = [("same_members", oa, ob) for oa, ob in same.items()] + [("changed_members", oa, ob) for oa, (ob, _) in paired.items()]
    for kind, oa, ob in mapped:
        if oa in anc_a.index and ob in anc_b.index:
            pa, pb = anc_a.loc[oa], anc_b.loc[ob]
            dx = (pa.object_ra - pb.object_ra) * np.cos(np.deg2rad(pa.object_dec)) * 3600.0
            dy = (pa.object_dec - pb.object_dec) * 3600.0
            shifts.append(float(np.hypot(dx, dy)))
            if pa.object_anchor_catalog != pb.object_anchor_catalog:
                anchor_changed.append(dict(kind=kind, object_a=oa, object_b=ob, anchor_a=pa.object_anchor_catalog, anchor_b=pb.object_anchor_catalog, shift_arcsec=shifts[-1]))
    return dict(n_objects_a=len(sig_a), n_objects_b=len(sig_b), same=len(same), changed_a=len(only_a), changed_b=len(sig_b) - len(same), radio=rr,
                label_changes=pd.DataFrame(changes), anchor_changes=pd.DataFrame(anchor_changed), shifts=shifts,
                anchors_a=radio_anchored_with_optical(assoc_a), anchors_b=radio_anchored_with_optical(assoc_b))  # fmt: skip


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", type=Path, required=True, help="the first run (legacy)")
    ap.add_argument("--b", type=Path, required=True, help="the second run (fixed)")
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    regs = pd.read_csv(a.regions)
    rows, radio, lab, anc = [], [], [], []
    for r in regs.itertuples():
        pa, pb = a.a / r.set / r.region, a.b / r.set / r.region
        if not (pa / "classified_objects.csv").exists() or not (pb / "classified_objects.csv").exists():
            print("MISSING", r.set, r.region)
            continue
        c = compare_region(load(pa), load(pb))
        rows.append(dict(set=r.set, region=r.region, objects_a=c["n_objects_a"], objects_b=c["n_objects_b"], same_members=c["same"], changed_a=c["changed_a"], changed_b=c["changed_b"],
                         radio_anchored_a=c["anchors_a"], radio_anchored_b=c["anchors_b"], label_changes=len(c["label_changes"]),
                         median_shift_arcsec=float(np.median(c["shifts"])) if c["shifts"] else np.nan))  # fmt: skip
        for tab, store in ((c["radio"], radio), (c["label_changes"], lab), (c["anchor_changes"], anc)):
            if len(tab):
                store.append(tab.assign(set=r.set, region=r.region))
    pd.DataFrame(rows).to_csv(a.out / "per_region.csv", index=False)
    pd.concat(radio).to_csv(a.out / "radio_rows.csv", index=False) if radio else None
    pd.concat(lab).to_csv(a.out / "label_changes.csv", index=False) if lab else None
    pd.concat(anc).to_csv(a.out / "anchor_changes.csv", index=False) if anc else None
    per = pd.DataFrame(rows)
    summ = per.groupby("set").agg(regions=("region", "size"), objects_a=("objects_a", "sum"), objects_b=("objects_b", "sum"), same_members=("same_members", "sum"),
                                  changed_a=("changed_a", "sum"), changed_b=("changed_b", "sum"), radio_anchored_a=("radio_anchored_a", "sum"),
                                  radio_anchored_b=("radio_anchored_b", "sum"), label_changes=("label_changes", "sum"))  # fmt: skip
    summ.loc["total"] = summ.sum()
    summ.to_csv(a.out / "summary.csv")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(summ.to_string())
    RI.write_args(a, ('a', 'b', 'regions'), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

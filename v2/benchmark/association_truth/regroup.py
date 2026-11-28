#!/usr/bin/env python3
"""Replay the three grouping steps of ``pipeline.py`` on a finished run and score fragments against COSMOS2020 (2.60.9).

    python regroup.py --runs DIR --truth-flux DIR --variant base|... --out DIR [--fields-root DIR]

The fragment grouping happens after classification (``host_groups.attach_ps1_fragments``, ``attach_galaxy_fragments``,
``attach_bright_star_artifacts``) and changes no ``primary_class``, only which objects stay top-level.  The label a
truth source gets in the score is the class of the object's parent when it is grouped (``score_accuracy``, as
``score_independent_fields.field_matches`` reads it), so a rule that puts an object of another class under a host does
change labels (``labels_changed``), while one that puts only GALAXY objects under GALAXY hosts (``V2_FRAG_HOST_CANDIDATE``
alone) cannot.  So a variant of these rules
can be tried on the stored ``classified_objects.csv`` of a base run without collecting or classifying again: the
grouping that the base run applied (roles ps1_duplicate / fragment / bright_star_halo) is removed, the three steps are
applied again with the variant, and the result is scored.  ``variant=base`` must give the grouping the run had (the
script prints the share of objects whose parent is the same).  Not replayed: the later steps (``subclass.annotate``
for hosts that gained components, detection quality, radio, clusters), which do not change the grouping.

Scores (``measure_association.fragments`` and below), per calibration / test half:
  fragments        truth sources (HSC i < 23) with extra single-catalogue top-level objects within 1.5'' and the number of
                   extra objects, split into: the same truth source again / another truth source / no truth source
  grouped          objects the three steps put under a parent, by role, and what they are in the truth: the parent's own
                   source ("same": a real duplicate or shred), no source within 0.6'' ("none": a spurious row) or a
                   different source ("wrong": a real neighbour absorbed, a wrong merge)
  summary rows     top-level objects as ``summary.write`` counts them
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
sys.path.insert(0, str(HERE))
import measure_association as M  # noqa: E402

GROUP_ROLES = ("ps1_duplicate", "fragment", "bright_star_halo")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def strip_grouping(out: pd.DataFrame) -> pd.DataFrame:
    """The table before the three steps: their roles removed, the SGA / identity grouping kept."""
    out = out.copy()
    role = out.component_role.fillna("").astype(str)
    drop = role.isin(GROUP_ROLES)
    out.loc[drop, "parent_object_id"] = np.nan
    out.loc[drop, "component_role"] = ""
    counts = out.parent_object_id.dropna().value_counts()
    out["n_components"] = out.object_id.map(counts).fillna(0).astype(int)
    return out


def apply_steps(out: pd.DataFrame, assoc: pd.DataFrame, hosts) -> pd.DataFrame:
    out = hosts.attach_ps1_fragments(out, assoc)
    out = hosts.attach_galaxy_fragments(out)
    out = hosts.attach_bright_star_artifacts(out)
    return out


def merge_quality(out: pd.DataFrame, truth: pd.DataFrame, before: pd.DataFrame) -> dict:
    """What the objects grouped by the three steps are in the truth."""
    role = out.component_role.fillna("").astype(str)
    new = role.isin(GROUP_ROLES)
    full = M.Sky(truth.ra, truth.dec)
    t_obj, _ = full.nearest(out.ra.to_numpy(float), out.dec.to_numpy(float), M.ID_RADIUS)
    by_id = pd.Series(np.arange(len(out)), index=out.object_id)
    res = {}
    for r in GROUP_ROLES:
        sel = np.flatnonzero((role == r).to_numpy())
        same = none = wrong = 0
        for i in sel:
            p = by_id.get(out.parent_object_id.iloc[i])
            tc, tp = t_obj[i], (t_obj[p] if p is not None else -1)
            if tc < 0:
                none += 1
            elif tc == tp:
                same += 1
            else:
                wrong += 1
        res[r] = dict(n=int(len(sel)), same=same, none=none, wrong=wrong)
    return res


def cosmos_truth_classes(truth: pd.DataFrame) -> pd.DataFrame:
    """STAR / GALAXY truth of ``score_independent_fields.truth_table`` (COSMOS2020 ACS+SED, F814W < 24.5)."""
    mu, lp, f814 = (pd.to_numeric(truth.get(c), errors="coerce") for c in ("ACSmuClass", "lptype", "ACSF814Wmag"))
    cls = np.where(mu.eq(2) & lp.eq(1), "STAR", np.where(mu.eq(1) & lp.eq(0), "GALAXY", None))
    t = truth[f814.lt(24.5) & pd.Series(cls, index=truth.index).notna() & M.inside(truth)].copy()
    t["truth"] = pd.Series(cls, index=truth.index)[t.index]
    return t


def score_accuracy(out: pd.DataFrame, truth: pd.DataFrame, lim: float = 1.5, near: float = 0.5) -> pd.DataFrame:
    """The label of every truth source as ``score_independent_fields.field_matches`` reads it: the counterpart is the
    object with the most catalogues within ``lim``'' (nearest on ties); an object grouped under a parent takes the
    parent's class.  Unmatched truth sources have no label.

    Two more readings of the same truth source that do not depend on WHICH object is picked (2.62.7, the review of 2.60.11 / 2.61.0: a rule that removes fragments
    changes which object is "the" counterpart, so the pick-one reading counts a change of the pick as a fixed or broken label):
      ``exists_near``  an object within ``near``'' (grouped objects take the class of their parent) has the truth class
      ``all_near``     at least one object within ``near``'' and every one of them has the truth class (no wrong-class competitor)
    ``n_near`` counts the objects within ``near``'' and ``classes_near`` lists their classes."""
    t = cosmos_truth_classes(truth).reset_index(drop=True)
    nc = out.catalogs.fillna("").str.count(r"\|").add(1).to_numpy()
    sky = M.Sky(out.ra.to_numpy(float), out.dec.to_numpy(float))
    host = out.set_index("object_id").primary_class
    own = out.primary_class.to_numpy(dtype=object)
    eff = np.array([host.get(p) if isinstance(p, str) and p else own[k] for k, p in enumerate(out.parent_object_id.to_numpy(dtype=object))], dtype=object)
    pred, nobj = [], []
    for ii, sep in sky.within(t.ra.to_numpy(float), t.dec.to_numpy(float), lim):
        if not len(ii):
            pred.append(None)
            nobj.append(0)
            continue
        j = ii[np.lexsort((sep, -nc[ii]))[0]]
        pred.append(eff[j])
        nobj.append(len(ii))
    t["pred"] = pred
    t["n_objects"] = nobj
    exists, every, n_near, classes = [], [], [], []
    for truth_class, (ii, _) in zip(t.truth.to_numpy(dtype=object), sky.within(t.ra.to_numpy(float), t.dec.to_numpy(float), near)):
        cls = [eff[k] for k in ii]
        n_near.append(len(cls))
        exists.append(any(c == truth_class for c in cls))
        every.append(bool(cls) and all(c == truth_class for c in cls))
        classes.append("|".join(sorted({str(c) for c in cls})))
    t["n_near"], t["exists_near"], t["all_near"], t["classes_near"] = n_near, exists, every, classes
    return t[["ra", "dec", "truth", "pred", "n_objects", "n_near", "exists_near", "all_near", "classes_near"]]


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--runs", type=Path, required=True, help="DIR/<field>/{classified_objects.csv,source_association.csv}"
    )
    ap.add_argument("--truth-flux", type=Path, required=True)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--env", nargs="*", default=[], help="KEY=VALUE set before host_groups is loaded")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    import os

    for kv in a.env:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    hosts = load_module(V2 / "host_groups.py", "v2_host_groups_regroup")
    summ = load_module(V2 / "summary.py", "v2_summary_regroup")
    split = pd.read_csv(HERE / "fields_split.csv")
    a.out.mkdir(parents=True, exist_ok=True)
    rows, merges, accs = [], [], []
    same_parent = tot = 0
    for name in split.name:
        d = a.runs / name
        out0 = pd.read_csv(d / "classified_objects.csv", low_memory=False)
        assoc = pd.read_csv(d / "source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"})
        truth = M.load_truth(
            a.truth_flux / f"{name}.csv.gz", (split.set_index("name").ra[name], split.set_index("name").dec[name])
        )
        out = apply_steps(strip_grouping(out0), assoc, hosts)
        p0, p1 = out0.parent_object_id.fillna(""), out.parent_object_id.fillna("")
        same_parent += int((p0 == p1).sum())
        tot += len(out0)
        main_rows = out[~summ.part(out) & ~summ.literature_only(out)]
        fr = M.fragments(main_rows, truth)
        fr.pop("by_catalog")
        fr["field"] = name
        fr["split"] = split.set_index("name").split[name]
        rows.append(fr)
        acc = score_accuracy(out, truth)
        acc.insert(0, "field", name)
        accs.append(acc)
        mq = merge_quality(out, truth, out0)
        for r, v in mq.items():
            merges.append(dict(field=name, split=fr["split"], role=r, **v))
        # labels of the objects the variant put under a parent: do they differ from the parent's?
        role = out.component_role.fillna("").astype(str)
        host_cls = out.set_index("object_id").primary_class
        new = role.isin(GROUP_ROLES)
        fr["grouped_label_differs"] = int(
            (out.primary_class[new].to_numpy() != out.parent_object_id[new].map(host_cls).to_numpy()).sum()
        )
        fr["grouped"] = int(new.sum())
    print(f"parent identical to the run's own grouping: {same_parent}/{tot} objects")
    A = pd.concat(accs, ignore_index=True)
    A.to_csv(a.out / f"regroup_labels_{a.variant}.csv.gz", index=False)
    A["split"] = A.field.map(split.set_index("name").split)
    got = A[A.pred.notna()]
    print(
        "truth label accuracy (STAR/GALAXY, F814W<24.5): %d truth sources, %d with an object, correct %d (%.3f %%)"
        % (len(A), len(got), int((got.pred == got.truth).sum()), 100 * (got.pred == got.truth).mean())
    )
    f = pd.DataFrame(rows)
    f.to_csv(a.out / f"regroup_fragments_{a.variant}.csv", index=False)
    m = pd.DataFrame(merges)
    m.to_csv(a.out / f"regroup_merges_{a.variant}.csv", index=False)
    cols = ["truth_sources", "truth_with_object", "truth_with_fragments", "extra_fragment_objects", "extra_same_truth",
            "extra_other_truth", "extra_no_truth", "top_level_objects", "grouped", "grouped_label_differs"]  # fmt: skip
    print(f.groupby("split")[cols].sum().T.to_string())
    print(m.groupby(["split", "role"])[["n", "same", "none", "wrong"]].sum().to_string())
    print(json.dumps({"variant": a.variant, "same_parent": same_parent, "objects": tot}))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

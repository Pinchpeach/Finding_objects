#!/usr/bin/env python3
"""Does the result depend on the order of the rows in the raw files?  (2.61.0)

    python shuffle_check.py stage1 --raw DIR --out DIR [--seeds 1 2 3] [--only CATALOG_FILE_PREFIX ...]
    python shuffle_check.py full   --raw DIR --ra RA --dec DEC --radius ARCMIN --out DIR [--seeds 1 2]
    python shuffle_check.py later  --raw DIR --ra RA --dec DEC --radius ARCMIN --out DIR [--seeds 1 2]
    python shuffle_check.py ties   --raw DIR --out DIR
    python shuffle_check.py root   --raw FIELDS_ROOT --out DIR --seeds N
    python shuffle_check.py compare --a WORK_DIR --b WORK_DIR [--out DIR]

The collectors return rows in whatever order the archive answers, and the same detections reach Stage 1 in another
order when an archive changes its answer order (a Legacy Surveys viewer answer against its TAP answer, 2.60.10).  The
checks permute the rows of the raw files (``--only`` limits it to the files whose name starts with a prefix) and compare
with the order as collected:

``stage1``  Stage 1 alone (``01_source_association.py``).  Objects are compared by their members, never by object id: a
            member is ``(input file, row of the original file)``, which the permutation maps back.  Reports per run the
            objects that exist in only one of the two runs (a different set of members), the detections whose
            association status differs, and which catalogues those detections belong to.
``full``    The whole pipeline on the permuted raw files; objects matched by their members, then the labels
            (``primary_class``, ``secondary_class``, ``high_confidence``) of the objects that exist in both.
``later``   Stages 2-7 and the grouping steps alone: the association stays as collected and the rows of every stage
            output are permuted before the next stage reads them.  Object ids are the same, so the comparison is
            row by row on ``classified_objects.csv``.
``root``    A copy of a folder of fields (``<field>/{field.json,raw/<tag>/*.csv}``, the layout of the 26 deep COSMOS
            fields) with the rows of every raw file permuted by seed N, for the pipeline and association runs
            of ``benchmark/association_truth`` (``run_full.sh``, ``run_variant.py``).
``compare`` Two finished runs (pipeline ``--work`` folders), e.g. the same sky with a Legacy Surveys table answered by TAP
            and by the viewer, where the rows have no common order: detections are matched by (catalogue, the
            catalogue's own identifier), objects by their members, then the labels as in ``full``.
``ties``    How often the row order can decide anything in Stage 1: detections that agree on every key of the sort
            order except the row (``_anchor_key`` and catalogue), per catalogue.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import zlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
SKIP_PREFIX = ("collection_summary_",)
LABELS = ["primary_class", "secondary_class", "high_confidence"]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def shuffle_raw(src: Path, dst: Path, seed: int | None, only: list[str] | None = None) -> dict[str, np.ndarray]:
    """Copy ``src`` to ``dst`` with the rows of the (selected) csv files permuted; ``{file name: perm}`` where row j of
    the new file is row ``perm[j]`` of the old one.  ``seed=None`` copies unchanged (identity)."""
    dst.mkdir(parents=True, exist_ok=True)
    perms = {}
    for p in sorted(src.iterdir()):
        if p.suffix != ".csv" or p.name.startswith(SKIP_PREFIX):
            if p.is_file():
                shutil.copy(p, dst / p.name)
            continue
        # strings only, so a value is written back exactly as it was read
        df = pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False)
        sel = seed is not None and (not only or any(p.name.startswith(o) for o in only))
        perm = np.random.default_rng([seed, zlib.crc32(p.name.encode())]).permutation(len(df)) if sel else np.arange(len(df))
        df.iloc[perm].to_csv(dst / p.name, index=False)
        perms[p.name] = perm
    return perms


def members(assoc: pd.DataFrame, perms: dict[str, np.ndarray]) -> pd.DataFrame:
    """One row per detection with its key (input file, original row) and the object it joined."""
    a = assoc.copy()
    rows = a.source_row.to_numpy(int)
    orig = np.array([perms[f][r] if f in perms else r for f, r in zip(a.input_file, rows)])
    a["key"] = list(zip(a.input_file, orig))
    return a


def compositions(a: pd.DataFrame) -> dict:
    return a.groupby("object_id").key.agg(frozenset).to_dict()


def compare_groups(ref: pd.DataFrame, new: pd.DataFrame) -> dict:
    """Objects compared by their members."""
    cr, cn = compositions(ref), compositions(new)
    sr, sn = set(cr.values()), set(cn.values())
    only_r, only_n = sr - sn, sn - sr
    det_diff = {k for c in only_r | only_n for k in c}
    st_r, st_n = ref.set_index("key").association_status, new.set_index("key").association_status
    common = st_r.index.intersection(st_n.index)
    status_diff = int((st_r.loc[common] != st_n.loc[common]).sum())
    cat = ref.set_index("key").catalog
    by_cat = pd.Series([cat.get(k, "?") for k in det_diff]).value_counts().to_dict()
    return dict(
        detections=len(ref),
        objects_ref=len(cr),
        objects_new=len(cn),
        objects_only_ref=len(only_r),
        objects_only_new=len(only_n),
        detections_in_changed_objects=len(det_diff),
        status_changed=status_diff,
        by_catalog=json.dumps(by_cat, sort_keys=True),
    )


def run_stage1(raw: Path, out: Path):
    s1 = load_module(V2 / "Preprocess" / "01_source_association.py", "v2_stage1_shuffle")
    out.parent.mkdir(parents=True, exist_ok=True)
    s1.run(raw, out)
    return pd.read_csv(out, low_memory=False, dtype={"catalog_object_id": "string"})


def cmd_stage1(a) -> int:
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    base_raw = out / "raw_ref"
    shuffle_raw(a.raw, base_raw, None)
    ref = members(run_stage1(base_raw, out / "ref.csv"), {})
    rows = []
    for seed in a.seeds:
        raw = out / f"raw_s{seed}"
        perms = shuffle_raw(a.raw, raw, seed, a.only)
        new = members(run_stage1(raw, out / f"s{seed}.csv"), perms)
        r = compare_groups(ref, new)
        r.update(seed=seed, only=" ".join(a.only or []) or "all")
        rows.append(r)
        print(r, flush=True)
        shutil.rmtree(raw)
    shutil.rmtree(base_raw)
    pd.DataFrame(rows).to_csv(out / "stage1_summary.csv", index=False)
    return 0


def run_pipeline(raw: Path, work: Path, ra: float, dec: float, radius: float):
    subprocess.run(
        [sys.executable, str(V2 / "pipeline.py"), "--work", str(work), "--raw-dir", str(raw), "--ra", str(ra),
         "--dec", str(dec), "--radius", str(radius)],
        check=True, stdout=subprocess.DEVNULL, env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
    )  # fmt: skip


def _s(x):
    """Values as text with a missing value as the empty string (NaN != NaN would count every empty cell)."""
    return x.astype(object).where(x.notna(), "").astype(str).to_numpy()


def label_diff(ref_c: pd.DataFrame, new_c: pd.DataFrame, ref_a, new_a) -> dict:
    """Labels of the objects that exist (same members) in both runs."""
    mr = {frozenset(v): k for k, v in compositions(ref_a).items()}
    mn = {frozenset(v): k for k, v in compositions(new_a).items()}
    common = [c for c in mr if c in mn]
    r = ref_c.set_index("object_id")
    n = new_c.set_index("object_id")
    idr = [mr[c] for c in common]
    idn = [mn[c] for c in common]
    out = dict(objects_common=len(common))
    for col in LABELS:
        if col in r and col in n:
            x = _s(r.loc[idr, col])
            y = _s(n.loc[idn, col])
            out[f"{col}_changed"] = int((x != y).sum())
    return out


def cmd_full(a) -> int:
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    base_raw = out / "raw_ref"
    shuffle_raw(a.raw, base_raw, None)
    run_pipeline(base_raw, out / "ref", a.ra, a.dec, a.radius)
    ref_a = members(pd.read_csv(out / "ref" / "source_association.csv", low_memory=False), {})
    ref_c = pd.read_csv(out / "ref" / "classified_objects.csv", low_memory=False)
    rows = []
    for seed in a.seeds:
        raw = out / f"raw_s{seed}"
        perms = shuffle_raw(a.raw, raw, seed, a.only)
        run_pipeline(raw, out / f"s{seed}", a.ra, a.dec, a.radius)
        new_a = members(pd.read_csv(out / f"s{seed}" / "source_association.csv", low_memory=False), perms)
        new_c = pd.read_csv(out / f"s{seed}" / "classified_objects.csv", low_memory=False)
        r = compare_groups(ref_a, new_a)
        r.update(label_diff(ref_c, new_c, ref_a, new_a))
        r.update(seed=seed, only=" ".join(a.only or []) or "all")
        rows.append(r)
        print(r, flush=True)
        shutil.rmtree(raw)
        if not a.keep:
            shutil.rmtree(out / f"s{seed}")
    shutil.rmtree(base_raw)
    pd.DataFrame(rows).to_csv(out / "full_summary.csv", index=False)
    return 0


def cmd_later(a) -> int:
    """Stages 2-7 and grouping on stage outputs whose rows are permuted before the next stage."""
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    base_raw = out / "raw_ref"
    shuffle_raw(a.raw, base_raw, None)
    P = load_module(V2 / "pipeline.py", "v2_pipeline_shuffle")
    s1 = load_module(V2 / "Preprocess" / "01_source_association.py", "v2_stage1_later")
    # the same Stage 1 output for every run: the association stays as collected
    ref_assoc = out / "source_association_ref.csv"
    s1.run(base_raw, ref_assoc)
    orig_load = P._load
    state = {}

    def patched(path, name):
        mod = orig_load(path, name)
        if not hasattr(mod, "run") or "01_source_association" in str(path) or "high_confidence" in str(path):
            return mod
        real = mod.run

        def wrapped(*args, **kw):
            work = state["work"]
            before = {p: p.stat().st_mtime_ns for p in work.glob("*.csv")}
            res = real(*args, **kw)
            rng = np.random.default_rng(state["seed"])
            for p in work.glob("*.csv"):
                if p.name == "source_association.csv" or (p in before and p.stat().st_mtime_ns == before[p]):
                    continue
                df = pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False)
                df.iloc[rng.permutation(len(df))].to_csv(p, index=False)
            return res

        mod.run = wrapped
        return mod

    P._load = patched
    rows = []
    for seed in [None, *a.seeds]:
        work = out / ("ref" if seed is None else f"s{seed}")
        work.mkdir(parents=True, exist_ok=True)
        shutil.copy(ref_assoc, work / "source_association.csv")
        if seed is not None:  # the association is the same, its rows come in another order
            d = pd.read_csv(ref_assoc, dtype=str, keep_default_na=False, low_memory=False)
            d.iloc[np.random.default_rng(seed).permutation(len(d))].to_csv(work / "source_association.csv", index=False)
        state.update(work=work, seed=seed)
        if seed is None:  # reference: no permutation
            P._load = orig_load
        else:
            P._load = patched
        # Stage 1 is skipped by pointing it at the stored association
        s1_run = s1.run
        s1.run = lambda raw, o: None
        try:
            P.run(work, raw_dir=base_raw, ra=a.ra, dec=a.dec, radius=a.radius)
        finally:
            s1.run = s1_run
        if seed is not None:
            r = later_diff(pd.read_csv(out / "ref" / "classified_objects.csv", low_memory=False),
                           pd.read_csv(work / "classified_objects.csv", low_memory=False))  # fmt: skip
            r.update(seed=seed)
            rows.append(r)
            print(r, flush=True)
    pd.DataFrame(rows).to_csv(out / "later_summary.csv", index=False)
    return 0


def later_diff(ref: pd.DataFrame, new: pd.DataFrame) -> dict:
    r, n = ref.set_index("object_id"), new.set_index("object_id")
    common = r.index.intersection(n.index)
    out = dict(objects_ref=len(r), objects_new=len(n), objects_common=len(common))
    cols = [c for c in r.columns if c in n.columns and c != "object_id"]
    changed = {}
    for c in cols:
        x, y = _s(r.loc[common, c]), _s(n.loc[common, c])
        k = int((x != y).sum())
        if k:
            changed[c] = k
    out["columns_changed"] = json.dumps(dict(sorted(changed.items(), key=lambda kv: -kv[1])[:12]))
    for col in LABELS + ["parent_object_id", "component_role"]:
        if col in r and col in n:
            out[f"{col}_changed"] = int((_s(r.loc[common, col]) != _s(n.loc[common, col])).sum())
    return out


def cmd_compare(a) -> int:
    def load_run(d: Path):
        assoc = pd.read_csv(d / "source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"})
        assoc["key"] = list(zip(assoc.catalog, assoc.catalog_object_id))
        return assoc, pd.read_csv(d / "classified_objects.csv", low_memory=False)

    ra, rc = load_run(a.a)
    na, nc = load_run(a.b)
    r = compare_groups(ra, na)
    r.update(label_diff(rc, nc, ra, na))
    print(r)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([r]).to_csv(a.out / "compare_summary.csv", index=False)
    return 0


def cmd_root(a) -> int:
    seed = a.seeds[0]
    for fdir in sorted(p for p in a.raw.iterdir() if (p / "field.json").exists()):
        dst = a.out / fdir.name
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(fdir / "field.json", dst / "field.json")
        for tag in sorted((fdir / "raw").iterdir()):
            shuffle_raw(tag, dst / "raw" / tag.name, seed)
    return 0


def cmd_ties(a) -> int:
    s1 = load_module(V2 / "Preprocess" / "01_source_association.py", "v2_stage1_ties")
    dets, _ = s1.load(a.raw)
    df = pd.DataFrame(
        dict(
            catalog=[d["catalog"] for d in dets],
            ann=[d["catalog"] in s1.ANNOTATION_CATALOGS for d in dets],
            tgt=[d["catalog"] in s1.TARGET_SPECTRA for d in dets],
            key=[s1._anchor_key(d) for d in dets],
        )
    )
    df["tie_group"] = df.groupby(["ann", "tgt", "key", "catalog"]).catalog.transform("size")
    g = df.groupby("catalog").agg(rows=("catalog", "size"), tied_rows=("tie_group", lambda s: int((s > 1).sum())),
                                  largest_tie=("tie_group", "max"))  # fmt: skip
    g["tied_share"] = (g.tied_rows / g.rows).round(3)
    g.sort_values("tied_rows", ascending=False).to_csv(a.out / "ties.csv") if a.out else None
    print(g.sort_values("tied_rows", ascending=False).to_string())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["stage1", "full", "later", "ties", "root", "compare"])
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--a", type=Path)
    ap.add_argument("--b", type=Path)
    ap.add_argument("--seeds", type=int, nargs="*", default=[1, 2, 3])
    ap.add_argument("--only", nargs="*", default=None, help="shuffle only files whose name starts with one of these")
    ap.add_argument("--ra", type=float)
    ap.add_argument("--dec", type=float)
    ap.add_argument("--radius", type=float, help="arcmin")
    ap.add_argument("--keep", action="store_true", help="keep the pipeline folders of the shuffled runs")
    ap.add_argument("--v2", type=Path, default=None, help="the v2 folder whose code is run (default: this checkout)")
    a = ap.parse_args()
    if a.v2:
        global V2
        V2 = a.v2.resolve()
    if a.out and a.mode != "compare":
        a.out.mkdir(parents=True, exist_ok=True)
    return {"stage1": cmd_stage1, "full": cmd_full, "later": cmd_later, "ties": cmd_ties, "root": cmd_root, "compare": cmd_compare}[a.mode](a)


if __name__ == "__main__":
    raise SystemExit(main())

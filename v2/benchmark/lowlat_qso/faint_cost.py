#!/usr/bin/env python3
"""What the low-latitude QSO switches cost faint real quasars: the 26 deep COSMOS fields with the latitude limit lifted (2.61.5).

    python faint_cost.py classify --deep DIR --fields-file fields_all26.csv --variants base,surveys2,surveys3,wise_second [--jobs 2]
    python faint_cost.py tables   --deep DIR --fields-file fields_all26.csv --variants base,surveys2,surveys3,wise_second --out OUT

``classify`` runs the pipeline on the stored blind raw files of each field (``benchmark/faint_qso_candidates.py`` layout:
``DIR/<field>/raw/<tag>``, ``DIR/<field>/truth``) with ``V2_LOWLAT_QSO=<variant>`` and ``V2_LOWLAT_QSO_ABSB=90`` (the switches act
at every latitude: COSMOS is at |b| = 42 deg, where they are off by default), keeps the columns this study needs
(``DIR/run_<variant>/<field>/classified_objects.csv``, a slim copy: the full tables of 26 fields are tens of GB) and removes the work
folder.  ``tables`` matches the truth objects of ``faint_qso_candidates.truth_table`` (Chandra COSMOS Legacy type 1 = ``TYPE1``, of
which ``spec`` marks the spectroscopically classified ones; COSMOS2020 ACS galaxies and stars; Chandra type 2) to the objects of every variant
and writes, against the first variant (``base``), by LS r bin and by the number of surveys of the object (``lowlat_qso.n_surveys``):

  type1_loss_by_r.csv         type 1 AGN labelled QSO by the base and by the variant, the ones lost, with Wilson 95 %
  type1_loss_by_surveys.csv   the same by number of surveys of the object
  type1_r_by_surveys.csv      type 1 AGN of the base: r bin x number of surveys, and how many of them the base labels QSO
  type1_ceiling_by_r.csv      the share of the type 1 AGN with at least 2 / 3 surveys at all, with and without Legacy Surveys (+ SGA-2020)
  type1_ps1_i_by_surveys.csv  the same on the Pan-STARRS1 i axis (the axis of the low-latitude regions; ``no PS1``: no PS1 magnitude)
  false_removed.csv           truth stars, galaxies and type 2 AGN that the base labels QSO and the variant does not
  claims.csv                  the claims a reader takes as "quasar" at 22 <= r < 24 (label QSO, label QSO or flagged candidate,
                              label QSO or any QSO reading including the held-back one): purity and recall of type 1
  qso_labels_all_objects.csv  QSO labels of every object by r bin, base against variant

Truth: Chandra type 1 misses non-X-ray quasars, so "false" claims are a lower bound of the contamination (as in faint_qso_candidates).
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
sys.path.insert(0, str(V2 / "benchmark"))
import faint_qso_candidates as FQ  # noqa: E402

_spec = importlib.util.spec_from_file_location("lowlat_qso_cost", V2 / "Preprocess" / "lowlat_qso.py")
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)

KEEP = [*FQ.COLS, "catalogs", "lowlat_qso_hold", "std_mag__ps1_i"]
FQ.COLS = tuple(dict.fromkeys(KEEP))  # matched() reads these
R_BINS = [(-np.inf, 20.0), (20.0, 21.0), (21.0, 22.0), (22.0, 23.0), (23.0, 24.0), (24.0, np.inf)]
N_BINS = [(1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 99, "4+")]
ENV = {  # variant -> environment
    "base": {},
    "surveys2": {"V2_LOWLAT_QSO": "surveys2"},
    "surveys3": {"V2_LOWLAT_QSO": "surveys3"},
    "wise_second": {"V2_LOWLAT_QSO": "wise_second"},
    "surveys2_wise_second": {"V2_LOWLAT_QSO": "surveys2,wise_second"},
    # 2.62.2: the survey-count switches on top of the association rules of 2.61.8 (V2_ASSOC_AMBIG=same,nearest), see decision_table.py.
    # V2_POSERR_UNITS=legacy: the base runs of this table were made before the unit fix of the position errors (2.62.2); the combinations
    # are measured against them with the same reading of the VLASS / NVSS errors, so the only difference is the switches under study.
    "same_nearest": {"V2_ASSOC_AMBIG": "same,nearest", "V2_POSERR_UNITS": "legacy"},
    "same_nearest_surveys2": {"V2_ASSOC_AMBIG": "same,nearest", "V2_LOWLAT_QSO": "surveys2", "V2_POSERR_UNITS": "legacy"},
    "same_nearest_surveys3": {"V2_ASSOC_AMBIG": "same,nearest", "V2_LOWLAT_QSO": "surveys3", "V2_POSERR_UNITS": "legacy"},
    # 2.62.7: the three switches together (the order of 2026-11-28, task b): the fixed units, the association rules and the survey-count switch; fixed had not been
    # measured together with the other two
    "fixed_same_nearest_surveys2": {"V2_POSERR_UNITS": "fixed", "V2_ASSOC_AMBIG": "same,nearest", "V2_LOWLAT_QSO": "surveys2"},
}
LIMIT_OFF = {"V2_LOWLAT_QSO_ABSB": "90"}  # the switches act at every latitude


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def wilson(k, n):
    return FQ.wilson(k, n)


def rname(lo, hi) -> str:
    return f"{'<' if lo == -np.inf else ''}{'' if lo == -np.inf else f'{lo:g}-'}{hi:g}" if hi != np.inf else f">={lo:g}"


def variant_env(v: str) -> dict:
    """The environment the pipelines of variant ``v`` run in (the V2_* variables of the caller's shell are dropped except the cache ones)."""
    env = {k: x for k, x in os.environ.items() if not k.startswith("V2_") or k in ("V2_CACHE", "V2_CACHE_DIR")}
    env.update({"PYTHONHASHSEED": "0", "V2_CACHE": "0"})
    env.update(ENV[v])
    if v != "base":
        env.update(LIMIT_OFF)
    return env


def classify(deep: Path, fields_file: Path, variants: list[str], jobs: int, work_root: Path) -> None:
    fields = FQ.load_fields(fields_file)
    t0 = RI.start()
    for v in variants:  # run_info.json per variant: the environment the pipelines of that directory run in, and what the code reads in it
        RI.write(deep / f"run_{v}", [fields_file], t0=t0, status="running", env=variant_env(v), replace_env=True, note=f"faint_cost classify, variant {v}")

    def one(args):
        v, f = args
        ra, dec = fields[f]
        out = deep / f"run_{v}" / f / "classified_objects.csv"
        if out.exists():
            return
        work = work_root / v / f
        shutil.rmtree(work, ignore_errors=True)
        env = variant_env(v)
        cmd = [sys.executable, str(V2 / "pipeline.py"), "--raw-dir", str(FQ.raw_dir(deep, f)), "--ra", str(ra), "--dec", str(dec),
               "--radius", str(FQ.RADIUS_ARCMIN), "--work", str(work)]  # fmt: skip
        subprocess.run(cmd, env=env, check=True, timeout=3600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        d = pd.read_csv(work / "classified_objects.csv", low_memory=False, usecols=lambda c: c in set(KEEP))
        out.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(out, index=False)
        shutil.rmtree(work, ignore_errors=True)
        print(f"[{v}] {f}: {len(d)} objects", flush=True)

    try:
        with ThreadPoolExecutor(max(1, jobs)) as ex:
            list(ex.map(one, [(v, f) for v in variants for f in fields]))
    except BaseException:
        for v in variants:
            RI.write(deep / f"run_{v}", [fields_file], t0=t0, status="failed", env=variant_env(v), replace_env=True, note=f"faint_cost classify, variant {v}")
        raise
    for v in variants:
        RI.write(deep / f"run_{v}", [fields_file], t0=t0, status="ok", env=variant_env(v), replace_env=True, note=f"faint_cost classify, variant {v}")


def load(deep: Path, variant: str) -> pd.DataFrame:
    m = FQ.matched(deep, variant)
    m["n_surveys"] = LL.n_surveys(m.o_catalogs) if "o_catalogs" in m else 0
    return m


def rbin(x: pd.DataFrame, lo, hi, col="o_std_mag__ls_r") -> pd.DataFrame:
    return x[(x[col] >= lo) & (x[col] < hi)]


def tables(deep: Path, fields_file: Path, variants: list[str], out: Path) -> None:
    FQ.FIELDS = FQ.load_fields(fields_file)
    out.mkdir(parents=True, exist_ok=True)
    key = ["field", "ra", "dec", "truth"]
    base = load(deep, variants[0])
    loss_r, loss_n, fp, claims, alls, cross = [], [], [], [], [], []
    for v in variants[1:]:
        mv = load(deep, v)
        m = base.merge(mv, on=key, suffixes=("_b", "_v"))
        t1 = m[m.truth == "TYPE1"]
        for sub, name in ((t1, "type1"), (t1[t1.spec_b == True], "type1_spectroscopic")):  # noqa: E712
            for lo, hi in [*R_BINS, (-np.inf, np.inf)]:
                x = rbin(sub, lo, hi, "o_std_mag__ls_r_b") if (lo, hi) != (-np.inf, np.inf) else sub
                qb = int((x.o_primary_class_b == "QSO").sum())
                qv = int((x.o_primary_class_v == "QSO").sum())
                lost = int(((x.o_primary_class_b == "QSO") & (x.o_primary_class_v != "QSO")).sum())
                lo_w, hi_w = wilson(lost, qb) if qb else (math.nan, math.nan)
                loss_r.append(dict(variant=v, truth=name, r="all" if (lo, hi) == (-np.inf, np.inf) else rname(lo, hi), n=len(x),
                                   qso_base=qb, qso_variant=qv, lost=lost, lost_frac=round(lost / qb, 4) if qb else math.nan,
                                   lost_lo=round(lo_w, 4), lost_hi=round(hi_w, 4),
                                   recall_base=round(qb / len(x), 4) if len(x) else math.nan,
                                   recall_variant=round(qv / len(x), 4) if len(x) else math.nan))  # fmt: skip
        for lo_n, hi_n, nm in N_BINS:
            x = t1[(t1.n_surveys_b >= lo_n) & (t1.n_surveys_b <= hi_n)]
            qb = int((x.o_primary_class_b == "QSO").sum())
            lost = int(((x.o_primary_class_b == "QSO") & (x.o_primary_class_v != "QSO")).sum())
            lo_w, hi_w = wilson(lost, qb) if qb else (math.nan, math.nan)
            loss_n.append(dict(variant=v, surveys=nm, n_type1=len(x), qso_base=qb, lost=lost, lost_frac=round(lost / qb, 4) if qb else math.nan,
                               lost_lo=round(lo_w, 4), lost_hi=round(hi_w, 4)))  # fmt: skip
        for tr in ("STAR", "GALAXY", "TYPE2"):
            for lo, hi in [*R_BINS, (-np.inf, np.inf)]:
                s = m[m.truth == tr]
                x = rbin(s, lo, hi, "o_std_mag__ls_r_b") if (lo, hi) != (-np.inf, np.inf) else s
                fp.append(dict(variant=v, truth=tr, r="all" if (lo, hi) == (-np.inf, np.inf) else rname(lo, hi), n=len(x),
                               qso_base=int((x.o_primary_class_b == "QSO").sum()), qso_variant=int((x.o_primary_class_v == "QSO").sum()),
                               removed=int(((x.o_primary_class_b == "QSO") & (x.o_primary_class_v != "QSO")).sum())))  # fmt: skip
    # type 1 AGN of the base by r and survey count, and how many the base labels QSO
    t1 = base[base.truth == "TYPE1"]
    for lo, hi in R_BINS:
        x = rbin(t1, lo, hi)
        for lo_n, hi_n, nm in N_BINS:
            y = x[(x.n_surveys >= lo_n) & (x.n_surveys <= hi_n)]
            cross.append(dict(r=rname(lo, hi), surveys=nm, n_type1=len(y), base_labels_qso=int((y.o_primary_class == "QSO").sum())))
    # the ceiling: the share of the type 1 AGN that has at least 2 / 3 surveys at all, with and without Legacy Surveys (most of the
    # plane has no Legacy Surveys coverage: SGA-2020 is built from its imaging, so it goes too)
    def without_ls(cats: pd.Series) -> np.ndarray:
        drop = {"DESI Legacy Surveys DR10", "SGA-2020"}
        return LL.n_surveys(cats.fillna("").map(lambda c: "|".join(x for x in c.split("|") if x not in drop)))

    t1c = t1.assign(n_no_ls=without_ls(t1.o_catalogs))
    ceiling = []
    for lo, hi in [*R_BINS, (-np.inf, np.inf)]:
        x = rbin(t1c, lo, hi) if (lo, hi) != (-np.inf, np.inf) else t1c
        if not len(x):
            continue
        ceiling.append(dict(r="all" if (lo, hi) == (-np.inf, np.inf) else rname(lo, hi), n_type1=len(x),
                            ge2=round(float((x.n_surveys >= 2).mean()), 4), ge3=round(float((x.n_surveys >= 3).mean()), 4),
                            ge2_without_ls=round(float((x.n_no_ls >= 2).mean()), 4), ge3_without_ls=round(float((x.n_no_ls >= 3).mean()), 4),
                            base_labels_qso=int((x.o_primary_class == "QSO").sum())))  # fmt: skip
    # the same on the Pan-STARRS1 i axis the low-latitude regions are binned on (PS1 covers both: r of Legacy Surveys does not)
    I_BINS = [(-np.inf, 19.0), (19.0, 20.0), (20.0, 21.0), (21.0, 22.0), (22.0, np.inf)]
    cross_i = []
    for lo, hi in [*I_BINS, (None, None)]:
        x = t1[t1.o_std_mag__ps1_i.isna()] if lo is None else t1[(t1.o_std_mag__ps1_i >= lo) & (t1.o_std_mag__ps1_i < hi)]
        for lo_n, hi_n, nm in N_BINS:
            y = x[(x.n_surveys >= lo_n) & (x.n_surveys <= hi_n)]
            cross_i.append(dict(ps1_i="no PS1" if lo is None else rname(lo, hi), surveys=nm, n_type1=len(y),
                                base_labels_qso=int((y.o_primary_class == "QSO").sum())))  # fmt: skip
    # the claims at 22-24 and over all r
    for v in variants:
        mv = load(deep, v)
        for lo, hi, name in ((22.0, 24.0, "22-24"), (-np.inf, np.inf, "all")):
            s = mv if name == "all" else rbin(mv, lo, hi)
            n1 = int((s.truth == "TYPE1").sum())
            lab = s.o_primary_class == "QSO"
            cand = (~lab) & (s.o_secondary_class == "QSO") & (s.o_secondary_class_reason == FQ_CAND)
            held = (~lab) & (s.o_secondary_class == "QSO") & (s.o_secondary_class_reason == "LOWLAT_QSO_HELD")
            for cname, claim in (("label QSO", lab), ("label QSO or candidate", lab | cand), ("label QSO or candidate or held", lab | cand | held)):
                tp = int((claim & (s.truth == "TYPE1")).sum())
                nn = int(claim.sum())
                claims.append(dict(variant=v, r=name, claim=cname, n_type1=n1, claims=nn, type1_among_claims=tp,
                                   purity=round(tp / nn, 4) if nn else math.nan, recall=round(tp / n1, 4) if n1 else math.nan))  # fmt: skip
    # every object of the fields: QSO labels by r bin
    runs = {}
    for v in variants:
        parts = []
        for f in FQ.FIELDS:
            p = deep / f"run_{v}" / f / "classified_objects.csv"
            if p.exists():
                d = pd.read_csv(p, low_memory=False, usecols=["object_id", "primary_class", "std_mag__ls_r", "parent_object_id"])
                d = d[d.parent_object_id.isna()]
                d["field"] = f
                parts.append(d)
        runs[v] = pd.concat(parts)
    for v in variants:
        for lo, hi in R_BINS:
            x = runs[v][(runs[v].std_mag__ls_r >= lo) & (runs[v].std_mag__ls_r < hi)]
            alls.append(dict(variant=v, r=rname(lo, hi), objects=len(x), qso_labels=int((x.primary_class == "QSO").sum())))
    for name, rows in (("type1_loss_by_r", loss_r), ("type1_loss_by_surveys", loss_n), ("false_removed", fp), ("claims", claims),
                       ("qso_labels_all_objects", alls), ("type1_r_by_surveys", cross), ("type1_ps1_i_by_surveys", cross_i), ("type1_ceiling_by_r", ceiling)):  # fmt: skip
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        for name, rows in (("type1_loss_by_r", loss_r), ("type1_loss_by_surveys", loss_n), ("claims", claims)):
            print("==", name)
            print(pd.DataFrame(rows).to_string(index=False))


FQ_CAND = "FAINT_QSO_CANDIDATE"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["classify", "tables"])
    ap.add_argument("--deep", type=Path, required=True)
    ap.add_argument("--fields-file", type=Path, required=True)
    ap.add_argument("--variants", default="base,surveys2,surveys3,wise_second")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--work", type=Path, default=Path("/tmp/faint_cost_work"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    t0 = RI.start()
    variants = a.variants.split(",")
    bad = [v for v in variants if v not in ENV]
    if bad:
        raise SystemExit(f"unknown variant {bad}; known: {list(ENV)}")
    if a.cmd == "classify":
        classify(a.deep, a.fields_file, variants, a.jobs, a.work)
    else:
        if not a.out:
            raise SystemExit("--out is needed for tables")
        tables(a.deep, a.fields_file, variants, a.out)
        RI.write_args(a, ("deep", "fields_file"), t0=t0, note="faint_cost tables of " + ",".join(variants))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

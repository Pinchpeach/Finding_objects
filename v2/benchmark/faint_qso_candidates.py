#!/usr/bin/env python3
"""Faint (r 22-24) type-1 AGN: label, candidate flag and prior variants on the deep COSMOS fields (2.57.0).

Truth (as in measure_cosmos_xray_agn.py and score_independent_fields.py):
  TYPE1  Chandra COSMOS Legacy (Marchesi et al. 2016) broad-line / unobscured AGN
  TYPE2  the same catalogue's obscured AGN and galaxies (host-dominated, expected GALAXY)
  GALAXY COSMOS2020 (Weaver et al. 2022) HST/ACS galaxies: ACSmuClass 1 and lptype 0, F814W < 24.5
  STAR   COSMOS2020 ACSmuClass 2 and lptype 1, F814W < 24.5
Chandra AGN are left out of the COSMOS2020 classes (lptype 2), so the classes do not overlap.

Fields and split: the nine deep_cosmos fields of experiment-ab-fields.yml; odd-numbered fields
calibrate, even-numbered test (prior_layer_study.split, fixed in 2.52.0).  Everything a rule or a
table is fitted on comes from the calibration fields; every reported number is the test fields.

    python v2/benchmark/faint_qso_candidates.py classify --deep DIR --variant NAME [--env K=V ...]
    python v2/benchmark/faint_qso_candidates.py tables   --deep DIR --variants base,qa --out OUT

``classify`` runs the pipeline on DIR/<field>/raw/<tag> (blind raw files, collect_deep_cosmos.py) with the
variant's environment and writes DIR/run_<variant>/<field>/; ``tables`` reads those runs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
V2 = B.parent
sys.path.insert(0, str(B))
import measure_cosmos_xray_agn as X  # noqa: E402  (FIELDS, truth_type, wilson, sep_arcsec, R_BINS, ...)

FIELDS = X.FIELDS
RADIUS_ARCMIN, EDGE_ARCMIN, MATCH_ARCSEC = X.RADIUS_ARCMIN, X.EDGE_ARCMIN, X.MATCH_ARCSEC
R_BINS = [(22.0, 23.0), (23.0, 24.0)]  # the range this study is about; r >= 24 is not touched
ALL_BINS = [(-np.inf, 21.0), (21.0, 22.0), (22.0, 23.0), (23.0, 24.0), (24.0, np.inf)]
THRESHOLDS = (0.02, 0.05, 0.1, 0.2, 0.3, 0.5)
CAND_R_MIN, CAND_R_MAX = 22.0, 24.0
COSMOS2020 = "J_ApJS_258_11_classic.csv.gz"


def split_of(field: str) -> str:
    return "cal" if int(field.rsplit("_", 1)[1]) % 2 else "test"


def raw_dir(deep: Path, field: str) -> Path:
    d = sorted((deep / field / "raw").glob("ra*"))
    if not d:
        raise FileNotFoundError(f"no raw folder in {deep / field}")
    return d[0]


# ------------------------------------------------------------------ classify
def classify(deep: Path, variant: str, env: dict, fields: list[str], jobs: int = 1, timeout: int = 3600) -> None:
    """Run the pipeline on the blind raw files of each field with the variant's environment (``jobs`` at a time)."""
    from concurrent.futures import ThreadPoolExecutor

    def one(f: str) -> None:
        ra, dec = FIELDS[f]
        work = deep / f"run_{variant}" / f
        if (work / "classified_objects.csv").exists():
            print(f"[{variant}] {f}: done", flush=True)
            return
        e = {k: v for k, v in os.environ.items() if not k.startswith("V2_") or k in ("V2_CACHE", "V2_CACHE_DIR")}
        e.update(env)
        cmd = [
            sys.executable,
            str(V2 / "pipeline.py"),
            "--raw-dir",
            str(raw_dir(deep, f)),
            "--ra",
            str(ra),
            "--dec",
            str(dec),
            "--radius",
            str(RADIUS_ARCMIN),
            "--work",
            str(work),
        ]
        print(f"[{variant}] {f}: {' '.join(f'{k}={v}' for k, v in env.items()) or 'defaults'}", flush=True)
        subprocess.run(cmd, env=e, check=True, timeout=timeout, stdout=subprocess.DEVNULL)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(one, fields))


# ---------------------------------------------- COSMOS2020 accuracy / calibration (2.52.0 method)
def layout(deep: Path, variants: list[str]) -> Path:
    """DIR/ab/<variant>/<field>/{field.json, truth/, objects_blind.csv.gz, objects_blind_evidence.csv.gz}: what
    compare_ab_fields.py reads (written like .github/workflows/experiment-ab-fields.yml does)."""
    import importlib.util
    import shutil

    spec = importlib.util.spec_from_file_location(
        "deep_truth_script", V2.parent / ".github" / "scripts" / "independent_truth_field.py"
    )
    sys.path.insert(0, str(V2 / "Get_data"))
    tf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tf)
    for v in variants:
        for f, (ra, dec) in FIELDS.items():
            work, out = deep / f"run_{v}" / f, deep / "ab" / v / f
            if not (work / "classified_objects.csv").exists() or (out / "objects_blind.csv.gz").exists():
                continue
            out.mkdir(parents=True, exist_ok=True)
            shutil.copytree(deep / f / "truth", out / "truth", dirs_exist_ok=True)
            (out / "field.json").write_text(json.dumps({"ra": ra, "dec": dec, "radius_arcmin": RADIUS_ARCMIN}))
            tf.compact(work, ra, dec, RADIUS_ARCMIN, out, "objects_blind")
    return deep / "ab"


def accuracy_tables(deep: Path, variants: list[str], out: Path, nboot: int = 1000) -> pd.DataFrame:
    """Paired accuracy (McNemar against ``base``), ECE and NLL of the final probabilities on the test fields,
    and the accuracy by LS r bin; the odd fields only calibrate (prior_layer_study.split)."""
    import prior_layer_study as PLS

    layout(deep, variants)
    ab_out = deep / "ab_out"
    subprocess.run(
        [
            sys.executable,
            str(B / "compare_ab_fields.py"),
            str(deep / "ab"),
            "--out",
            str(ab_out),
            "--base",
            "base",
            "--nboot",
            str(nboot),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    rows = []
    base = None
    for v in variants:
        t = pd.read_csv(ab_out / f"truth_probs_{v}.csv.gz", low_memory=False)
        t["split"] = split_of_series(t.field)
        for split in ("cal", "test"):
            x = t[
                (t.split == split)
                & t.t_truth.isin(["STAR", "GALAXY", "QSO"])
                & t[["p_star", "p_galaxy", "p_qso"]].notna().all(axis=1)
            ]
            P = x[["p_star", "p_galaxy", "p_qso"]].to_numpy(float)
            y = x.t_truth.map({"STAR": 0, "GALAXY": 1, "QSO": 2}).to_numpy()
            ok = x.ours == x.t_truth
            rows.append(
                {
                    "variant": v,
                    "split": split,
                    "n": len(x),
                    "acc": round(100 * float(ok.mean()), 3),
                    "ece": round(100 * PLS.ece(P, y), 3),
                    "classwise_ece": round(100 * PLS.classwise_ece(P, y), 3),
                    "nll": round(float(-np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1)).mean()), 4),
                }
            )
    res = pd.DataFrame(rows)
    res.to_csv(out / "accuracy_ece.csv", index=False)
    return res


def split_of_series(fields: pd.Series) -> pd.Series:
    return fields.map(split_of)


# --------------------------------------------------------------------- truth
def truth_table(deep: Path, field: str) -> pd.DataFrame:
    """Truth objects of one field inside the edge cut: columns ra, dec, truth, spec."""
    ra0, de0 = FIELDS[field]
    rows = []
    c = pd.read_csv(X.TRUTH)
    c["ra"], c["dec"] = c.RAOdeg.fillna(c.RAJ2000), c.DEOdeg.fillna(c.DEJ2000)
    c["truth"] = X.truth_type(c).map({"TYPE1": "TYPE1", "TYPE2": "TYPE2", "STAR": "STAR"})
    c["spec"] = c.Clsp.isin([0, 1, 2])
    rows.append(c[["ra", "dec", "truth", "spec"]].dropna(subset=["truth"]))
    p = deep / field / "truth" / COSMOS2020
    if p.exists():
        d = pd.read_csv(p, low_memory=False)
        num = lambda k: pd.to_numeric(d[k], errors="coerce")
        mu, lp, f814 = num("ACSmuClass"), num("lptype"), num("ACSF814Wmag")
        ok = f814.lt(24.5)
        cls = np.where(mu.eq(2) & lp.eq(1), "STAR", np.where(mu.eq(1) & lp.eq(0), "GALAXY", None))
        t = pd.DataFrame({"ra": num("_RAJ2000"), "dec": num("_DEJ2000"), "truth": cls, "spec": False})[ok]
        rows.append(t.dropna(subset=["truth", "ra", "dec"]))
    t = pd.concat(rows, ignore_index=True)
    t = t[X.sep_arcsec(ra0, de0, t.ra.to_numpy(), t.dec.to_numpy()) <= (RADIUS_ARCMIN - EDGE_ARCMIN) * 60].reset_index(
        drop=True
    )
    # a COSMOS2020 star / galaxy within 1" of a Chandra source is that source
    ch = t[t.truth.isin(["TYPE1", "TYPE2"])]
    if len(ch):
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        other = t.truth.isin(["STAR", "GALAXY"]).to_numpy()
        _, sep, _ = SkyCoord(t.ra[other].to_numpy() * u.deg, t.dec[other].to_numpy() * u.deg).match_to_catalog_sky(
            SkyCoord(ch.ra.to_numpy() * u.deg, ch.dec.to_numpy() * u.deg)
        )
        drop = np.zeros(len(t), bool)
        drop[np.flatnonzero(other)[sep.arcsec <= 1.0]] = True
        t = t[~drop].reset_index(drop=True)
    return t


def match(objects: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """Nearest object within MATCH_ARCSEC of every truth object."""
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    o = objects.dropna(subset=["ra", "dec"]).reset_index(drop=True)
    i, s, _ = SkyCoord(truth.ra.to_numpy() * u.deg, truth.dec.to_numpy() * u.deg).match_to_catalog_sky(
        SkyCoord(o.ra.to_numpy() * u.deg, o.dec.to_numpy() * u.deg)
    )
    hit = s.arcsec <= MATCH_ARCSEC
    m = o.iloc[i].reset_index(drop=True)
    m = pd.concat([truth.reset_index(drop=True), m.add_prefix("o_")], axis=1)
    m["matched"] = hit
    return m[hit].reset_index(drop=True)


COLS = (
    "object_id",
    "ra",
    "dec",
    "primary_class",
    "classification_status",
    "std_mag__ls_r",
    "p_star",
    "p_galaxy",
    "p_qso",
    "secondary_class",
    "secondary_class_reason",
    "parent_object_id",
    "classification_basis",
)


def matched(deep: Path, variant: str) -> pd.DataFrame:
    out = []
    for f in FIELDS:
        p = deep / f"run_{variant}" / f / "classified_objects.csv"
        if not p.exists():
            continue
        o = pd.read_csv(p, low_memory=False, usecols=lambda c: c in COLS)
        m = match(o, truth_table(deep, f))
        m.insert(0, "field", f)
        m.insert(1, "split", split_of(f))
        out.append(m)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ------------------------------------------------------------------- tables
def wilson(k, n):
    return X.wilson(int(k), int(n))


def rbin(x: pd.DataFrame, lo, hi) -> pd.DataFrame:
    return x[(x.o_std_mag__ls_r >= lo) & (x.o_std_mag__ls_r < hi)]


def candidate(m: pd.DataFrame, t: float) -> pd.Series:
    """The (a) rule: not labelled QSO, 22 <= LS r < 24, p_qso >= t."""
    r = m.o_std_mag__ls_r
    return (m.o_primary_class != "QSO") & r.ge(CAND_R_MIN) & r.lt(CAND_R_MAX) & (m.o_p_qso >= t)


def recall_table(m: pd.DataFrame, thresholds=THRESHOLDS) -> pd.DataFrame:
    rows = []
    for split in ("cal", "test", "all"):
        s = m if split == "all" else m[m.split == split]
        for lo, hi in ALL_BINS:
            t1 = rbin(s[s.truth == "TYPE1"], lo, hi)
            n = len(t1)
            lab = int((t1.o_primary_class == "QSO").sum())
            row = {
                "split": split,
                "r": f"{lo:g}-{hi:g}",
                "n_type1": n,
                "label_QSO": lab,
                "label_recall": round(lab / n, 3) if n else None,
            }
            if lo >= CAND_R_MIN and hi <= CAND_R_MAX:
                for t in thresholds:
                    c = int(candidate(t1, t).sum())
                    row[f"cand>={t:g}"] = c
                    row[f"recall_any>={t:g}"] = round((lab + c) / n, 3) if n else None
            rows.append(row)
    return pd.DataFrame(rows)


def purity_table(m: pd.DataFrame, thresholds=THRESHOLDS) -> pd.DataFrame:
    """Per threshold, in the 22-24 range: how many candidates there are by truth class, the false-positive
    rate of each non-QSO class, and the purity in the real mix of the field (the COSMOS fields are complete
    samples of what the classifier sees, so no re-weighting is needed; Chandra misses non-X-ray quasars,
    which count as false positives: the purity is a lower bound)."""
    rows = []
    for split in ("cal", "test", "all"):
        s = m if split == "all" else m[m.split == split]
        s = rbin(s, CAND_R_MIN, CAND_R_MAX)
        for t in thresholds:
            c = candidate(s, t)
            row = {
                "split": split,
                "threshold": t,
                "n_type1": int((s.truth == "TYPE1").sum()),
                "cand_type1": int((c & (s.truth == "TYPE1")).sum()),
            }
            fp = 0
            for k in ("GALAXY", "STAR", "TYPE2"):
                nk = int((s.truth == k).sum())
                ck = int((c & (s.truth == k)).sum())
                row[f"n_{k}"], row[f"cand_{k}"] = nk, ck
                row[f"fp_rate_{k}"] = round(ck / nk, 4) if nk else None
                fp += ck
            tp = row["cand_type1"]
            row["purity"] = round(tp / (tp + fp), 3) if tp + fp else None
            row["purity_wilson95"] = wilson(tp, tp + fp) if tp + fp else None
            row["recall_of_type1_candidates"] = round(tp / row["n_type1"], 3) if row["n_type1"] else None
            rows.append(row)
    return pd.DataFrame(rows)


def calibration_table(m: pd.DataFrame, edges=(0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0001)) -> pd.DataFrame:
    """Observed type-1 fraction in bins of p_qso (22 <= r < 24, objects with a truth class): is p_qso a probability?"""
    rows = []
    for split in ("cal", "test", "all"):
        s = rbin(m if split == "all" else m[m.split == split], CAND_R_MIN, CAND_R_MAX)
        for lo, hi in zip(edges[:-1], edges[1:]):
            x = s[(s.o_p_qso >= lo) & (s.o_p_qso < hi)]
            n = len(x)
            k = int((x.truth == "TYPE1").sum())
            row = {
                "split": split,
                "p_qso": f"{lo:g}-{min(hi, 1):g}",
                "n": n,
                "type1": k,
                "observed": round(k / n, 4) if n else None,
                "mean_p_qso": round(float(x.o_p_qso.mean()), 4) if n else None,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def label_table(m: pd.DataFrame) -> pd.DataFrame:
    """Label counts by truth class and r bin (the test of "labels change in a variant")."""
    rows = []
    for split in ("cal", "test"):
        s = m[m.split == split]
        for lo, hi in ALL_BINS:
            x = rbin(s, lo, hi)
            for k in ("TYPE1", "TYPE2", "GALAXY", "STAR"):
                y = x[x.truth == k]
                rows.append(
                    {
                        "split": split,
                        "r": f"{lo:g}-{hi:g}",
                        "truth": k,
                        "n": len(y),
                        **{c: int((y.o_primary_class == c).sum()) for c in ("QSO", "GALAXY", "STAR", "UNKNOWN")},
                    }
                )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--deep", type=Path, required=True)
    c.add_argument("--variant", required=True)
    c.add_argument("--env", nargs="*", default=[], metavar="K=V")
    c.add_argument("--fields", default=",".join(FIELDS))
    c.add_argument("--jobs", type=int, default=1, help="fields classified at a time")
    q = sub.add_parser(
        "accuracy", help="COSMOS2020 accuracy, McNemar and ECE per variant (compare_ab_fields.py layout)"
    )
    q.add_argument("--deep", type=Path, required=True)
    q.add_argument("--variants", default="base")
    q.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("tables")
    t.add_argument("--deep", type=Path, required=True)
    t.add_argument("--variants", default="base")
    t.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "classify":
        classify(a.deep, a.variant, dict(kv.split("=", 1) for kv in a.env), a.fields.split(","), a.jobs)
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "accuracy":
        print(accuracy_tables(a.deep, a.variants.split(","), a.out).to_string(index=False))
        return 0
    for v in a.variants.split(","):
        m = matched(a.deep, v)
        m.to_csv(a.out / f"matched_{v}.csv.gz", index=False)
        recall_table(m).to_csv(a.out / f"recall_{v}.csv", index=False)
        purity_table(m).to_csv(a.out / f"purity_{v}.csv", index=False)
        calibration_table(m).to_csv(a.out / f"calibration_{v}.csv", index=False)
        label_table(m).to_csv(a.out / f"labels_{v}.csv", index=False)
        print(f"== {v}: {len(m)} matched truth objects, truth {m.truth.value_counts().to_dict()}")
        print(recall_table(m)[lambda d: d.split == "test"].to_string(index=False))
        print(purity_table(m)[lambda d: d.split == "test"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

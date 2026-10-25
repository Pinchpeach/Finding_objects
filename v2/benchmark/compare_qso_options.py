#!/usr/bin/env python3
"""Compare the QSO-separation options of Preprocess/qso_options.py (2.38.0).

Every option is replayed on the same Stage-4 evidence, so differences come
from the option alone.

  bench   SDSS and DESI test splits: accuracy, QSO precision / recall, faint
          bins, and the real-sky QSO purity per r bin from the DESI recall
          matrix under the field class mix of natural_purity (2.36.0).
            python v2/benchmark/compare_qso_options.py bench --out DIR \\
                --sdss-manifest M1 --desi-manifest M2
  field   one search: Stage 5 for every option on WORK/evidence.csv; writes
          object_id, r and class / confidence per option (the validation
          workflow calls this).
            python v2/benchmark/compare_qso_options.py field WORK OUT.csv.gz
  score   the 200 independent fields (validation-data branch): truth accuracy
          and QSO numbers per option from the field files.
            python v2/benchmark/compare_qso_options.py score --out DIR
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
V2 = B.parent
PRE = V2 / "Preprocess"
C = ["STAR", "GALAXY", "QSO"]
# c2, c5 and c6 are the default since 2.38.0 (Preprocess/qso_options.ADOPTED)
SINGLES = ["c1a", "c1a_half", "c1b", "c3a", "c3b", "c4", "c7", "c8"]
COMBOS = ["c3a+c7", "c1b+c3a+c7"]
SETS = ["base", *SINGLES, *COMBOS]


def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def stage4(features, out):
    load(PRE / "04_build_evidence.py", "s4_cmp").run(features, PRE / "classification_rules.csv", out)


def stage5(evidence, opt, model=None):
    s5 = load(PRE / "05_likelihood_vectors.py", "s5_cmp")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "l.csv"
        t = time.perf_counter()
        s5.run(evidence, out, model or s5.MODEL_PATH, options=[] if opt == "base" else opt.split("+"))
        dt = time.perf_counter() - t
        keep = ["object_id", "benchmark_id", "primary_class", "primary_confidence", "classification_status"]
        d = pd.read_csv(out, usecols=lambda c: c in keep, low_memory=False)
    return d, dt


# ---------------------------------------------------------------- bench
def bench_evidence(truth, root, cache):
    """Stage-4 evidence of a benchmark (cached)."""
    f, e = cache / "features.csv", cache / "evidence.csv"
    if not e.exists():
        base = load(B / "evaluate_rule_baseline.py", "rb_cmp")
        base.pre = load(PRE / "02_integrate_objects.py", "integ_cmp")
        raw = base.wide(pd.read_csv(truth), base.read_catalogs(root))
        cache.mkdir(parents=True, exist_ok=True)
        raw.to_csv(cache / "objects.csv", index=False)
        load(PRE / "03_extract_features.py", "s3_cmp").run(cache / "objects.csv", PRE / "classification_rules.csv", f)
        stage4(f, e)
    return f, e


def metrics(t):
    y, p = t.truth_class, t.primary_class
    out = {"n": len(t), "acc": (y == p).mean(), "unknown": (p == "UNKNOWN").mean()}
    for c in C:
        out[f"rec_{c}"] = ((y == c) & (p == c)).sum() / max((y == c).sum(), 1)
        out[f"prec_{c}"] = ((y == c) & (p == c)).sum() / max((p == c).sum(), 1)
    return out


def natural_mix():
    d = pd.read_csv(B / "natural_purity" / "natural_purity.csv")
    d = d[d.thr == 0.5]
    return {b: np.array([float(d[(d.bin == b) & (d.cls == c)].pi.iloc[0]) for c in C]) for b in d.bin.unique()}


def real_sky_qso_purity(t, mix):
    """QSO purity per r bin under the field mix: pi_q R_qq / sum_s pi_s R_sq (Jeffreys rates)."""
    out = {}
    for b, pi in mix.items():
        g = t[t.r_bin == b]
        if not len(g):
            continue
        R = []
        for c in C:
            h = g[g.truth_class == c]
            R.append((((h.primary_class == "QSO").sum()) + 0.5) / (len(h) + 1))
        R = np.array(R)
        out[b] = float(pi[2] * R[2] / (pi @ R))
    return out


def bench(a):
    cache = a.out / "cache"
    sets = {}
    for name, truth, root, man in (
        ("sdss", B / "truth_data/ground_truth.csv", B / "catalog_features", a.sdss_manifest),
        ("desi", B / "desi_external/truth.csv", B / "desi_external/catalog_features", a.desi_manifest),
    ):
        f, e = bench_evidence(truth, root, cache / name)
        tr = pd.read_csv(truth)
        tr["r_bin"] = tr.get("r_bin", pd.Series(np.nan, index=tr.index))
        m = pd.read_csv(man)
        sets[name] = (e, tr.merge(m[["benchmark_id", "split"]], on="benchmark_id"))
    mix = natural_mix()
    rows = []
    for opt in SETS:
        row = {"option": opt}
        for name, (e, tr) in sets.items():
            pred, dt = stage5(e, opt)
            t = tr.merge(pred, on="benchmark_id")
            t = t[t.split.eq("test")]
            for k, v in metrics(t).items():
                row[f"{name}_{k}"] = v
            row[f"{name}_s5_seconds"] = dt
            if name == "desi":
                for b, v in real_sky_qso_purity(t, mix).items():
                    row[f"skyQSOpur_{b}"] = v
                faint = t[t.r_mag > 21]
                for k, v in metrics(faint).items():
                    row[f"desi_r>21_{k}"] = v
        rows.append(row)
        print(opt, {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items() if "acc" in k or "QSO" in k})
    r = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out / "qso_options_bench.csv", index=False)
    return r


# ---------------------------------------------------------------- field
def field(work, out):
    work = Path(work)
    s4 = work / "evidence.csv"
    res = {}
    for opt in SETS:
        d, dt = stage5(s4, opt)
        res[opt] = d.set_index("object_id")
        print(f"{opt}: {dt:.1f} s, QSO {int((d.primary_class == 'QSO').sum())}", flush=True)
    s5 = load(PRE / "05_likelihood_vectors.py", "s5_r")
    t = pd.read_csv(s4, usecols=lambda c: c == "object_id" or c in s5.QSO_OPT.MAG_COLUMNS or c in ("ra", "dec"), low_memory=False)
    t["r"] = s5.QSO_OPT.r_mag(t)
    o = t[["object_id", "ra", "dec", "r"]].set_index("object_id")
    for opt, d in res.items():
        o[f"{opt}_class"] = d.primary_class
        o[f"{opt}_conf"] = d.primary_confidence.round(4)
    o.reset_index().to_csv(out, index=False)


# ---------------------------------------------------------------- score
def score(a):
    sys.path.insert(0, str(B))
    import score_independent_fields as sf

    bench_pos = sf.benchmark_positions()
    rows, per_field = [], []
    for fdir in sorted(p for p in (B / "independent_fields").iterdir() if (p / "qso_options_blind.csv.gz").exists()):
        q = pd.read_csv(fdir / "qso_options_blind.csv.gz")
        m, _ = sf.field_matches(fdir, "blind", bench_pos)
        mm = m.merge(q, on="object_id", how="inner")
        js = json.loads((fdir / "field.json").read_text())
        area = np.pi * (js["radius_arcmin"] / 60) ** 2
        for opt in SETS:
            col = f"{opt}_class"
            if col not in q:
                continue
            rows.append(
                pd.DataFrame(
                    {"field": fdir.name, "option": opt, "truth": mm.t_truth, "pred": mm[col].fillna("UNKNOWN"), "r": mm.r}
                )
            )
            per_field.append(
                {"field": fdir.name, "option": opt, "n_qso": int((q[col] == "QSO").sum()), "qso_per_deg2": float((q[col] == "QSO").sum() / area), "n": len(q)}
            )
    t = pd.concat(rows, ignore_index=True)
    pf = pd.DataFrame(per_field)
    out = []
    for opt, g in t.groupby("option", sort=False):
        r = metrics(g.rename(columns={"truth": "truth_class", "pred": "primary_class"}))
        f = pf[pf.option == opt]
        r.update(
            option=opt,
            median_field_qso_per_deg2=float(f.qso_per_deg2.median()),
            mc_qso=int(f[f.field.str.startswith(("lmc", "smc", "mag_"))].n_qso.sum()),
            other_qso=int(f[~f.field.str.startswith(("lmc", "smc", "mag_"))].n_qso.sum()),
        )
        out.append(r)
    res = pd.DataFrame(out)
    a.out.mkdir(parents=True, exist_ok=True)
    res.to_csv(a.out / "qso_options_fields.csv", index=False)
    pf.to_csv(a.out / "qso_options_field_density.csv", index=False)
    print(res.round(4).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--sdss-manifest", type=Path, required=True)
    b.add_argument("--desi-manifest", type=Path, required=True)
    f = sub.add_parser("field")
    f.add_argument("work")
    f.add_argument("out")
    s = sub.add_parser("score")
    s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    {"bench": bench, "field": lambda a: field(a.work, a.out), "score": score}[a.mode](a)


if __name__ == "__main__":
    main()

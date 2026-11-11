#!/usr/bin/env python3
"""Rule fusion against a single GBM, with full and partial data (2.51.0).

The scientific review (SCIENTIFIC_REVIEW_2026-11-11.md sec. 4, item 13)
found the fused coarse classifier no better than one gradient-boosted tree
model on the balanced SDSS / DESI benchmarks, and noted that the claimed
advantage of the rule structure, behaviour when only some surveys cover an
object, had never been measured.  This script measures it.

For each scenario one or more surveys are removed from every object (the
catalogue rows are dropped before Stage 2, as if the survey did not cover
the field).  Both models then see exactly the same Stage-3 inputs:
  pipeline  Stage 3-5 with the production fusion weights
  gbm_full  HistGradientBoosting on the measured features (no X-ray / radio,
            as the production trees), trained on the full-data train splits
  gbm_aug   the same, plus a 0.3-weight copy of the train rows for every
            scenario (the augmentation the fusion weights get)
Train = SDSS + DESI + DESI-fusion train splits (as fit_fusion_weights.py);
reported on the SDSS and DESI test splits, with balanced accuracy and the
exact McNemar test against the pipeline (benchmark/field_stats.py).

    python v2/benchmark/partial_data_compare.py --manifests READY READY_DESI READY_DFUS --out DIR
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
sys.path.insert(0, str(B))
import field_stats as FS  # noqa: E402

spec = importlib.util.spec_from_file_location("erb", B / "evaluate_rule_baseline.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

SETS = {
    "sdss": (B / "truth_data/ground_truth.csv", B / "catalog_features"),
    "desi": (B / "desi_external/truth.csv", B / "desi_external/catalog_features"),
    "dfus": (B / "desi_fusion/truth.csv", B / "desi_fusion/catalog_features"),
}
SCENARIOS = {
    "full": [],
    "no_gaia": ["gaia_dr3"],
    "no_ls": ["desi_legacy"],
    "no_ps1": ["panstarrs1"],
    "no_wise": ["allwise"],
    "no_ls_ps1": ["desi_legacy", "panstarrs1"],
    "no_ls_gaia": ["desi_legacy", "gaia_dr3"],
}
CLS = ["STAR", "GALAXY", "QSO"]


def stage(truth, cats, drop, with_fusion):
    cats = {k: v for k, v in cats.items() if k not in drop}
    raw = E.wide(truth, cats)
    s3, s4, s5 = (E.load_script(n) for n in ("03_extract_features.py", "04_build_evidence.py", "05_likelihood_vectors.py"))
    rules = E.PRE / "classification_rules.csv"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        raw.to_csv(td / "o.csv", index=False)
        s3.run(td / "o.csv", rules, td / "f.csv")
        f = pd.read_csv(td / "f.csv", low_memory=False)
        pred = None
        if with_fusion:
            s4.run(td / "f.csv", rules, td / "e.csv")
            s5.run(td / "e.csv", td / "l.csv")
            pred = pd.read_csv(td / "l.csv", usecols=["benchmark_id", "primary_class"])
    return f, pred


def num(f, *names):
    for n in names:
        if n in f:
            return pd.to_numeric(f[n], errors="coerce")
    return pd.Series(np.nan, index=f.index)


def gbm_features(f):
    """Measured quantities only: no catalogue labels, no X-ray / radio, no positions."""
    x = pd.DataFrame(index=f.index)
    x["plx_snr"] = num(f, "gaia_dr3__parallax", "parallax") / num(f, "gaia_dr3__parallax_error", "parallax_error")
    x["pm_snr"] = np.hypot(num(f, "gaia_dr3__pmra", "pmra") / num(f, "gaia_dr3__pmra_error", "pmra_error"),
                           num(f, "gaia_dr3__pmdec", "pmdec") / num(f, "gaia_dr3__pmdec_error", "pmdec_error"))
    for k in ("quasar", "galaxy", "star", "whitedwarf", "binarystar"):
        x[f"dsc_{k}"] = num(f, f"gaia_dr3__classprob_dsc_combmod_{k}", f"classprob_dsc_combmod_{k}")
    x["gaia_g"] = num(f, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    for c in ("ps1_g_r_color", "ps1_r_i_color", "ps1_i_z_color", "ps1_z_y_color", "ps1_i_psf_minus_kron",
              "ls_g_r_color", "ls_r_z_color", "ls_z_w1_color", "ls_w1_w2_color", "ls_zw1_excess",
              "ls_dchisq_rex_rel_log", "ls_size_sig_log", "ls_r_mag", "wise_w1_w2_color", "wise_w2_w3_color"):
        x[c] = num(f, c)
    x["ps1_i"] = num(f, "pan_starrs1_dr2_meanobject__iMeanPSFMag", "iMeanPSFMag")
    for b in "gri":
        x[f"ps1_{b}_std"] = num(f, f"pan_starrs1_dr2_meanobject__{b}MeanPSFMagStd", f"{b}MeanPSFMagStd")
    x["w2"] = num(f, "allwise__W2mag", "W2mag")
    t = f.get("desi_legacy_surveys_dr10__type", f.get("type", pd.Series("", index=f.index))).astype(str).str.strip().str.upper()
    x["ls_psf"] = np.where(t.isin(["", "NAN"]), np.nan, (t == "PSF").astype(float))
    return x.replace([np.inf, -np.inf], np.nan)


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier

    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests", type=Path, nargs=3, required=True, help="benchmark_manifest.csv of sdss, desi, dfus")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    data = {}
    for (name, (tp, root)), mp in zip(SETS.items(), a.manifests):
        t = pd.read_csv(tp).merge(pd.read_csv(mp)[["benchmark_id", "split"]], on="benchmark_id")
        E.pre = E.load_script("02_integrate_objects.py")
        data[name] = (t, E.read_catalogs(root))
    feats, preds = {}, {}
    for sc, drop in SCENARIOS.items():
        for name, (t, cats) in data.items():
            print("stage", sc, name, flush=True)
            f, p = stage(t, cats, drop, with_fusion=name != "dfus")
            x = gbm_features(f)
            x["benchmark_id"] = f.benchmark_id.to_numpy()
            feats[sc, name] = x.merge(t[["benchmark_id", "truth_class", "split"]], on="benchmark_id")
            if p is not None:
                preds[sc, name] = p
    cols = [c for c in feats["full", "sdss"].columns if c not in ("benchmark_id", "truth_class", "split")]

    def train(aug):
        parts = []
        for (sc, _), x in feats.items():
            if sc == "full" or aug:
                tr = x[x.split.eq("train")]
                parts.append(tr.assign(w=1.0 if sc == "full" else 0.3))
        tr = pd.concat(parts, ignore_index=True)
        # class-balanced like the fusion weights
        cw = tr.groupby("truth_class").w.sum()
        w = tr.w * tr.truth_class.map(cw.mean() / cw)
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0)
        m.fit(tr[cols], tr.truth_class, sample_weight=w)
        return m

    models = {"gbm_full": train(False), "gbm_aug": train(True)}
    rows = []
    for sc in SCENARIOS:
        for name in ("sdss", "desi"):
            x = feats[sc, name]
            te = x[x.split.eq("test")].merge(preds[sc, name], on="benchmark_id")
            ok_p = (te.primary_class == te.truth_class).to_numpy()
            r = dict(scenario=sc, set=name, n=len(te),
                     pipeline=round(100 * ok_p.mean(), 2),
                     pipeline_bal=round(100 * FS._bal(te.primary_class, te.truth_class), 2),
                     pipeline_unknown=int((te.primary_class == "UNKNOWN").sum()))
            for k, m in models.items():
                yp = m.predict(te[cols])
                ok = yp == te.truth_class.to_numpy()
                r[k] = round(100 * ok.mean(), 2)
                r[k + "_bal"] = round(100 * FS._bal(pd.Series(yp), te.truth_class.reset_index(drop=True)), 2)
                p, n01, n10 = FS.mcnemar(ok, ok_p)
                r[k + "_vs_pipeline_p"] = round(p, 4)
                r[k + "_only_right"], r[k + "_pipeline_only_right"] = n01, n10
            rows.append(r)
            print(r, flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(a.out / "partial_data_compare.csv", index=False)
    (a.out / "features.json").write_text(json.dumps(cols, indent=1))
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()

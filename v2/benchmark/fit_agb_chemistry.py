"""Fit the photometric AGB chemistry models (C-rich vs O-rich) used by
Classifier/subclass.py:agb_chemistry().

Truth: Suh (2021, ApJS 256, 43) O-AGB / C-AGB stars with Gaia DR3, 2MASS,
AllWISE and Gaia DR3 LPV photometry (benchmark/agb_truth, built by
build_agb_chemistry_truth.py).  A seed-42 50/50 random split: the logistic
models are fitted on one half and all metrics are measured on the other.

Models form a cascade; a star uses the first model whose features it has:
  1. W_RP - W_KJ (Lebzelter et al. 2018), Ks - W3, Gaia LPV is_cstar
     (Lebzelter et al. 2023)
  2. W_RP - W_KJ, Ks - W3
  3. J - Ks, Ks - W3, W1 - W2, W3 - W4 (no Gaia)
A WISE-only model was tried and dropped (46.6 % on stars without 2MASS).
Probabilities within ``--band`` of 0.5 abstain.

Stars fainter than the red clump with a good parallax (M_Ks > -1, parallax
S/N >= 5, RUWE < 1.4) are dropped (``--keep-faint`` keeps them): they are
dwarf / CH carbon stars in the C-AGB table, which the classifier vetoes
before the models are used (Classifier/subclass.py AGB_MAX_MKS).

    python v2/benchmark/fit_agb_chemistry.py            # prints metrics
    python v2/benchmark/fit_agb_chemistry.py --write    # updates the model file
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

V2 = Path(__file__).resolve().parents[1]
TRUTH = V2 / "benchmark/agb_truth/agb_chemistry_truth.csv.gz"
MODEL = V2 / "Classifier/agb_chemistry_model.json"
SPEC = [("GAIA_2MASS_WISE_CSTAR", ["dW", "kw3", "cst"]),
        ("GAIA_2MASS_WISE", ["dW", "kw3"]),
        ("NIR_MIR", ["jk", "kw3", "w12", "w34"])]


def features(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["jk"] = d.tm_j - d.tm_ks
    d["kw3"] = d.tm_ks - d.aw_w3
    d["w34"] = d.aw_w3 - d.aw_w4
    d["w12"] = d.aw_w1 - d.aw_w2
    d["dW"] = (d.g_rp - 1.3 * (d.g_bp - d.g_rp)) - (d.tm_ks - 0.686 * d.jk)
    d["cst"] = d.lpv_is_cstar
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--truth", default=str(TRUTH))
    ap.add_argument("--band", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--keep-faint", action="store_true", help="keep the sub-red-clump (non-AGB) stars")
    ap.add_argument("--write", action="store_true", help=f"write {MODEL.relative_to(V2)}")
    a = ap.parse_args()

    d = features(pd.read_csv(a.truth, low_memory=False))
    good = (d.g_plx > 0) & (d.g_eplx > 0) & (d.g_plx / d.g_eplx >= 5) & (d.g_ruwe < 1.4)
    faint = good & (d.tm_ks + 5 * np.log10(d.g_plx.where(d.g_plx > 0)) - 10 > -1.0)
    n_faint = {k: int(v) for k, v in d[faint].chem.value_counts().items()}
    if not a.keep_faint:
        d = d[~faint].reset_index(drop=True)
    y = d.chem.eq("C").astype(int).to_numpy()
    train = np.random.default_rng(a.seed).random(len(d)) < 0.5
    te = ~train
    models, P = {}, {}
    for name, f in SPEC:
        m = d[f].notna().all(axis=1).to_numpy()
        clf = LogisticRegression(max_iter=1000).fit(d.loc[m & train, f].to_numpy(), y[m & train])
        models[name] = {"features": f, "coef": [round(float(c), 4) for c in clf.coef_[0]],
                        "intercept": round(float(clf.intercept_[0]), 4)}
        p = np.full(len(d), np.nan)
        p[m] = clf.predict_proba(d.loc[m, f].to_numpy())[:, 1]
        P[name] = p

    pred = np.full(len(d), np.nan)
    src = np.full(len(d), "", dtype=object)
    for name, _ in SPEC:                       # first available model wins
        todo = (src == "") & ~np.isnan(P[name])
        src[todo] = name
        sure = todo & (np.abs(P[name] - 0.5) >= a.band)
        pred[sure] = P[name][sure] >= 0.5

    m = te & ~np.isnan(pred)
    pc, yc = pred[m], y[m]
    r = lambda x: round(float(x), 3)
    res = {"test_n": int(te.sum()), "coverage": r(m.sum() / te.sum()), "accuracy": r((pc == yc).mean()),
           "C_precision": r(((pc == 1) & (yc == 1)).sum() / max((pc == 1).sum(), 1)),
           "C_recall": r(((pc == 1) & (yc == 1)).sum() / max((yc == 1).sum(), 1)),
           "O_precision": r(((pc == 0) & (yc == 0)).sum() / max((pc == 0).sum(), 1)),
           "O_recall": r(((pc == 0) & (yc == 0)).sum() / max((yc == 0).sum(), 1)),
           "per_model": {}}
    for name, _ in SPEC:
        mm = te & (src == name)
        ok = mm & ~np.isnan(pred)
        res["per_model"][name] = {"n": int(mm.sum()), "decided": int(ok.sum()),
                                  "accuracy": r((pred[ok] == y[ok]).mean()) if ok.any() else None}
    res["O_rich_Ks_W3_gt_1"] = r((d.kw3[d.chem.eq("O")] > 1.0).mean())
    out = {"models": models, "abstain_band": a.band, "test": res,
           "split": f"50/50 random (seed {a.seed}); fitted on train half, metrics on test half",
           "excluded_sub_red_clump": {} if a.keep_faint else n_faint,
           "truth": "benchmark/agb_truth/agb_chemistry_truth.csv.gz (Suh 2021 O-AGB 5301, C-AGB 3576)"}
    print(json.dumps(out, indent=1))
    if a.write:
        MODEL.write_text(json.dumps(out, indent=1))
        print(f"wrote {MODEL}")


if __name__ == "__main__":
    main()

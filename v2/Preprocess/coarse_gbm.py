"""Single gradient-boosted coarse classifier on measured quantities (2.51.0).

The scientific review (SCIENTIFIC_REVIEW_2026-11-11.md sec. 4, item 13) asked
whether the rule fusion of Stage 5 beats one gradient-boosted model given the
same inputs, with full and with partial survey coverage, and to use the single
model if it does not.  benchmark/partial_data_compare.py measured it on the
SDSS / DESI test splits (WORK_REPORT_2026-11-11.md): the single model with
survey-drop augmentation was better in all 14 set x coverage cases, by 1.2-2.8
points with full data and up to 39 points when the deep optical surveys are
missing.  Gradient-boosted trees on photometry and astrometry are the
standard for this task (Chaussidon et al. 2023 for DESI QSO targets; Hughes
et al. 2022, Clarke et al. 2020 for multi-survey STAR/GALAXY/QSO).

Inputs are measurements only: Gaia parallax and proper-motion significance,
Gaia DSC probabilities, PS1 / LS colours, PSF-Kron, LS Tractor fit
quantities, WISE colours and PS1 epoch scatter.  No X-ray or radio (survey
coverage, not class; the production trees exclude them since 2.26.0), no
positions, no catalogue labels.  Trained class-balanced on the train splits
(benchmark/partial_data_compare.py --export), so Stage 5's priors apply to
its output exactly as to the fusion's.  Inference is numpy-only
(ls_gbm.raw_scores), like LS-GBM-001.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

CLASSES = ("STAR", "GALAXY", "QSO")
MODEL_PATH = Path(__file__).with_name("coarse_gbm_model.npz")
_s = importlib.util.spec_from_file_location("v2_ls_gbm_trees_c", Path(__file__).with_name("ls_gbm.py"))
TREES = importlib.util.module_from_spec(_s)
_s.loader.exec_module(TREES)

COLOURS = ("ps1_g_r_color", "ps1_r_i_color", "ps1_i_z_color", "ps1_z_y_color", "ps1_i_psf_minus_kron",
           "ls_g_r_color", "ls_r_z_color", "ls_z_w1_color", "ls_w1_w2_color", "ls_zw1_excess",
           "ls_dchisq_rex_rel_log", "ls_size_sig_log", "ls_r_mag", "wise_w1_w2_color", "wise_w2_w3_color")


def _num(f, *names):
    for n in names:
        if n in f:
            return pd.to_numeric(f[n], errors="coerce")
    return pd.Series(np.nan, index=f.index)


def features(f: pd.DataFrame) -> pd.DataFrame:
    """Measured quantities from a Stage-3 / Stage-4 table (survey-prefixed
    columns first, raw benchmark names as fall-back)."""
    x = pd.DataFrame(index=f.index)
    x["plx_snr"] = _num(f, "gaia_dr3__parallax", "parallax") / _num(f, "gaia_dr3__parallax_error", "parallax_error")
    x["pm_snr"] = np.hypot(_num(f, "gaia_dr3__pmra", "pmra") / _num(f, "gaia_dr3__pmra_error", "pmra_error"),
                           _num(f, "gaia_dr3__pmdec", "pmdec") / _num(f, "gaia_dr3__pmdec_error", "pmdec_error"))
    d = {k: _num(f, f"gaia_dr3__classprob_dsc_combmod_{k}", f"classprob_dsc_combmod_{k}")
         for k in ("quasar", "galaxy", "star", "whitedwarf", "binarystar")}
    x["dsc_quasar"], x["dsc_galaxy"] = d["quasar"], d["galaxy"]
    # star + white dwarf + binary: VizieR's PSS (benchmark) is this sum, the
    # Gaia archive (production) splits it, so only the sum is a feature.
    x["dsc_star"] = (d["star"].fillna(0) + d["whitedwarf"].fillna(0) + d["binarystar"].fillna(0)).where(d["quasar"].notna())
    x["gaia_g"] = _num(f, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    for c in COLOURS:
        x[c] = _num(f, c)
    x["ps1_i"] = _num(f, "pan_starrs1_dr2_meanobject__iMeanPSFMag", "iMeanPSFMag")
    for b in "gri":
        x[f"ps1_{b}_std"] = _num(f, f"pan_starrs1_dr2_meanobject__{b}MeanPSFMagStd", f"{b}MeanPSFMagStd")
    x["w2"] = _num(f, "allwise__W2mag", "W2mag")
    t = f["desi_legacy_surveys_dr10__type"] if "desi_legacy_surveys_dr10__type" in f else f.get("type", pd.Series("", index=f.index))
    t = t.fillna("").astype(str).str.strip().str.upper()
    x["ls_psf"] = np.where(t.isin(["", "NAN", "NONE"]), np.nan, (t == "PSF").astype(float))
    return x.replace([np.inf, -np.inf], np.nan)


@lru_cache(maxsize=2)
def load_model(path: str = str(MODEL_PATH)):
    return TREES.load_model(path)


def predict_proba(f: pd.DataFrame, path: str = str(MODEL_PATH)):
    """(n, 3) STAR/GALAXY/QSO probabilities and a mask of rows with at least
    one measured feature; None when the model file is missing."""
    m = load_model(path)
    if m is None:
        return None
    names = [str(n) for n in m["features"]]
    x = features(f).reindex(columns=names)
    X = x.to_numpy(float)
    has = np.isfinite(X).any(axis=1)
    order = [[str(c) for c in m["classes"]].index(c) for c in CLASSES]
    P = np.full((len(X), 3), np.nan)
    if has.any():
        z = TREES.raw_scores(X[has], m)[:, order]
        z = np.exp(z - z.max(axis=1, keepdims=True))
        P[has] = z / z.sum(axis=1, keepdims=True)
    return P, has

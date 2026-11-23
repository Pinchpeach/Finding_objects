"""QSO-separation options for Stage 5 (2.38.0 comparison).

On by default (names still accepted and ignored): c5, c6 (2.38.0), c1b,
c3a, c7 (2.39.0) and c1a_half (2.40.0, user decision after the 200-field
confirmation): all improved or kept the accuracy on the 200 independent
fields; c1a_half costs accuracy on the QSO-rich benchmarks (SDSS -0.75,
DESI -3.4 %p) for real-sky QSO purity.  c2 was default in 2.38.0 and reverted in
2.39.0 (the fields lost 0.11 %p).  The others stay switchable.

Each option is one candidate of ``v2/LITERATURE_QSO.md`` Sect. 3; they are
off by default and switched on with ``V2_QSO_OPTIONS`` (comma-separated
names) or the ``options`` argument of Stage 5 ``run``, so that
``benchmark/compare_qso_options.py`` can measure every candidate on the same
evidence.  Factors act on the odds of the extragalactic classes after the
fusion and never exceed 1; ``VETO`` is the likelihood ratio of a failed
literature cut (soft: a cut that removes ~4x the contaminants, Quaia, is
evidence, not proof).

  c1a   magnitude label-shift prior on the QSO odds: real-sky QSO fraction
        per r bin (benchmark/natural_purity, 2.36.0) against the fusion's
        training prior (Saerens et al. 2002; Bovy et al. 2011 number-count
        prior).  c1a_half applies the square root (a tempered prior).
  c1b   local stellar-density prior on GALAXY and QSO odds: Gaia source
        density at the object (10th neighbour) against the training sky,
        min(1, rho_ref / rho); replaces the latitude and Magellanic factors
        (Jamal & Bailer-Jones 2024 continuous prior; Hughes et al. 2022).
  c2    Mahalanobis zero-motion test with the pmra-pmdec correlation and
        scale s = 1.1485 (Li & Fynbo 2026) for AST-EXT-002 / AST-GAL-002
        (Stage 4; needs refitted fusion weights to be fair).
  c3a   DESI QSO preselection: W1 < 22.3 and W2 < 22.3 AB in Legacy Surveys
        (Chaussidon et al. 2023, Sect. 3), else the QSO odds x VETO.
  c3b   c3a and the r-dependent QSO threshold p_th(r) = 0.88 - 0.04 tanh(r -
        20.5) (Chaussidon et al. 2023, North values; their RF scale).
  c4    Quaia colour cuts for Gaia sources with G < 20.5: G - W1 > 2.15,
        W1 - W2 > 0.4 (Vega) and BP - G > -0.3 (Storey-Fisher et al. 2024),
        else the QSO odds x VETO.
  c5    Magellanic systemic motions of Luri et al. 2021, Table 4.
  c6    X-ray star line [W1] < -1.625 log F(0.5-2 keV) - 8.8 (Salvato et al.
        2018, Eq. 2; Vega W1): X-ray source on the stellar side, QSO odds x VETO.
  c7    Gaia DSC evidence ignored inside the Magellanic Clouds (38 % of DSC
        quasars lie in the LMC; Delchambre et al. 2023).
  c8    QSO predictions fainter than r = 22 (outside the training range,
        Nakoneczny et al. 2019) become UNKNOWN.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

KNOWN = ("c1a", "c2", "c3b", "c4", "c8")
# on by default: c5, c6 since 2.38.0; c1b, c3a, c7 since 2.39.0 (200-field
# replay); c1a_half since 2.40.0 (c1a = the full-strength prior instead)
ADOPTED = ("c1a_half", "c1b", "c3a", "c5", "c6", "c7")
VETO = 0.1

# QSO fraction per r bin from the true class mix of the 18 search fields
# (benchmark/natural_purity/natural_purity.csv, 2.36.0).
# Known inconsistency (2.59.0, WORK_REPORT_2026-11-23c.md section 6): the last bin is not the real-sky
# fraction at r > 22.  natural_purity.py fixes the QSO count of a bin from the published density
# (QSO_DENSITY "r>22" = 110 deg^-2, one magnitude, 22-23) but divides by every classified object from
# r = 22 to the faint end, so 0.0011 is the share at 24-25; the measured COSMOS shares are 3-7 times
# higher at 22-23 (0.0051-0.0081) and 23-24 (0.0023-0.0033).  Kept: the two corrected variants
# (measured COSMOS share, literature density) broke 3 and 5 COSMOS2020 labels with no fix and made the
# test-field ECE and NLL worse, also on the truth extended with Chandra type-1 quasars (ECE 0.41 ->
# 0.64 / 0.67 %).  Faint quasars are reported as candidates instead (faint_candidates below).
MAG_EDGES = (-np.inf, 18.0, 20.0, 21.0, 22.0, np.inf)
PI_QSO = (0.0007, 0.0037, 0.0056, 0.0077, 0.0011)
MAG_COLUMNS = ("ls_r_mag", "pan_starrs1_dr2_meanobject__rMeanPSFMag", "sdss_dr18_photoobj__r", "gaia_dr3__phot_g_mean_mag")
# Gaia DR3 sources per deg^2 of the training sky: median of the 200-region
# fields at |b| > 30 deg away from the Clouds (2026-10-24 counts).
RHO_REF = 5.0e3
KNN = 10
# W1, W2 AB - Vega (Jarrett et al. 2011)
W1_AB_VEGA, W2_AB_VEGA = 2.699, 3.339


def parse(options=None) -> frozenset:
    raw = options if options is not None else os.environ.get("V2_QSO_OPTIONS", "")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",")]
    opts = frozenset(x for x in raw if x)
    opts = opts - set(ADOPTED)  # always on now
    bad = opts - set(KNOWN)
    if bad:
        raise ValueError(f"unknown V2_QSO_OPTIONS {sorted(bad)}; known: {KNOWN}")
    return opts


# ---- faint QSO candidates (2.57.0; WORK_REPORT_2026-11-23b.md section 11) ----------------------
# Where the posterior cannot make a quasar the label (the sky holds ~10^2-10^3 galaxies per quasar at
# r > 22, Bayes), the object is still reported as a candidate next to its label, as the label-less
# "other reading" of agn_host.py: secondary_class = QSO, reason FAINT_QSO_CANDIDATE.  The primary class
# and every accuracy stay as they were.  On by default since 2.57.0 at CANDIDATE_P (the threshold of the table
# in the work report, chosen on the odd COSMOS fields); V2_FAINT_QSO_CANDIDATE=off or another value overrides it.
CANDIDATE_R = (22.0, 24.0)  # LS r; r >= 24 is not touched (no measurement of the purity there)
CANDIDATE_REASON = "FAINT_QSO_CANDIDATE"
CANDIDATE_P = 0.1  # the F1-optimal threshold of the odd COSMOS fields (work report section 11); None = off
LS_R_COLUMN = "std_mag__ls_r"


def candidate_threshold():
    """Threshold on p_qso for the candidate flag, or None when it is off."""
    v = os.environ.get("V2_FAINT_QSO_CANDIDATE", "" if CANDIDATE_P is None else str(CANDIDATE_P)).strip().lower()
    if v in ("", "off", "0", "none", "false", "no"):
        return None
    t = float(v)
    if not 0.0 < t < 1.0:
        raise ValueError(f"V2_FAINT_QSO_CANDIDATE={v!r}: a probability in (0, 1), or 'off'")
    return t


def faint_candidates(df, labels, p_qso, sec, why):
    """Add the QSO candidate reading to rows that have no other reading yet.

    ``labels`` the primary classes, ``p_qso`` the final quasar probabilities (NaN where none), ``sec`` / ``why``
    the lists of agn_host.secondary.  A row qualifies when its label is not QSO, its Legacy Surveys r is
    in CANDIDATE_R and p_qso >= the threshold."""
    t = candidate_threshold()
    if t is None or not len(df):
        return sec, why
    r = _col(df, LS_R_COLUMN)
    p = np.asarray(p_qso, float)
    hit = (np.asarray(labels, object) != "QSO") & (r >= CANDIDATE_R[0]) & (r < CANDIDATE_R[1]) & (p >= t)
    sec, why = list(sec), list(why)
    for i in np.flatnonzero(hit):
        if not sec[i]:
            sec[i], why[i] = "QSO", CANDIDATE_REASON
    return sec, why


# ---- QSO share of the faint prior from COSMOS (2.57.0; variant (b) of the work report) ---------
# faint_class_prior_cosmos.csv (2.52.0) holds star and galaxy counts only, and the QSO magnitude prior
# above takes its last bin (r > 22, 0.11 %) from spectroscopic fields that hardly reach it.  With
# V2_FAINT_QSO_SHARE=half|full the QSO odds at 22 <= r < 24 come from the Chandra type-1 share of the
# COSMOS calibration fields (benchmark/build_faint_qso_share.py -> faint_qso_share_cosmos.csv), tempered
# by the square root like the default prior ("half") or not ("full").  Off by default.
SHARE_TABLE = Path(__file__).resolve().parent / "faint_qso_share_cosmos.csv"
SHARE_MODES = ("off", "half", "full")


def share_mode() -> str:
    v = os.environ.get("V2_FAINT_QSO_SHARE", "off").strip().lower() or "off"
    if v not in SHARE_MODES:
        raise ValueError(f"V2_FAINT_QSO_SHARE={v!r}; known: {SHARE_MODES}")
    return v


def share_table_path() -> Path:
    """The share table: V2_FAINT_QSO_SHARE_TABLE (for an A/B of another table), else the bundled one."""
    v = os.environ.get("V2_FAINT_QSO_SHARE_TABLE", "").strip()
    return Path(v) if v else SHARE_TABLE


def faint_share_factor(df, table=None, mode=None) -> np.ndarray:
    """Factor on the QSO odds from the COSMOS type-1 share per LS r bin; NaN where it does not apply
    (mode off, r outside the table, no r)."""
    mode = share_mode() if mode is None else mode
    out = np.full(len(df), np.nan)
    if mode == "off" or not len(df):
        return out
    t = pd.read_csv(share_table_path()) if table is None else table
    r = _col(df, LS_R_COLUMN)
    train = 1.0 / 3.0
    for row in t.itertuples():
        pi = (row.n_type1 + 0.5) / (row.n_type1 + row.n_other + 1.0)  # Jeffreys smoothing
        f = (pi / (1.0 - pi)) / (train / (1.0 - train))
        f = np.sqrt(f) if mode == "half" else f
        out = np.where((r >= row.r_lo) & (r < row.r_hi), min(float(f), 1.0), out)
    return out


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def r_mag(df) -> np.ndarray:
    r = np.full(len(df), np.nan)
    for c in MAG_COLUMNS:
        r = np.where(np.isfinite(r), r, _col(df, c))
    return np.where((r > 5) & (r < 30), r, np.nan)


def _ls_ab(df, band):
    f = _col(df, f"desi_legacy_surveys_dr10__flux_{band}")
    t = _col(df, f"desi_legacy_surveys_dr10__mw_transmission_{band}")
    t = np.where(np.isfinite(t) & (t > 0), t, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = 22.5 - 2.5 * np.log10(f / t)
    return np.where(np.isfinite(f), np.where(f > 0, m, np.inf), np.nan)  # inf = not detected


def wise_vega(df):
    """(W1, W2) Vega: AllWISE, else Legacy Surveys unWISE forced photometry."""
    w1, w2 = _col(df, "allwise__W1mag"), _col(df, "allwise__W2mag")
    l1, l2 = _ls_ab(df, "w1") - W1_AB_VEGA, _ls_ab(df, "w2") - W2_AB_VEGA
    l1 = np.where(np.isfinite(l1), l1, np.nan)
    l2 = np.where(np.isfinite(l2), l2, np.nan)
    return np.where(np.isfinite(w1), w1, l1), np.where(np.isfinite(w2), w2, l2)


def magnitude_prior(df, half=False) -> np.ndarray:
    """c1a: factor on the QSO odds from the real-sky QSO fraction of the object's r bin."""
    r = r_mag(df)
    pi = np.full(len(df), np.nan)
    for lo, hi, p in zip(MAG_EDGES[:-1], MAG_EDGES[1:], PI_QSO):
        pi = np.where((r > lo) & (r <= hi), p, pi)
    train = 1.0 / 3.0  # fusion training prior (fusion_weights.json, about equal classes)
    f = (pi / (1 - pi)) / (train / (1 - train))
    f = np.sqrt(f) if half else f
    return np.where(np.isfinite(f), np.minimum(f, 1.0), 1.0)


def local_density(df) -> np.ndarray:
    """Gaia DR3 sources per deg^2 at each object from its 10th Gaia neighbour;
    NaN where it cannot be measured (no position, <= KNN Gaia sources in the search)."""
    ra, dec = _col(df, "ra"), _col(df, "dec")
    g = np.isfinite(_col(df, "gaia_dr3__phot_g_mean_mag")) & np.isfinite(ra) & np.isfinite(dec)
    rho_out = np.full(len(df), np.nan)
    if g.sum() <= KNN:
        return rho_out
    from scipy.spatial import cKDTree

    def xyz(a, d):
        a, d = np.radians(a), np.radians(d)
        return np.c_[np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)]

    tree = cKDTree(xyz(ra[g], dec[g]))
    ok = np.isfinite(ra) & np.isfinite(dec)
    dist, _ = tree.query(xyz(ra[ok], dec[ok]), k=KNN + 1)
    theta = 2 * np.degrees(np.arcsin(np.clip(dist[:, -1] / 2, 0, 1)))  # chord -> deg
    rho_out[ok] = KNN / (np.pi * np.maximum(theta, 1e-6) ** 2)
    return rho_out


def density_prior(df, rho=None) -> np.ndarray:
    """c1b: min(1, RHO_REF / local Gaia density) from the 10th Gaia neighbour;
    NaN where it cannot be measured (no position, <= KNN Gaia sources in the search)."""
    rho = local_density(df) if rho is None else rho
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isfinite(rho), np.maximum(np.minimum(1.0, RHO_REF / rho), 1e-4), np.nan)


def desi_wise_cut(df) -> np.ndarray:
    """c3a: True where Legacy Surveys W1 or W2 is fainter than 22.3 AB (or not detected)."""
    w1, w2 = _ls_ab(df, "w1"), _ls_ab(df, "w2")
    have = np.isfinite(_col(df, "desi_legacy_surveys_dr10__flux_w1"))
    return have & ((w1 >= 22.3) | (w2 >= 22.3))


def desi_threshold(df) -> np.ndarray:
    r = r_mag(df)
    return np.where(np.isfinite(r), 0.88 - 0.04 * np.tanh(r - 20.5), 0.5)


def quaia_fail(df) -> np.ndarray:
    """c4: True for a Gaia source with G < 20.5 that fails a Quaia colour cut."""
    g, bp = _col(df, "gaia_dr3__phot_g_mean_mag"), _col(df, "gaia_dr3__phot_bp_mean_mag")
    w1, w2 = wise_vega(df)
    in_range = np.isfinite(g) & (g < 20.5) & np.isfinite(w1) & np.isfinite(w2)
    with np.errstate(invalid="ignore"):
        bad = (g - w1 <= 2.15) | (w1 - w2 <= 0.4) | (np.isfinite(bp) & (bp - g <= -0.3))
    return in_range & bad


def xray_star_side(df) -> np.ndarray:
    """c6: True for an X-ray source on the stellar side of Salvato+2018 Eq. 2.

    X-ray flux as Stage 4 ``xray_flux`` (0.3-3.5 keV from Chandra broad,
    4XMM band 8 or a point-like eRASS1 band 1, Gamma = 1.8), converted to
    0.5-2 keV with the same photon index."""
    def band(e1, e2):
        return (3.5**0.2 - 0.3**0.2) / (e2**0.2 - e1**0.2)

    fx = np.full(len(df), np.nan)
    ext = np.nan_to_num(_col(df, "erosita_erass1__EXTLike"), nan=0.0) > 0
    for name, scale in (
        ("chandra_csc_2_0__Fluxb", band(0.5, 7.0)),
        ("xmm_4xmm_dr13__Flux8", band(0.2, 12.0)),
        ("erosita_erass1__MLFlux1", band(0.2, 2.3)),
    ):
        v = _col(df, name)
        if name.startswith("erosita_"):
            v = np.where(ext, np.nan, v)
        fx = np.where(np.isfinite(fx) | ~(v > 0), fx, v * scale)
    soft = fx * (2.0**0.2 - 0.5**0.2) / (3.5**0.2 - 0.3**0.2)
    w1, _ = wise_vega(df)
    with np.errstate(invalid="ignore", divide="ignore"):
        line = -1.625 * np.log10(soft) - 8.8
        return np.isfinite(soft) & np.isfinite(w1) & (w1 < line)

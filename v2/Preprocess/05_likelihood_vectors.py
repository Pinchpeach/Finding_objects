#!/usr/bin/env python3
"""Stage 5: fuse coarse evidence into STAR/GALAXY/QSO scores.

Fusion is a linear log-odds model: each evidence item contributes
``w[rule:class][target] * logit(score)`` to every coarse class.  Without a
fitted model the weights are the hand-set priors in ``WEIGHT`` applied to the
item's target group, and the outputs are normalized evidence scores, not
calibrated probabilities.  When ``fusion_weights.json`` exists, weights for
evidence keys with independent training support (benchmark train split) are
replaced by fitted multinomial-logistic coefficients, and the abstention
threshold is the one chosen on the calibration split; keys without support
keep their prior weights.  See v2/benchmark/fit_fusion_weights.py.

Hybrid fusion (2.25.0): when the model names a ``gbm`` tree file, the fitted
part is a gradient-boosted tree model over the same supported keys (absent
evidence = missing, not 0), so evidence can interact -- e.g. a colour can
count differently for resolved and unresolved sources, which a linear sum
cannot express.  Unsupported keys are still added with their prior weights
on top of the trees' log-odds.  The result is blended (geometric mean,
weight ``blend``) with the linear model of the same fit.  The trees are
evaluated with numpy only (``ls_gbm.raw_scores``), as for LS-GBM-001.
"""

from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import importlib.util as _tio_u

_tio_s = _tio_u.spec_from_file_location(
    "v2_table_io", Path(__file__).resolve().parents[1] / "Preprocess" / "table_io.py"
)
TABLE_IO = _tio_u.module_from_spec(_tio_s)
_tio_s.loader.exec_module(TABLE_IO)
_gbm_s = _tio_u.spec_from_file_location("v2_ls_gbm_trees", Path(__file__).resolve().parent / "ls_gbm.py")
TREES = _tio_u.module_from_spec(_gbm_s)
_gbm_s.loader.exec_module(TREES)
_qo_s = _tio_u.spec_from_file_location("v2_qso_options", Path(__file__).resolve().parent / "qso_options.py")
QSO_OPT = _tio_u.module_from_spec(_qo_s)
_qo_s.loader.exec_module(QSO_OPT)
CLASSES = ("STAR", "GALAXY", "QSO")
WEIGHT = {"direct_probability": 1.0, "catalog_label": 1.5, "continuous_score": 0.35, "binary_evidence": 0.35}
MIN_CONFIDENCE = 0.50
MIN_MARGIN = 0.10
# EXTRAGALACTIC (astrometric null, mid-IR AGN colour) cannot separate
# galaxies from quasars; POINT_SOURCE (unresolved morphology) cannot separate
# stars from quasars. Together they single out QSO.
GROUPS = {"EXTRAGALACTIC": ("GALAXY", "QSO"), "POINT_SOURCE": ("STAR", "QSO")}
# Inside a large galaxy's D26 ellipse, survey detections are mostly pieces of
# that galaxy (HII regions, arms) rather than independent objects; only a
# Gaia-confirmed foreground star is classified there.
HOST_RADIUS = 1.0
# Minimum independent objects (with evidence, outside large-galaxy hosts) needed
# to re-estimate the field's class mix.
FIELD_PRIOR_MIN_OBJECTS = 50
CONFLICT_RESOLVED_P = 0.99
# A Gaia parallax or proper motion measured at >= 10 sigma is physically
# incompatible with a galaxy or a quasar: Gaia DR3 quasars scatter about
# zero with normalised parallax/proper-motion widths of ~1.05-1.1
# (Lindegren et al. 2021, A&A 649, A2; Gaia-CRF3, Klioner et al. 2022), so
# 10 sigma stays decisive even if the faint-end errors are underestimated by
# ~1.5 (El-Badry, Rix & Heintz 2021). Benchmarks: of the objects at >= 10
# sigma, 99.6% (SDSS, n = 2989) and 99.0% (DESI, n = 518) are spectroscopic
# stars; the rest are mis-associations already predicted STAR. Such an object
# is classified STAR even when other (photometric) evidence conflicts.
DECISIVE_MOTION_SIGMA = 10.0
DECISIVE_MIN_RELIABILITY = 0.8  # Gaia astrometry quality (RUWE <= ~1.75) and association
MODEL_PATH = Path(__file__).resolve().parent / "fusion_weights.json"
# Stage-4 rules measuring a significant Gaia parallax / proper motion.
GAIA_MOTION_RULES = frozenset({"AST-GAL-001", "AST-GAL-002"})


def _or1(v):
    return 1.0 if v is None else v


def evidence_features(items):
    """Map evidence items to {"RULE:CLASS": logit(score)} plus their kinds."""
    x = {}
    kinds = {}
    for e in items:
        c = e.get("class")
        if e.get("kind") == "linear_feature":
            # Continuous feature (e.g. a colour): enters the model linearly and
            # carries weight only when a fitted model provides one.
            try:
                x[f"{e.get('rule_id')}:{c}"] = float(e.get("value"))
                kinds[f"{e.get('rule_id')}:{c}"] = "linear_feature"
            except (TypeError, ValueError):
                pass
            continue
        if c in {"WD", "BINARY"}:
            c = "STAR"
        if c not in GROUPS and c not in CLASSES:
            continue
        # Reliability discounts the evidence in log-odds space: weight x
        # logit(raw score).  Folding it into the score instead (logit of
        # raw x reliability) turns an unreliable claim into strong evidence
        # *against* the class (a resolved Tractor model with near-zero
        # association reliability gave p_star = 1.00 for galaxies).
        try:
            raw = e.get("raw_score")
            if raw is not None:
                r = min(max(float(raw), 0.01), 0.99)
                rel = float(_or1(e.get("reliability"))) * float(_or1(e.get("association_reliability")))
                v = max(0.0, min(1.0, rel)) * math.log(r / (1 - r))
            else:
                s = min(max(float(e.get("score", 0)), 0.01), 0.99)
                v = math.log(s / (1 - s))
        except (TypeError, ValueError):
            continue
        key = f"{e.get('rule_id')}:{c}"
        x[key] = x.get(key, 0.0) + v
        kinds[key] = e.get("kind")
    return x, kinds


def prior_coef(key, kind):
    if kind == "linear_feature":
        return {t: 0.0 for t in CLASSES}
    c = key.rsplit(":", 1)[1]
    w = WEIGHT.get(kind, 0.25)
    return {t: (w if t in GROUPS.get(c, (c,)) else 0.0) for t in CLASSES}


def load_model(path=MODEL_PATH):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _add_prior(logit, key, kind, v):
    """Unfitted rules are one-sided support: a low-confidence claim (e.g. a
    catalogue label with poor association reliability) is weak support, not
    evidence against the class."""
    w = prior_coef(key, kind)
    v = max(v, 0.0)
    for t in CLASSES:
        logit[t] += w.get(t, 0.0) * v


def fuse(items, model=None):
    return _fuse_linear(*evidence_features(items), model)


def _fuse_linear(x, kinds, model):
    """Linear log-odds fusion of ``evidence_features`` output."""
    coef = (model or {}).get("coef", {})
    # The fitted intercept is the baseline of the fitted feature set; with
    # none of those features present (e.g. only SIMBAD/NED labels, which use
    # prior weights) it would be an extrapolation, so equal odds are used.
    fitted = any(k in coef for k in x)
    logit = {c: float((model or {}).get("intercept", {}).get(c, 0.0)) if fitted else 0.0 for c in CLASSES}
    used = 0
    for key, v in x.items():
        w = coef.get(key)
        if w is None:
            _add_prior(logit, key, kinds[key], v)
        else:
            for t in CLASSES:
                logit[t] += w.get(t, 0.0) * v
        # A continuous feature without a fitted weight carries no evidence.
        used += int(kinds[key] != "linear_feature" or key in coef)
    return _softmax(logit), used


def _softmax(logit):
    m = max(logit.values())
    p = {c: math.exp(v - m) for c, v in logit.items()}
    z = sum(p.values())
    return {c: p[c] / z for c in CLASSES}


def _gbm(model, base_dir=None):
    """(spec, trees, class order) of the model's tree part, or None (no tree
    file: the linear coefficients of the same fit are used instead)."""
    g = (model or {}).get("gbm")
    if not g:
        return None
    trees = TREES.load_model(str(Path(base_dir or MODEL_PATH.parent) / g["file"]))
    if trees is None:
        return None
    names = [str(c) for c in trees["classes"]]
    return g, trees, [names.index(c) for c in CLASSES]


def fuse_many(item_lists, model=None, base_dir=None):
    """``fuse`` for many objects; the tree part is evaluated in one batch."""
    gb = _gbm(model, base_dir)
    if gb is None:
        return [fuse(items, model) for items in item_lists]
    spec, trees, order = gb
    keys = spec["keys"]
    col = {k: j for j, k in enumerate(keys)}
    feats = [evidence_features(items) for items in item_lists]
    X = np.full((len(feats), len(keys)), np.nan)
    for r, (x, _) in enumerate(feats):
        for k, v in x.items():
            j = col.get(k)
            if j is not None:
                X[r, j] = v
    fitted = np.isfinite(X).any(axis=1)
    Z = np.zeros((len(feats), len(CLASSES)))
    if fitted.any():
        Z[fitted] = TREES.raw_scores(X[fitted], trees)[:, order] / float(spec.get("temperature", 1.0))
    a = float(spec.get("blend", 1.0))
    out = []
    for r, (x, kinds) in enumerate(feats):
        # Without any supported key the trees' baseline would be an
        # extrapolation (as the linear intercept), so odds start equal.
        logit = dict(zip(CLASSES, Z[r] if fitted[r] else np.zeros(len(CLASSES))))
        used = 0
        for key, v in x.items():
            if key in col:
                used += 1
                continue
            _add_prior(logit, key, kinds[key], v)
            used += int(kinds[key] != "linear_feature")
        p = _softmax(logit)
        if a < 1.0:
            # Geometric mean with the sign-constrained linear model of the same
            # fit (product of experts): the trees add interactions, the linear
            # part keeps its predictable direction for evidence combinations
            # rare in training (Gaia-only faint stars, 2.25.0 measurement).
            q, _ = _fuse_linear(x, kinds, model)
            p = _softmax({c: (1 - a) * math.log(max(q[c], 1e-300)) + a * math.log(max(p[c], 1e-300)) for c in CLASSES})
        out.append((p, used))
    return out


# Astrometry of a source whose Gaia BP/RP flux excess is > 5 sigma from that
# of an isolated point source (Riello et al. 2021 C*; ``cstar_sigma`` from
# Stage 4) belongs to an extended or blended source -- e.g. a galaxy nucleus,
# where spurious 14-sigma "proper motions" occur (NGC 4522, 2.22.0) -- and is
# not used to override the in-galaxy status or the fusion.
CSTAR_MAX_SIGMA = 5.0


def _point_like(e):
    try:
        return float(e.get("cstar_sigma")) <= CSTAR_MAX_SIGMA
    except (TypeError, ValueError):
        return True  # not measured: keep the old behaviour


def _gaia_foreground_star(items):
    """Significant Gaia parallax or proper motion (S/N >= 5; Stage-4 score >= 0.5)
    of a point-like source."""
    return any(
        e.get("rule_id") in GAIA_MOTION_RULES and float(e.get("raw_score", 0)) >= 0.5 and _point_like(e) for e in items
    )


# The C* gate guards against spurious *proper motions* of blended or
# extended sources (the NGC 4522 nucleus, 2.22.0).  Inside bright nebulae
# (ONC, M8) the BP/RP excess of genuine young stars is raised by the nebular
# background, so C* > 5 there too, and the gate hid their parallaxes
# (200-region validation, 2026-10-24: ONC 64 % correct, 27 % UNKNOWN).  A
# parallax at >= 15 sigma is kept decisive whatever C*: of the 152 C*-failing
# truth objects with such a parallax (reliability and association >= 0.8),
# 151 are spectroscopic stars (the other, a galaxy, was UNKNOWN before), and
# the Gaia quasar parallaxes scatter with a width of ~1.1 (Lindegren et al.
# 2021), so 15 sigma also covers an error underestimate of ~1.5 for blended
# faint sources (El-Badry, Rix & Heintz 2021; Fabricius et al. 2021, A&A
# 649, A5).  Proper motion keeps the C* gate.
DECISIVE_PARALLAX_NONPOINT_SIGMA = 15.0


def _decisive_motion(items):
    """Gaia parallax or proper motion at >= DECISIVE_MOTION_SIGMA with a good
    astrometric solution and a reliable association (a parallax of a
    non-point-like source only at >= DECISIVE_PARALLAX_NONPOINT_SIGMA)."""
    for e in items:
        if e.get("rule_id") not in GAIA_MOTION_RULES:
            continue
        if _point_like(e):
            need = DECISIVE_MOTION_SIGMA
        elif e.get("rule_id") == "AST-GAL-001":
            need = DECISIVE_PARALLAX_NONPOINT_SIGMA
        else:
            continue
        try:
            if (
                float(e.get("value")) >= need
                and float(e.get("reliability", 0)) >= DECISIVE_MIN_RELIABILITY
                and float(e.get("association_reliability", 0)) >= DECISIVE_MIN_RELIABILITY
            ):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _spectroscopic(items):
    """Pipeline spectral class of this position (SPC-* rules, e.g. SDSS
    CLASS with ZWARNING == 0; Bolton et al. 2012, AJ 144, 144).  A spectrum
    classifies the light in its own fibre, so it stays valid inside a large
    galaxy: the nucleus or an HII region gives GALAXY, a foreground star STAR."""
    return any(str(e.get("rule_id", "")).startswith("SPC-") and float(e.get("raw_score", 0) or 0) >= 0.5 for e in items)


def estimate_field_prior(P, train_prior, iters=200, tol=1e-7):
    """EM re-estimation of class priors under label shift.

    Saerens, Latinne & Decaestecker (2002, Neural Computation 14, 21): with
    posteriors calibrated under ``train_prior``, iterate
    pi <- mean_i p_i(pi), p_i(pi) ~ p_i * pi / train_prior.
    """
    base = np.asarray(train_prior, dtype=float)
    pi = base.copy()
    for _ in range(iters):
        Q = P * pi / base
        Q /= Q.sum(axis=1, keepdims=True)
        new = Q.mean(axis=0)
        done = np.abs(new - pi).max() < tol
        pi = new
        if done:
            break
    return pi


# Galactic-latitude class prior (2.35.0).  The fusion was trained and tested
# on SDSS/DESI objects, none of them at |b| < 10 deg and 21 of 23,000 at
# |b| < 20 deg, so it assumes high-latitude class odds.  Toward the plane the
# star counts rise roughly as csc|b| (plane-parallel disc; Bahcall & Soneira
# 1980) while extragalactic counts fall (extinction), and Gaia's
# zero-motion/zero-parallax test passes distant disc stars, most of all toward
# the anticentre: a field at l = 182, b = +2 had 616 "QSO" among G ~ 20 stars
# (2026-10-21).  Gaia DR3 source classification uses a class prior that varies
# with latitude for this reason (Hughes, Bailer-Jones & Jamal 2022, A&A 668,
# A99; Bailer-Jones et al. 2024), and quasar catalogues cut |sin b| <= 0.1.
# Here the GALAXY and QSO odds are scaled by the star-count ratio
# sin|b| / sin(20 deg) below 20 deg (extinction ignored, i.e. conservative);
# at |b| >= 20 deg, where all benchmarks lie, nothing changes.
LATITUDE_PRIOR_DEG = 20.0


def latitude_factor(df: pd.DataFrame) -> np.ndarray:
    """Per-row factor (0, 1] on the GALAXY and QSO odds from Galactic latitude; 1 without a position."""
    ra = pd.to_numeric(df.get("ra", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    dec = pd.to_numeric(df.get("dec", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    a, d = np.radians(ra), np.radians(dec)
    # sin b = n_gp . r, north Galactic pole at ICRS (192.85948, +27.12825) deg
    # (Hipparcos catalogue, ESA 1997, vol. 1 sec. 1.5.3)
    sinb = np.abs(-0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d))
    f = np.minimum(1.0, sinb / np.sin(np.radians(LATITUDE_PRIOR_DEG)))
    return np.where(np.isfinite(f), np.maximum(f, 1e-3), 1.0)


# Magellanic Cloud prior (2.37.0).  Inside the LMC and SMC the star counts
# reach 10^6 deg^-2 (Gaia DR3 sources in the 200-region validation: lmc_bar
# 1.3e6, smc_bar 1.1e6) against ~10^4 at the same latitudes elsewhere, while
# background quasars stay at ~10^2 deg^-2, so a photometric QSO there is
# almost always a faint Cloud star: the blind run predicted 2,900-5,900 QSO
# per 6' field (~10^5 deg^-2).  Gaia DR3 meets the same contamination: 38 %
# of its DSC quasar labels lie in the LMC and 6.4 % in the SMC (Delchambre et
# al. 2023, A&A 674, A31), and excluding generous regions around the Clouds
# removes 41 % of the 6.6 million qso_candidates (Gaia Collaboration,
# Bailer-Jones et al. 2023, A&A 674, A41); Quaia adds a G-W1 / W1-W2 cut
# against Cloud stars (Storey-Fisher et al. 2024, ApJ 964, 69).  Behind the
# Clouds there are ~25 quasars deg^-2 at I < 20 against > 10^6 stars deg^-2
# (Kozlowski et al. 2013, ApJ 775, 92).  (Corrected in 2.37.1; checked
# against the papers' text, v2/LITERATURE_QSO.md.)
# Two factors on the GALAXY and QSO odds, never above 1:
#   * prior: the local star-count excess rho_ref / rho(R), rho(R) =
#     rho0 exp(-R / h), fitted to the Gaia counts of the 11 Cloud fields
#     (LMC rho0 = 1.2e6, h = 1.97 deg; SMC 1.09e6, 0.66 deg; scatter 0.2 dex)
#     with rho_ref the median count of the |b| = 25-35 (LMC, b = -33) and
#     35-45 deg (SMC, b = -44) fields away from the Clouds (1.2e4, 6.6e3).
#     It reaches 1 at R = 9.1 deg (LMC) and 3.4 deg (SMC), the usual extent
#     of their discs;
#   * proper motion: the likelihood ratio of the Gaia proper motion under
#     "Cloud member" (systemic motion with an internal spread) and
#     "background source" (zero; errors scaled by 1.1 as for Gaia-CRF3
#     quasars, Lindegren et al. 2021).  Systemic motions (mas/yr): the
#     linear fits at the Clouds' centres of Gaia Collaboration, Luri et al.
#     2021 (A&A 649, A7, Table 4; checked against the paper text, 2.38.0):
#     LMC (1.871, 0.391), SMC (0.686, -1.237); spreads 0.4 (LMC disc
#     rotation ~0.3 mas/yr at 50 kpc; their LMC sample sigma 0.45/0.64) and
#     0.3 (SMC sample sigma 0.37/0.30).  2.37.0 used (1.88, 0.31) and
#     (0.82, -1.21) from the range of DR1-EDR3/HST values.
#     A motion consistent with zero but not with the Cloud (bright
#     quasars) raises the odds again, at most back to the fusion's.
MAGELLANIC = (
    # name, centre (deg), rho0, scale length (deg), rho_ref (deg^-2), systemic PM, internal spread (mas/yr)
    ("LMC", 80.89, -69.76, 1.2e6, 1.97, 1.2e4, (1.871, 0.391), 0.4),
    ("SMC", 13.19, -72.83, 1.09e6, 0.66, 6.6e3, (0.686, -1.237), 0.3),
)
MAGELLANIC_PM_ERROR_SCALE = 1.1
MAGELLANIC_MIN_RELIABILITY = 0.8


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def magellanic_region(df: pd.DataFrame) -> np.ndarray:
    """True where the Magellanic star-count prior is below 1 (inside the Clouds' discs)."""
    ra, dec = _col(df, "ra"), _col(df, "dec")
    inside = np.zeros(len(df), bool)
    for _, ra0, dec0, rho0, h, rho_ref, _, _ in MAGELLANIC:
        c = np.sin(np.radians(dec)) * np.sin(np.radians(dec0)) + np.cos(np.radians(dec)) * np.cos(
            np.radians(dec0)
        ) * np.cos(np.radians(ra - ra0))
        r = np.degrees(np.arccos(np.clip(c, -1, 1)))
        inside |= np.isfinite(r) & (rho_ref / (rho0 * np.exp(-r / h)) < 1.0)
    return inside


def magellanic_factor(df: pd.DataFrame, systemic=None) -> np.ndarray:
    """Per-row factor (0, 1] on the GALAXY and QSO odds inside the Magellanic Clouds; 1 elsewhere.

    ``systemic`` = {"LMC": (pmra, pmdec), "SMC": ...} overrides the adopted motions."""
    ra, dec = _col(df, "ra"), _col(df, "dec")
    f = np.ones(len(df))
    pa, pd_ = _col(df, "gaia_dr3__pmra"), _col(df, "gaia_dr3__pmdec")
    ea, ed = (MAGELLANIC_PM_ERROR_SCALE * _col(df, c) for c in ("gaia_dr3__pmra_error", "gaia_dr3__pmdec_error"))
    rel = np.fmin(
        np.nan_to_num(_col(df, "catalog_confidence_gaia_astrometry"), nan=0.0),
        np.nan_to_num(_col(df, "association_confidence__gaia_dr3"), nan=1.0),
    )
    ok = np.isfinite(pa + pd_ + ea + ed) & (ea > 0) & (ed > 0) & (rel >= MAGELLANIC_MIN_RELIABILITY)
    for name, ra0, dec0, rho0, h, rho_ref, (ma, md), s in MAGELLANIC:
        ma, md = (systemic or {}).get(name, (ma, md))
        c = np.sin(np.radians(dec)) * np.sin(np.radians(dec0)) + np.cos(np.radians(dec)) * np.cos(
            np.radians(dec0)
        ) * np.cos(np.radians(ra - ra0))
        r = np.degrees(np.arccos(np.clip(c, -1, 1)))
        prior = np.minimum(1.0, rho_ref / (rho0 * np.exp(-r / h)))
        inside = np.isfinite(r) & (prior < 1.0)
        if not inside.any():
            continue
        # ln L(member) - ln L(zero motion), independent Gaussian components
        va, vd = ea**2 + s**2, ed**2 + s**2
        with np.errstate(invalid="ignore", divide="ignore"):
            lnlr = (
                -0.5 * ((pa - ma) ** 2 / va + (pd_ - md) ** 2 / vd)
                - 0.5 * np.log(va * vd)
                + 0.5 * ((pa / ea) ** 2 + (pd_ / ed) ** 2)
                + 0.5 * np.log(ea**2 * ed**2)
            )
        lnlr = np.where(ok, np.clip(lnlr, -700, 700), 0.0)
        g = np.minimum(1.0, prior * np.exp(-lnlr))
        f = np.where(inside, np.minimum(f, g), f)
    return np.maximum(f, 1e-6)


def run(evidence, out, model_path=MODEL_PATH, min_confidence=None, field_prior=False, options=None):
    opts = QSO_OPT.parse(options)
    model = load_model(model_path)
    min_conf = float(model.get("min_confidence", MIN_CONFIDENCE)) if model else MIN_CONFIDENCE
    if min_confidence is not None:
        min_conf = float(min_confidence)  # caller trades coverage for precision
    min_margin = float(model.get("min_margin", MIN_MARGIN)) if model else MIN_MARGIN
    df = TABLE_IO.read_table(evidence)
    raw_series = df["evidence_json"] if "evidence_json" in df else pd.Series(["[]"] * len(df))
    host_r = (
        pd.to_numeric(df["host_elliptical_radius"], errors="coerce")
        if "host_elliptical_radius" in df
        else pd.Series(float("nan"), index=df.index)
    )
    item_lists = []
    for raw in raw_series:
        try:
            item_lists.append(json.loads(raw) if isinstance(raw, str) else [])
        except (json.JSONDecodeError, TypeError):
            item_lists.append([])
    # Gaia DSC is ignored inside the Magellanic Clouds, where 38 % of its
    # quasar labels lie (Delchambre et al. 2023); 200-field replay (2.39.0):
    # Magellanic QSO predictions 5,657 -> 3,162, other fields unchanged.
    for i in np.flatnonzero(magellanic_region(df)):
        item_lists[i] = [e for e in item_lists[i] if e.get("rule_id") != "DSC-001"]
    fused = fuse_many(item_lists, model, Path(model_path).parent)
    rows = []
    for items, hr, (p, used) in zip(item_lists, host_r, fused):
        strong = set()
        for e in items:
            c = e.get("class")
            if c in {"WD", "BINARY"}:
                c = "STAR"
            try:
                s = float(e.get("score", 0))
            except (TypeError, ValueError):
                s = 0
            # Colour-kNN fractions are soft evidence for the fitted fusion,
            # not hard claims (same rule as Stage 4's evidence_conflict).
            if c in CLASSES and s >= 0.8 and not str(e.get("rule_id", "")).endswith(("-CKNN-001", "-GBM-001")):
                strong.add(c)
        conflict = bool(items) and len(strong) > 1
        in_host = hr < HOST_RADIUS and not _gaia_foreground_star(items) and not _spectroscopic(items)
        rows.append((np.array([p[c] for c in CLASSES]), used, conflict, in_host, _decisive_motion(items)))
    P = np.array([r[0] for r in rows]).reshape(len(rows), len(CLASSES))
    # Field-prior adjustment needs calibrated posteriors (fitted model) and
    # enough independent objects in the field to estimate the class mix.
    eligible = np.array(
        [used > 0 and not conflict and not in_host for _, used, conflict, in_host, _ in rows], dtype=bool
    )
    train_prior = [float((model or {}).get("training_prior", {}).get(c, 1 / len(CLASSES))) for c in CLASSES]
    # The EM estimate assumes pure label shift with calibrated posteriors.
    # Real fields also shift which evidence exists (depth, footprint, archive
    # outages), and on five DESI-checked fields applying it lowered accuracy
    # in four; it is therefore estimated and reported, but applied only on
    # request (``field_prior=True``).
    estimable = bool(model) and int(eligible.sum()) >= FIELD_PRIOR_MIN_OBJECTS
    prior = estimate_field_prior(P[eligible], train_prior) if estimable else np.array(train_prior)
    adjust = estimable and bool(field_prior)
    Q = P * (prior if adjust else np.array(train_prior)) / np.array(train_prior)
    # Local stellar-density prior (2.39.0): the Gaia source density at the
    # object (10th neighbour) against the training sky, min(1, rho_ref/rho)
    # -- a continuous position prior as in Jamal & Bailer-Jones 2024 and
    # Hughes et al. 2022 that covers the plane, the bulge, clusters and the
    # Clouds alike.  200-field replay: Stage-5 accuracy 96.12 -> 96.16 %,
    # QSO predictions -16 % outside and -59 % inside the Clouds.  Where it
    # cannot be measured (small searches, < 11 Gaia sources) the latitude and
    # Magellanic priors above are used.
    dens = QSO_OPT.density_prior(df)
    lat = np.where(np.isfinite(dens), dens, latitude_factor(df) * magellanic_factor(df))
    Q[:, [CLASSES.index("GALAXY"), CLASSES.index("QSO")]] *= lat[:, None]
    qf = np.ones(len(df))
    # Magnitude prior on the QSO odds (2.40.0): the fusion was trained with
    # about equal classes, the sky has 0.07-0.8 % quasars per r bin
    # (natural_purity, 2.36.0), so the QSO odds are scaled by the square
    # root of the real-sky / training odds (a tempered label-shift prior,
    # Saerens et al. 2002; number-count priors as in Bovy et al. 2011 and
    # Jamal & Bailer-Jones 2024).  2.39.0 200-field replay: Stage-5 accuracy
    # 96.21 -> 96.31 %, QSO precision 79.5 -> 86.9 %, recall 94.4 -> 90.9 %;
    # QSO-rich benchmarks lose (SDSS -0.75, DESI -3.4 %p).  Option c1a
    # applies the full prior.
    qf *= QSO_OPT.magnitude_prior(df, half="c1a" not in opts)
    # DESI QSO preselection W1 < 22.3 and W2 < 22.3 AB (Chaussidon et al.
    # 2023, Sect. 3; removes stars faint in WISE, e.g. the Sagittarius
    # stream): QSO odds x VETO otherwise (2.39.0; fields +0.09 %p, SDSS
    # -0.10 %p, DESI +0.10 %p).
    qf *= np.where(QSO_OPT.desi_wise_cut(df), QSO_OPT.VETO, 1.0)
    if "c4" in opts:
        qf *= np.where(QSO_OPT.quaia_fail(df), QSO_OPT.VETO, 1.0)
    # An X-ray source on the stellar side of the X-ray-flux / W1 relation
    # (Salvato et al. 2018, MNRAS 473, 4937, Eq. 2; coronal stars are bright
    # in W1 for their X-ray flux): QSO odds x VETO (2.38.0; SDSS 98.69 ->
    # 98.74 % with the Mahalanobis motion test, DESI unchanged).
    qf *= np.where(QSO_OPT.xray_star_side(df), QSO_OPT.VETO, 1.0)
    Q[:, CLASSES.index("QSO")] *= qf
    qso_min = QSO_OPT.desi_threshold(df) if "c3b" in opts else np.zeros(len(df))
    faint = QSO_OPT.r_mag(df) > 22 if "c8" in opts else np.zeros(len(df), bool)
    Q = Q / Q.sum(axis=1, keepdims=True) if len(Q) else Q
    labels = []
    confidence = []
    margins = []
    statuses = []
    best_candidates = []
    best_candidate_scores = []
    for q, (_, used, conflict, in_host, moving), qmin, qfaint in zip(Q, rows, qso_min, faint):
        order = np.argsort(-q)
        conf = float(q[order[0]])
        margin = conf - float(q[order[1]])
        top = CLASSES[order[0]]
        # Inside a large galaxy the host status is the most informative one,
        # with or without evidence (e.g. Legacy Surveys DUP sources there).
        if in_host:
            label = "UNKNOWN"
            status = "WITHIN_LARGE_GALAXY"
        elif used == 0:
            label = "UNKNOWN"
            status = "NO_EVIDENCE"
        elif moving:
            # Confidence = the rule's benchmark precision (>= 0.99), or the
            # fused STAR probability when that is higher.
            label = "STAR"
            status = "CLASSIFIED"
            top = "STAR"
            conf = max(float(q[CLASSES.index("STAR")]), 0.99)
            margin = max(0.0, conf - max(float(v) for c, v in zip(CLASSES, q) if c != "STAR"))
        # Strong evidence pointing at different classes abstains unless the
        # fitted fusion resolves it decisively (benchmark held-out conflicts
        # with p >= 0.99: 19/19 correct; at p >= 0.9: 91-100%).
        elif conflict and (not model or conf < CONFLICT_RESOLVED_P):
            label = "UNKNOWN"
            status = "CONFLICT"
        elif conf < min_conf or margin < min_margin or (top == "QSO" and (conf < qmin or qfaint)):
            label = "UNKNOWN"
            status = "LOW_CONFIDENCE"
        else:
            label = top
            status = "CLASSIFIED"
        labels.append(label)
        confidence.append(conf)
        margins.append(margin)
        statuses.append(status)
        if used == 0:
            best_candidates.append("UNKNOWN")
            best_candidate_scores.append(float("nan"))
        else:
            best_candidates.append(top)
            best_candidate_scores.append(conf)
    result_columns = {}
    for i, c in enumerate(CLASSES):
        result_columns[f"likelihood_{c.lower()}"] = Q[:, i] if len(Q) else []
        result_columns[f"p_{c.lower()}"] = Q[:, i] if len(Q) else []  # legacy alias
        result_columns[f"p_{c.lower()}_training_prior"] = P[:, i] if len(P) else []
        result_columns[f"field_prior_{c.lower()}"] = [float(prior[i])] * len(df)
    result_columns.update(
        {
            "coarse_probability_calibrated": [bool(model)] * len(df),
            "coarse_prior_adjusted": [adjust] * len(df),
            "coarse_score_semantics": [
                (model or {}).get("semantics", "normalized evidence likelihood; not a calibrated posterior probability")
                + ("; class priors re-estimated for this field (Saerens+2002 EM)" if adjust else "")
            ]
            * len(df),
            "primary_class": labels,
            "primary_confidence": confidence,
            "primary_margin": margins,
            "classification_status": statuses,
            "best_candidate_class": best_candidates,
            "best_candidate_probability": best_candidate_scores,
        }
    )
    df = pd.concat([df, pd.DataFrame(result_columns, index=df.index)], axis=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(
        f"[OK] {len(df)} sources -> {out}"
        + (
            f"; field prior estimate {dict(zip(CLASSES,(round(float(x),3) for x in prior)))}"
            + (" (applied)" if adjust else " (not applied)")
            if estimable
            else ""
        )
    )
    return out


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, default=root / "evidence.csv")
    p.add_argument("--out", type=Path, default=root / "likelihood_vectors.csv")
    p.add_argument(
        "--min-confidence",
        type=float,
        help="override the abstention threshold (see COARSE_BENCHMARK_RESULTS.md for coverage/accuracy)",
    )
    p.add_argument(
        "--field-prior",
        action="store_true",
        help="apply the EM field class-prior re-estimate (Saerens+2002) to the labels",
    )
    a = p.parse_args()
    run(a.evidence, a.out, min_confidence=a.min_confidence, field_prior=a.field_prior)


if __name__ == "__main__":
    main()

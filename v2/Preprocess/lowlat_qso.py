"""Switches that limit the QSO label at low Galactic latitude (2.61.2).  Every switch is off by default.

At |b| < 20 deg most of what the classifier calls QSO is not a quasar (benchmark/lowlat_qso/LOWLAT_QSO.md: 170 objects that are
not sample quasars in 1.18 deg^2, 144 deg^-2, against 5-8 deg^-2 quasars expected to i ~ 19.3 at high latitude).  The 2.61.1
dissection (WORK_REPORT_2026-11-27b.md, LITERATURE_LOWLAT_QSO_2026-11-27.md) found that 45 % of them rest on one survey (Legacy
Surveys colours alone 28 %, AllWISE colours alone 16 %), that the Gaia proper motion is no help for the faint ones (all 33 with a
Gaia row pass the cut), and that the AllWISE colour rules are applied where the literature built them only for high latitude.

``V2_LOWLAT_QSO`` is a comma list of

  surveys2 / surveys3   a QSO label needs measurements from at least 2 / 3 different surveys (annotation catalogues -- NED,
                        SIMBAD, ... -- do not count); otherwise the object is UNKNOWN (status LOW_CONFIDENCE, the way a
                        faint QSO is held back).  Every quasar selection of the literature uses two surveys or more
                        (PS1 + AllWISE: Fu et al. 2021; Gaia + unWISE: Storey-Fisher et al. 2024)
  pm                    the Gaia proper motion must pass the Fu et al. (2021, Sec. 5.3) cut log10 f_PM0 >= -4 (no Gaia proper
                        motion: no restriction), as Quaia and Gaia-CRF3 use the astrometry to remove stars
  wise_footprint        WISE-AGN-001 (Stern et al. 2012, W1-W2 >= 0.8: reliability 95 % in COSMOS, "in a high Galactic latitude
                        survey" stars are no contaminant) only where the Assef et al. (2018) R90 rule is defined: |b| > 10 deg and
                        more than 30 deg from the Galactic Centre
  wise_second           WISE-AGN-001 and WISE-AGN-R90-001 need another survey than AllWISE at |b| < ``V2_LOWLAT_QSO_ABSB``

``V2_LOWLAT_QSO_ABSB`` (default 20): the latitude below which the switches act.  Nothing changes at |b| >= this value or where a
position is missing.  The literature behind the numbers is in LITERATURE_LOWLAT_QSO_2026-11-27.md.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

OPTIONS = ("surveys2", "surveys3", "pm", "wise_footprint", "wise_second")
# catalogues that identify or annotate a source, not measure it (01_source_association.ANNOTATION_CATALOGS)
ANNOTATION = frozenset({"NED", "SIMBAD", "Roma-BZCAT", "Suh 2021 AGB Catalog", "HASH PN Catalog", "Acker PN Spectroscopy",
                        "ATNF Pulsar Catalog", "Galaxy Zoo DESI"})  # fmt: skip
PM_LOG10_CUT = -4.0  # Fu et al. 2021, Sec. 5.3
PM_K, PM_SIGMA_BRIGHT, PM_SIGMA_FAINT = 1.08, 0.032, 0.066  # mas/yr (Lindegren et al. 2018 external uncertainty, as Fu et al.)


def options() -> frozenset:
    raw = os.environ.get("V2_LOWLAT_QSO", "").strip()
    got = [t.strip() for t in raw.split(",") if t.strip()]
    bad = [t for t in got if t not in OPTIONS]
    if bad:
        raise ValueError(f"V2_LOWLAT_QSO={raw!r}: unknown {bad}; known: {list(OPTIONS)}")
    if "surveys2" in got and "surveys3" in got:
        raise ValueError("V2_LOWLAT_QSO: surveys2 and surveys3 exclude each other")
    return frozenset(got)


def max_abs_b() -> float:
    raw = os.environ.get("V2_LOWLAT_QSO_ABSB", "").strip()
    if not raw:
        return 20.0
    v = float(raw)
    if not (math.isfinite(v) and 0.0 <= v <= 90.0):
        raise ValueError(f"V2_LOWLAT_QSO_ABSB={raw!r}: expected a number in [0, 90]")
    return v


def galactic_latitude(ra, dec) -> np.ndarray:
    """b in degrees (ICRS -> Galactic rotation of ESA 1997, vol. 1)."""
    r, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    gz = -0.8676661490 * np.cos(d) * np.cos(r) - 0.1980763734 * np.cos(d) * np.sin(r) + 0.4559837762 * np.sin(d)
    return np.degrees(np.arcsin(np.clip(gz, -1.0, 1.0)))


def galactic_centre_distance(ra, dec) -> np.ndarray:
    r, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    gx = -0.0548755604 * np.cos(d) * np.cos(r) - 0.8734370902 * np.cos(d) * np.sin(r) - 0.4838350155 * np.sin(d)
    return np.degrees(np.arccos(np.clip(gx, -1.0, 1.0)))


def low_latitude(df: pd.DataFrame) -> np.ndarray:
    ra = pd.to_numeric(df.get("ra", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    dec = pd.to_numeric(df.get("dec", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    with np.errstate(invalid="ignore"):
        return np.isfinite(ra) & np.isfinite(dec) & (np.abs(galactic_latitude(ra, dec)) < max_abs_b())


def n_surveys(catalogs: pd.Series) -> np.ndarray:
    """Number of different measurement catalogues of each object."""
    out = []
    for c in catalogs.fillna("").astype(str):
        names = {x for x in c.split("|") if x and x not in ANNOTATION}
        out.append(len(names))
    return np.array(out, dtype=int)


def log10_fpm0(df: pd.DataFrame) -> np.ndarray:
    """log10 of the density of zero proper motion of Fu et al. (2021), Eq. 10 (NaN without a Gaia proper motion)."""

    def col(name):
        return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)

    a, d = col("gaia_dr3__pmra"), col("gaia_dr3__pmdec")
    ea, ed, rho, g = col("gaia_dr3__pmra_error"), col("gaia_dr3__pmdec_error"), col("gaia_dr3__pmra_pmdec_corr"), col("gaia_dr3__phot_g_mean_mag")
    rho = np.where(np.isfinite(rho), np.clip(rho, -0.999, 0.999), 0.0)
    ss = np.where(np.isfinite(g) & (g < 13), PM_SIGMA_BRIGHT, PM_SIGMA_FAINT)
    with np.errstate(invalid="ignore", divide="ignore"):
        sx, sy = np.sqrt((PM_K * ea) ** 2 + ss**2), np.sqrt((PM_K * ed) ** 2 + ss**2)
        q = (a / sx) ** 2 - 2 * rho * a * d / (sx * sy) + (d / sy) ** 2
        ln = -np.log(2 * np.pi * sx * sy * np.sqrt(1 - rho**2)) - q / (2 * (1 - rho**2))
    return ln / math.log(10.0)


def qso_forbidden(df: pd.DataFrame) -> np.ndarray:
    """True where the switches in force say that the object may not get the QSO label."""
    opts = options()
    out = np.zeros(len(df), dtype=bool)
    if not len(df) or not opts & {"surveys2", "surveys3", "pm"}:
        return out
    low = low_latitude(df)
    if opts & {"surveys2", "surveys3"}:
        need = 3 if "surveys3" in opts else 2
        cats = df["catalogs"] if "catalogs" in df else pd.Series("", index=df.index)
        out |= low & (n_surveys(cats) < need)
    if "pm" in opts:
        f = log10_fpm0(df)
        out |= low & np.isfinite(f) & (f < PM_LOG10_CUT)
    return out


def wise_rule_allowed(rule_id: str, row, ra, dec) -> bool:
    """False where a switch removes the AllWISE AGN evidence of ``rule_id`` for this object (04_build_evidence)."""
    opts = options()
    if not opts & {"wise_footprint", "wise_second"} or ra is None or dec is None:
        return True
    r, d = float(ra), float(dec)
    if "wise_footprint" in opts and rule_id == "WISE-AGN-001":
        if not (abs(float(galactic_latitude(r, d))) > 10.0 and float(galactic_centre_distance(r, d)) > 30.0):
            return False
    if "wise_second" in opts and abs(float(galactic_latitude(r, d))) < max_abs_b():
        names = {x for x in str(row.get("catalogs", "") or "").split("|") if x and x not in ANNOTATION}
        if names <= {"AllWISE"}:
            return False
    return True

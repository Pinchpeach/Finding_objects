"""Switches that limit the QSO label at low Galactic latitude (2.61.3).  Every switch is off by default.

At |b| < 20 deg most of what the classifier calls QSO is not a quasar (benchmark/lowlat_qso/LOWLAT_QSO.md: 170 objects that are
not sample quasars in 1.18 deg^2, 144 deg^-2, against 5-8 deg^-2 quasars expected to i ~ 19.3 at high latitude).  The 2.61.3
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
  spectro_keep          (2.61.5) an object whose pipeline spectral class is QSO (a SPC-SDSS-003, SPC-DESI-003 or SPC-LAMOST-003
                        reading, raw score >= 0.5) is never held back by ``surveys2`` / ``surveys3`` / ``pm``: a spectrum is
                        a direct measurement of the class, and a blind benchmark (no spectra) is not affected by this switch

``V2_LOWLAT_QSO_ABSB`` (default 20): the latitude below which the switches act.  Nothing changes at |b| >= this value or where a
position is missing (every switch tests the object's own |b|; ``wise_footprint`` too, 2.61.3 review).  The literature behind the
numbers is in LITERATURE_LOWLAT_QSO_2026-11-27.md.

How surveys are counted (2.61.3 review): one per survey, not per catalogue.  Catalogues that are products of the same measurement
count once (``SURVEY_OF``: Gaia DR3 and its SOS variability tables, the two ZTF tables, DESI spectra and their FastSpecFit fits,
the Siena Galaxy Atlas built from Legacy Surveys imaging).  Only AllWISE is collected from WISE (the W1/W2 forced photometry of a
Legacy Surveys row belongs to that row), and the Gaia DSC probabilities are columns of the Gaia row.  Different telescopes in
the same optical bands (Pan-STARRS1, Legacy Surveys, SDSS imaging) count separately: the switches ask for independent
detections, which a deblending fragment or an artefact of one survey's pipeline does not have, not for independent wavelength
coverage.  SDSS imaging and an SDSS spectrum are different measurements and count separately.

What a held-back object becomes: ``UNKNOWN`` with status ``LOW_CONFIDENCE`` (the path of a faint QSO), best candidate ``QSO``,
the secondary reading ``QSO`` with reason ``LOWLAT_QSO_HELD`` where it has no other reading, and the column ``lowlat_qso_hold``
(written only when a label switch is on) saying why; Classifier/unknown_reason shows that text.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

OPTIONS = ("surveys2", "surveys3", "pm", "wise_footprint", "wise_second", "spectro_keep")
# catalogues that identify or annotate a source, not measure it (01_source_association.ANNOTATION_CATALOGS)
ANNOTATION = frozenset({"NED", "SIMBAD", "Roma-BZCAT", "Suh 2021 AGB Catalog", "HASH PN Catalog", "Acker PN Spectroscopy",
                        "ATNF Pulsar Catalog", "Galaxy Zoo DESI"})  # fmt: skip
# catalogues that are products of the same survey measurement count as one survey (n_surveys)
SURVEY_OF = {
    "Gaia DR3 variability SOS": "Gaia DR3",  # Specific Object Studies of the same Gaia DR3 photometry
    "ZTF periodic variables": "ZTF light curves",  # periodic-variable table of the same ZTF photometry
    "DESI DR1 FastSpecFit": "DESI DR1 spectroscopy",  # fits of the same DESI spectra
    "SGA-2020": "DESI Legacy Surveys DR10",  # Siena Galaxy Atlas, built from Legacy Surveys imaging (Moustakas et al. 2023)
}
HELD_REASON = "LOWLAT_QSO_HELD"  # secondary_class_reason of a QSO reading the switches held back
HOLD_COLUMN = "lowlat_qso_hold"
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
    """Number of different surveys measuring each object (annotation catalogues excluded, same-measurement catalogues once)."""
    out = []
    for c in catalogs.fillna("").astype(str):
        names = {SURVEY_OF.get(x, x) for x in c.split("|") if x and x not in ANNOTATION}
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


def spectro_keep() -> bool:
    """Spectroscopically classified QSOs are exempt from the label switches (``spectro_keep``)."""
    return "spectro_keep" in options()


def exempt_spectroscopic(details: list[str], spectroscopic_qso) -> list[str]:
    """``details`` of :func:`hold_details` with the spectroscopically classified QSOs (bool per object) left out when ``spectro_keep``."""
    if not spectro_keep():
        return details
    return ["" if s else d for d, s in zip(details, spectroscopic_qso)]


def label_switches_on() -> bool:
    """A switch that can hold back the QSO label is in force (the hold column is written only then)."""
    return bool(options() & {"surveys2", "surveys3", "pm"})


def hold_details(df: pd.DataFrame) -> list[str]:
    """Why the switches in force forbid the QSO label of each object ('' where they do not)."""
    opts = options()
    out = [""] * len(df)
    if not len(df) or not label_switches_on():
        return out
    low = low_latitude(df)
    ra = pd.to_numeric(df.get("ra", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    dec = pd.to_numeric(df.get("dec", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    with np.errstate(invalid="ignore"):
        b = np.abs(galactic_latitude(ra, dec))
    need = 3 if "surveys3" in opts else (2 if "surveys2" in opts else 0)
    if need:
        cats = df["catalogs"] if "catalogs" in df else pd.Series("", index=df.index)
        n = n_surveys(cats)
    f = log10_fpm0(df) if "pm" in opts else np.full(len(df), np.nan)
    for i in np.flatnonzero(low):
        why = []
        if need and n[i] < need:
            why.append(f"measured by {n[i]} survey{'s' if n[i] != 1 else ''}, {need} needed")
        if np.isfinite(f[i]) and f[i] < PM_LOG10_CUT:
            why.append(f"Gaia proper motion log10 f_PM0 = {f[i]:.1f} < {PM_LOG10_CUT:g} (Fu et al. 2021)")
        if why:
            out[i] = f"QSO label withheld at |b| = {b[i]:.1f} < {max_abs_b():g} deg (V2_LOWLAT_QSO): " + "; ".join(why)
    return out


def qso_forbidden(df: pd.DataFrame) -> np.ndarray:
    """True where the switches in force say that the object may not get the QSO label."""
    return np.array([bool(x) for x in hold_details(df)], dtype=bool)


def held_readings(details: list[str], labels, statuses, best, sec, why):
    """Stage 5: the QSO reading of each object the switches held back (UNKNOWN, LOW_CONFIDENCE, best candidate QSO) as a
    secondary reading where it has no other one, and the hold column (the reason; '' elsewhere)."""
    sec, why, col = list(sec), list(why), []
    for i, d in enumerate(details):
        held = bool(d) and labels[i] == "UNKNOWN" and statuses[i] == "LOW_CONFIDENCE" and best[i] == "QSO"
        col.append(d if held else "")
        if held and not sec[i]:
            sec[i], why[i] = "QSO", HELD_REASON
    return sec, why, col


def wise_rule_allowed(rule_id: str, row, ra, dec) -> bool:
    """False where a switch removes the AllWISE AGN evidence of ``rule_id`` for this object (04_build_evidence)."""
    opts = options()
    if not opts & {"wise_footprint", "wise_second"} or ra is None or dec is None:
        return True
    r, d = float(ra), float(dec)
    b = abs(float(galactic_latitude(r, d)))
    if "wise_footprint" in opts and rule_id == "WISE-AGN-001" and b < max_abs_b():
        # only below the switches' latitude: near the Galactic Centre at |b| >= 20 deg the Stern rule stays (2.61.3 review)
        if not (b > 10.0 and float(galactic_centre_distance(r, d)) > 30.0):
            return False
    if "wise_second" in opts and b < max_abs_b():
        names = {x for x in str(row.get("catalogs", "") or "").split("|") if x and x not in ANNOTATION}
        if names <= {"AllWISE"}:
            return False
    return True

"""Unit harmonisation: one unit system for quantities that several catalogues
measure in different units.

Stage 2 keeps every catalogue field under its own namespace
(``<catalog>__<column>``) in the catalogue's native units. ``harmonize``
adds standard columns next to them, so later code never has to know which
survey reports nanomaggies, Vega or AB magnitudes, mJy or Jy, z or cz:

=======================  ============================================  =======================================
quantity                 standard                                      conversion (source)
=======================  ============================================  =======================================
optical/IR photometry    AB magnitude ``std_mag__<survey>_<band>``     see BANDS below
                         and 1-sigma error ``std_magerr__...``
Gaia G / BP / RP         kept in the Gaia (Vega) system,               not converted: every Gaia colour in the
                         ``std_mag_gaia__g|bp|rp``                     pipeline is compared with Gaia-system
                                                                       references (Pecaut & Mamajek BP-RP,
                                                                       Gentile Fusillo+2021 WD locus)
Galactic reddening       ``std_ebv`` = SFD E(B-V)                      Legacy Surveys mw_transmission_g with
                                                                       R_g = 3.214 (Schlafly & Finkbeiner 2011),
                                                                       else GALEX E(B-V)
radio flux density       mJy at the native frequency, and              FIRST/NVSS 1.4 GHz as published; LoTSS
                         ``std_radio_1p4ghz_mjy``                      144 MHz and VLASS 3 GHz scaled with
                                                                       alpha = -0.7 (Condon 1992)
redshift                 ``std_z_spec`` (spectroscopic only) and       SDSS/DESI/LAMOST z; NED z unless flagged
                         ``std_z_spec_source``; ``std_z_catalog``       photometric; NED velocity / c; SIMBAD
                         for redshifts of unknown method               rvz_redshift only as ``std_z_catalog``
astrometry               mas and mas/yr: ``std_parallax_mas``,         Gaia DR3 (already mas)
                         ``std_pm_mas_yr``
=======================  ============================================  =======================================

Photometric systems (AB offsets m_AB = m_native + offset):

* Legacy Surveys DR10 g r i z W1 W2: nanomaggies, AB by definition,
  m = 22.5 - 2.5 log10(f), sigma_m = 1.0857 / (f sqrt(ivar)) (Dey+2019).
  W1/W2 are unWISE forced photometry calibrated to AllWISE (Schlafly+2019).
* Pan-STARRS1: AB (Tonry et al. 2012).
* SDSS: asinh magnitudes close to AB; u_AB = u - 0.04, z_AB = z + 0.02
  (SDSS DR14 flux-calibration notes; g r i taken as AB).
* GALEX: AB (Morrissey et al. 2007).
* AllWISE W1..W4: Vega, +2.699 / +3.339 / +5.174 / +6.620 (Jarrett et al.
  2011; WISE Explanatory Supplement IV.4.h). Checked against the Legacy
  Surveys unWISE AB fluxes of the same sources by ``consistency``.
* 2MASS J H Ks (2MASS PSC or the AllWISE 2MASS columns): Vega,
  +0.91 / +1.39 / +1.85 (Blanton & Roweis 2007).
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

LS = "desi_legacy_surveys_dr10__"
PS1 = "pan_starrs1_dr2_meanobject__"
SDSS = "sdss_dr18_photoobj__"
GALEX = "galex_ais__"
WISE = "allwise__"
TMASS = "2mass_psc__"
GAIA = "gaia_dr3__"

SDSS_AB = {"u": -0.04, "g": 0.0, "r": 0.0, "i": 0.0, "z": 0.02}
WISE_AB = {"w1": 2.699, "w2": 3.339, "w3": 5.174, "w4": 6.620}
TMASS_AB = {"j": 0.91, "h": 1.39, "ks": 1.85}
ALPHA_RADIO = -0.7
R_DECAM_G = 3.214
C_KMS = 299792.458


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce") if name in df else pd.Series(np.nan, index=df.index)


def _nmgy_to_ab(flux, ivar):
    f = flux.where(flux > 0)
    mag = 22.5 - 2.5 * np.log10(f)
    err = 1.0857 / (f * np.sqrt(ivar.where(ivar > 0)))
    return mag, err


def harmonize(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with the standard ``std_*`` columns added (inputs untouched)."""
    new: dict[str, pd.Series] = {}
    # Legacy Surveys (AB nanomaggies)
    for b in ("g", "r", "i", "z", "w1", "w2"):
        m, e = _nmgy_to_ab(_col(df, f"{LS}flux_{b}"), _col(df, f"{LS}flux_ivar_{b}"))
        new[f"std_mag__ls_{b}"], new[f"std_magerr__ls_{b}"] = m, e
    # Pan-STARRS1 (AB)
    for b in ("g", "r", "i", "z", "y"):
        new[f"std_mag__ps1_{b}"] = _col(df, f"{PS1}{b}MeanPSFMag")
        new[f"std_magerr__ps1_{b}"] = _col(df, f"{PS1}{b}MeanPSFMagErr")
        new[f"std_mag__ps1kron_{b}"] = _col(df, f"{PS1}{b}MeanKronMag")
    # SDSS (asinh ~ AB; u and z offsets)
    for b, off in SDSS_AB.items():
        new[f"std_mag__sdss_{b}"] = _col(df, f"{SDSS}modelMag_{b}") + off
        new[f"std_magerr__sdss_{b}"] = _col(df, f"{SDSS}modelMagErr_{b}")
        new[f"std_mag__sdsspsf_{b}"] = _col(df, f"{SDSS}psfMag_{b}") + off
    # GALEX (AB)
    for b, col in (("fuv", "FUVmag"), ("nuv", "NUVmag")):
        new[f"std_mag__galex_{b}"] = _col(df, f"{GALEX}{col}")
        new[f"std_magerr__galex_{b}"] = _col(df, f"{GALEX}e_{col}")
    # AllWISE (Vega -> AB)
    for b, off in WISE_AB.items():
        n = b.upper()
        new[f"std_mag__wise_{b}"] = _col(df, f"{WISE}{n}mag") + off
        new[f"std_magerr__wise_{b}"] = _col(df, f"{WISE}e_{n}mag")
    # 2MASS (Vega -> AB): PSC first, else the 2MASS columns carried by AllWISE
    for b, col in (("j", "Jmag"), ("h", "Hmag"), ("ks", "Kmag")):
        v = _col(df, f"{TMASS}{col}").fillna(_col(df, f"{WISE}{col}"))
        e = _col(df, f"{TMASS}e_{col}").fillna(_col(df, f"{WISE}e_{col}"))
        new[f"std_mag__2mass_{b}"], new[f"std_magerr__2mass_{b}"] = v + TMASS_AB[b], e
    # Gaia: native system
    for b, col in (("g", "phot_g_mean_mag"), ("bp", "phot_bp_mean_mag"), ("rp", "phot_rp_mean_mag")):
        new[f"std_mag_gaia__{b}"] = _col(df, f"{GAIA}{col}")
    new["std_parallax_mas"] = _col(df, f"{GAIA}parallax")
    new["std_parallax_err_mas"] = _col(df, f"{GAIA}parallax_error")
    new["std_pm_mas_yr"] = np.hypot(_col(df, f"{GAIA}pmra"), _col(df, f"{GAIA}pmdec"))
    # Reddening
    t = _col(df, f"{LS}mw_transmission_g")
    new["std_ebv"] = (-2.5 * np.log10(t.where((t > 0) & (t <= 1))) / R_DECAM_G).fillna(_col(df, f"{GALEX}E(B-V)"))
    # Radio flux densities (mJy)
    first, nvss = _col(df, "first__Fint"), _col(df, "nvss__S1.4")
    lotss = _col(df, "lotss_dr2__Stotal").fillna(_col(df, "lotss_dr2__SpeakTot")).fillna(_col(df, "lotss_dr2__Total_flux"))
    vlass = _col(df, "vlass__Ftot").fillna(_col(df, "vlass__Total_flux"))
    new["std_radio_first_mjy"], new["std_radio_nvss_mjy"] = first, nvss
    new["std_radio_lotss_144mhz_mjy"], new["std_radio_vlass_3ghz_mjy"] = lotss, vlass
    r14 = first.where(first > 0).fillna(nvss.where(nvss > 0))
    r14 = r14.fillna(lotss.where(lotss > 0) * (1400 / 144) ** ALPHA_RADIO)
    new["std_radio_1p4ghz_mjy"] = r14.fillna(vlass.where(vlass > 0) * (1400 / 3000) ** ALPHA_RADIO)
    # Redshifts
    zspec = pd.Series(np.nan, index=df.index, dtype=float)
    src = pd.Series(None, index=df.index, dtype=object)
    for name, col in (("SDSS", "sdss_dr18_spectroscopy__z"), ("DESI", "desi_dr1_spectroscopy__z"),
                      ("LAMOST", "lamost_dr_catalog__z")):
        v = _col(df, col)
        take = zspec.isna() & v.notna()
        zspec[take], src[take] = v[take], name
    flag = df["ned__Redshift Flag"].astype(str).str.upper() if "ned__Redshift Flag" in df else pd.Series("", index=df.index)
    nedz = _col(df, "ned__Redshift").fillna(_col(df, "ned__Velocity") / C_KMS)
    ok = zspec.isna() & nedz.notna() & ~flag.str.contains("PHOT|PZ", regex=True)
    zspec[ok], src[ok] = nedz[ok], "NED"
    new["std_z_spec"], new["std_z_spec_source"] = zspec, src
    new["std_z_catalog"] = _col(df, "simbad__rvz_redshift")
    return pd.concat([df.drop(columns=[c for c in new if c in df.columns]), pd.DataFrame(new, index=df.index)], axis=1)


def consistency(df: pd.DataFrame, min_n: int = 5) -> dict:
    """Median differences between catalogues that measure the same band, after
    harmonisation (a wrong unit or zero point shows up as an offset)."""
    h = df if "std_mag__ls_w1" in df else harmonize(df)
    pairs = {"W1 LS-AllWISE": ("std_mag__ls_w1", "std_mag__wise_w1"), "W2 LS-AllWISE": ("std_mag__ls_w2", "std_mag__wise_w2"),
             "r LS-PS1": ("std_mag__ls_r", "std_mag__ps1_r"), "r SDSS-PS1": ("std_mag__sdsspsf_r", "std_mag__ps1_r"),
             "g LS-PS1": ("std_mag__ls_g", "std_mag__ps1_g"), "z LS-PS1": ("std_mag__ls_z", "std_mag__ps1_z")}
    out = {}
    for name, (a, b) in pairs.items():
        d = (h[a] - h[b]).dropna()
        d = d[d.abs() < 2.0] if len(d) else d                      # drop gross mismatches (blends)
        if len(d) >= min_n:
            out[name] = {"n": int(len(d)), "median": round(float(d.median()), 3),
                         "nmad": round(float(1.4826 * (d - d.median()).abs().median()), 3)}
    return out

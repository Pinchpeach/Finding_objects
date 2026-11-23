#!/usr/bin/env python3
"""Purity / completeness of two published X-ray rules on our existing data (2.56.0).

Rules (thresholds as published; nothing fitted here):
* Rodriguez (2024, arXiv:2401.09537, the "X-ray Main Sequence"):
  accreting compact object if log(F_X / F_opt) > (BP - RP) - 3.5.  F_X: XMM
  0.2-12 keV (4XMM band 8) in the paper.  F_opt as Liu et al. (2025,
  arXiv:2505.10478 eq. in sect. 2): F_opt = 10^(-0.4 (G - 4.83)) L_sun / (4 pi (10 pc)^2),
  i.e. Rodriguez's L_opt = 10^(0.4 (M_G,sun - M_G)) L_sun put at the distance
  of the source; Liu et al. used the eRASS1 0.2-2.3 keV flux directly.
  Rodriguez drew the cut on Galactic 4XMM x Gaia sources: parallax / error > 3,
  |pm / error| > 5 in RA and Dec, flux / error > 3 in G, BP, RP, corrected
  BP/RP excess C* < 0.05 (Riello et al. 2021 eq. 6), RUWE < 1.4 ("domain").
  The author gives no purity or completeness: these are the first numbers.
* Lin, Webb & Barret (2012, ApJ 756, 27, arXiv:1207.1913): star if
  log(F_X / F_IR) < -0.9 with log F_IR = -Ks / 2.5 - 6.95 (2MASS Ks; upper
  limits, ph_qual 'U', left out) and F_X the
  maximum 0.2-12 keV XMM flux (their Figs. 7-8: "0.2-12.0 keV; maximum"), i.e.
  4XMM F8max.  Their "except HR1 <= 0.3" clause is not applied (the sign is
  unclear in the text we could extract).

Truth (sample built by xray_rules/build_sample.py):
  compact objects: CVs (Ritter & Kolb 7.24, B/cb), HMXB (Neumann+2023, Fortin+2023),
  LMXB (Avakyan+2023, Fortin+2024); duplicates within 3" counted once.
  stars: SDSS DR18 spectroscopic STAR (no CV / WD subclass) with an X-ray match
  (class from the optical spectrum, independent of X-rays), and HamStar eRASS1
  coronal identifications (Freund+2024), without those within 3" of a compact
  object (drop_hamstar_compact).  HamStar's coronal probability uses
  F_X/F_G and BP-RP (its Bayes map, eq. 2), the plane of the Rodriguez rule, so
  its false-positive rate there is biased low; it is reported separately.
  AGN: SDSS DR18 spectroscopic QSOs with an X-ray match.
"""

from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
SAMPLE = B / "xray_rules" / "sample.csv.gz"
L_SUN, PC = 3.828e33, 3.0857e18
F_OPT0 = L_SUN / (4 * math.pi * (10 * PC) ** 2)  # erg/s/cm2 at G = M_G,sun = 4.83
COMPACT = ("CV", "LMXB", "HMXB")
BANDS = {"4XMM 0.2-12 keV (Rodriguez)": "xmm_Flux8", "eRASS1 0.2-2.3 keV (Liu+2025)": "ero_MLFlux1", "CSC 0.5-7 keV (ours)": "csc_Favgb"}
SEP = {"xmm_Flux8": "xmm_sep", "xmm_F8max": "xmm_sep", "ero_MLFlux1": "ero_sep", "csc_Favgb": "csc_sep"}
# X-ray match radius.  The SDSS stars are faint and at high latitude, where an
# unrelated X-ray source (mostly an AGN) inside the X-ray error circle is
# common: shifting the SDSS star positions by 1-2' leaves 19 % (4XMM, 3 sigma
# up to 10"), 65 % (eRASS1) and 11 % (CSC) of the matches (chance
# coincidences).  Within 1.5" the chance fraction is 4.2 % (4XMM) and 1.7 %
# (CSC); eRASS1 positions (sigma ~ 5") cannot reach it, so its SDSS-star
# numbers mostly measure wrong counterparts.
MAX_SEP = (None, 1.5)


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def rate(k, n):
    return {"k": int(k), "n": int(n), "rate": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def c_star(bp_rp, c):
    """Corrected BP/RP flux excess (Riello et al. 2021, eq. 6 and table 2)."""
    x = bp_rp
    f = np.where(x < 0.5, 1.154360 + 0.033772 * x + 0.032277 * x**2,
                 np.where(x < 4.0, 1.162004 + 0.011464 * x + 0.049255 * x**2 - 0.005879 * x**3, 1.057572 + 0.140537 * x))
    return c - f


# HamStar controls that are compact-object truth (PR #72 review): the HamStar
# control was not cleaned of the compact-object lists, unlike the SDSS control
# (build_sample.py drops SDSS objects within 3" of a compact object), so a
# correct detection of e.g. V2400 Oph or PSR B1259-63 was counted as a
# control false positive.  Dropped here within MATCH_ARCSEC, as for SDSS.
MATCH_ARCSEC = 3.0


def drop_hamstar_compact(m: pd.DataFrame) -> pd.DataFrame:
    """The HamStar controls farther than MATCH_ARCSEC from every compact-object truth row."""
    ham = m.truth.eq("CORONAL_STAR_HAMSTAR")
    comp = m.truth.isin(COMPACT)
    if not ham.any() or not comp.any():
        return m
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    h = SkyCoord(m.ra[ham].to_numpy() * u.deg, m.dec[ham].to_numpy() * u.deg)
    c = SkyCoord(m.ra[comp].to_numpy() * u.deg, m.dec[comp].to_numpy() * u.deg)
    _, sep, _ = h.match_to_catalog_sky(c)
    drop = m.index[ham][sep.arcsec <= MATCH_ARCSEC]
    print(f"HamStar controls within {MATCH_ARCSEC:g}\" of a compact object, dropped: {len(drop)}")
    return m.drop(index=drop)


def prepare(m: pd.DataFrame) -> pd.DataFrame:
    m = drop_hamstar_compact(m).copy()
    m["G"] = m.g_phot_g_mean_mag
    m["bp_rp"] = m.g_phot_bp_mean_mag - m.g_phot_rp_mean_mag
    m["log_fopt"] = np.log10(F_OPT0) - 0.4 * (m.G - 4.83)
    m["cstar"] = c_star(m.bp_rp, m.g_phot_bp_rp_excess_factor)
    m["domain"] = (
        (m.g_parallax / m.g_parallax_error > 3)
        & ((m.g_pmra / m.g_pmra_error).abs() > 5)
        & ((m.g_pmdec / m.g_pmdec_error).abs() > 5)
        & (m.g_phot_g_mean_flux_over_error > 3)
        & (m.g_phot_bp_mean_flux_over_error > 3)
        & (m.g_phot_rp_mean_flux_over_error > 3)
        & (m.cstar < 0.05)
        & (m.g_ruwe < 1.4)
    )
    # A Ks with photometric quality 'U' (third character of the 2MASS ph_qual,
    # t_Qflg) is an upper limit, not a measurement (2MASS PSC explanatory
    # supplement, sec. 2.2a): it bounds log(F_X/F_IR) from below only, so it
    # cannot establish log(F_X/F_IR) < -0.9 (PR #72 review: five X-ray
    # binaries with Ks 'U' were counted as stars).  Left out of the Lin rule.
    ks_limit = m.t_Qflg.astype(str).str[2].eq("U") if "t_Qflg" in m else pd.Series(False, index=m.index)
    m["ks_upper_limit"] = ks_limit
    m["log_fir"] = (-m.t_Kmag / 2.5 - 6.95).where(~ks_limit)
    m["group"] = np.where(m.truth.isin(COMPACT), "COMPACT", m.truth)
    return m


def rodriguez(m: pd.DataFrame) -> dict:
    out = {}
    for band, col in [(b, c) for b, c in BANDS.items()]:
      for ms in MAX_SEP:
        fx = pd.to_numeric(m[col], errors="coerce")
        if ms is not None:
            fx = fx.where(m[SEP[col]] <= ms)
            band_name = f"{band}, match <= {ms}\""
        else:
            band_name = f"{band}, match <= 3 sigma"
        has = (fx > 0) & m.G.notna() & m.bp_rp.notna()
        above = np.log10(fx.where(fx > 0)) - m.log_fopt > m.bp_rp - 3.5
        for dom_name, dom in (("Gaia G and BP-RP", has), ("Rodriguez Galactic cuts", has & m.domain)):
            r = {}
            for g in ("COMPACT", "CV", "LMXB", "HMXB", "STAR_SDSS_SPEC", "CORONAL_STAR_HAMSTAR", "QSO_SDSS_SPEC"):
                sel = (m.truth == g) if g != "COMPACT" else (m.group == "COMPACT")
                r[g] = rate((above & dom & sel).sum(), (dom & sel).sum())
                r[g]["with_flux"] = int((fx.gt(0) & sel).sum())
            tp = r["COMPACT"]["k"]
            for ctl in ("STAR_SDSS_SPEC", "CORONAL_STAR_HAMSTAR"):
                fp = r[ctl]["k"]
                r[f"purity_vs_{ctl}"] = rate(tp, tp + fp)
            out[f"{band_name} | {dom_name}"] = r
    return out


def lin(m: pd.DataFrame) -> dict:
    return {f"4XMM F8max (0.2-12 keV maximum) | 2MASS Ks | match <= {ms or '3 sigma'}": _lin(m, ms) for ms in MAX_SEP}


def _lin(m: pd.DataFrame, ms) -> dict:
    fx = pd.to_numeric(m["xmm_F8max"], errors="coerce")
    if ms is not None:
        fx = fx.where(m.xmm_sep <= ms)
    has = (fx > 0) & m.log_fir.notna()
    star = np.log10(fx.where(fx > 0)) - m.log_fir < -0.9
    r = {}
    for g in ("STAR_SDSS_SPEC", "CORONAL_STAR_HAMSTAR", "COMPACT", "CV", "LMXB", "HMXB", "QSO_SDSS_SPEC"):
        sel = (m.truth == g) if g != "COMPACT" else (m.group == "COMPACT")
        r[g] = rate((star & has & sel).sum(), (has & sel).sum())
        r[g]["with_xmm"] = int((fx.gt(0) & sel).sum())
    for ctl in ("STAR_SDSS_SPEC", "CORONAL_STAR_HAMSTAR"):
        tp = r[ctl]["k"]
        fp_c, fp_q = r["COMPACT"]["k"], r["QSO_SDSS_SPEC"]["k"]
        r[f"purity_{ctl}_vs_compact"] = rate(tp, tp + fp_c)
        r[f"purity_{ctl}_vs_compact_and_qso"] = rate(tp, tp + fp_c + fp_q)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, default=SAMPLE)
    ap.add_argument("--out", type=Path, default=B / "xray_rules" / "metrics.json")
    a = ap.parse_args()
    m = prepare(pd.read_csv(a.sample, low_memory=False))
    res = {
        "sample": m.truth.value_counts().to_dict(),
        "ks_upper_limits_left_out": m.groupby("truth").ks_upper_limit.sum().astype(int).to_dict(),
        "rodriguez_2024": rodriguez(m),
        "lin_2012": lin(m),
    }
    a.out.write_text(json.dumps(res, indent=1) + "\n")
    print("sample", res["sample"])
    for k, r in res["rodriguez_2024"].items():
        print(f"\nRodriguez | {k}")
        for g, v in r.items():
            print(f"  {g:38s} {v['k']:6d}/{v['n']:<6d} {v['rate']}  {v['wilson95']}")
    for k, r in res["lin_2012"].items():
        print(f"\nLin | {k}  (rate = called star)")
        for g, v in r.items():
            print(f"  {g:50s} {v['k']:6d}/{v['n']:<6d} {v['rate']}  {v['wilson95']}")


if __name__ == "__main__":
    main()

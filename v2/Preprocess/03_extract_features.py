#!/usr/bin/env python3
"""Stage 3: derive rule-required classification features.

Preserves all integrated columns and adds deterministic derived features used by
classification_rules.csv. It does not classify objects.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import importlib.util


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_V2 = Path(__file__).resolve().parents[1]
TABLE_IO = _load("v2_table_io", _V2 / "Preprocess" / "table_io.py")
# SIMBAD otype hierarchy (catalog_confidence_simbad_type); loaded once, not per run().
OTYPES = _load("v2_simbad_otypes_s3", _V2 / "Classifier" / "simbad_otypes.py")


def safe_div(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    return a.div(b.where(b.ne(0)))


def run(objects: Path, rules_path: Path, out: Path) -> Path:
    df = TABLE_IO.read_table(objects)
    rules = pd.read_csv(rules_path, keep_default_na=False)
    required = set()
    for cell in rules["feature_columns"]:
        required.update(x for x in str(cell).split("|") if x)
    # Build all derived columns together, then concatenate once. This avoids
    # repeated DataFrame.insert calls and fragmentation as feature count grows.
    derived = {}
    namespaced = {c.split("__", 1)[0] for c in df.columns if "__" in c}

    def field(prefix, name):
        """Column holding ``name`` from catalog ``prefix`` (see Stage 2)."""
        if prefix in namespaced:
            key = f"{prefix}__{name}"
            return key if key in df.columns else None
        return name if name in df.columns else None

    gaia = lambda n: field("gaia_dr3", n)
    if gaia("parallax") and gaia("parallax_error"):
        plx, eplx = pd.to_numeric(df[gaia("parallax")], errors="coerce"), df[gaia("parallax_error")]
        derived["parallax_snr"] = safe_div(plx.abs(), eplx)
        derived["normalized_corrected_parallax"] = safe_div((plx + 0.017).abs(), eplx)
    pm = [gaia(c) for c in ("pmra", "pmra_error", "pmdec", "pmdec_error")]
    if all(pm):
        a = safe_div(df[pm[0]], df[pm[1]])
        d = safe_div(df[pm[2]], df[pm[3]])
        derived["proper_motion_significance"] = np.sqrt(a * a + d * d)
    # Pan-STARRS photometric colours and PSF-Kron morphology proxies.
    # These are continuous measurements only; no class threshold is applied here.
    ps1_bands = ("g", "r", "i", "z", "y")

    def ps1_col(name):
        return field("pan_starrs1_dr2_meanobject", name)

    psf = {b: ps1_col(f"{b}MeanPSFMag") for b in ps1_bands}
    kron = {b: ps1_col(f"{b}MeanKronMag") for b in ps1_bands}

    def valid_ps1_mag(col):
        s = pd.to_numeric(df[col], errors="coerce")
        # PS1 uses sentinel/non-physical values (notably -999) for missing photometry.
        return s.where((s > 0) & (s < 40))

    psf_mag = {b: (valid_ps1_mag(psf[b]) if psf[b] else None) for b in ps1_bands}
    kron_mag = {b: (valid_ps1_mag(kron[b]) if kron[b] else None) for b in ps1_bands}
    for b1, b2 in zip(ps1_bands, ps1_bands[1:]):
        if psf_mag[b1] is not None and psf_mag[b2] is not None:
            derived[f"ps1_{b1}_{b2}_color"] = psf_mag[b1] - psf_mag[b2]
    for b in ps1_bands:
        if psf_mag[b] is not None and kron_mag[b] is not None:
            derived[f"ps1_{b}_psf_minus_kron"] = psf_mag[b] - kron_mag[b]
    # Preserve uncertainty and per-band detection counts so later evidence
    # rules can gate on measurement quality rather than colour alone.
    for b in ps1_bands:
        err_col = ps1_col(f"{b}MeanPSFMagErr")
        kron_err_col = ps1_col(f"{b}MeanKronMagErr")
        n_col = ps1_col(f"n{b}")
        if err_col:
            err = pd.to_numeric(df[err_col], errors="coerce")
            derived[f"ps1_{b}_psf_mag_err"] = err.where((err > 0) & (err < 5))
        if kron_err_col:
            kerr = pd.to_numeric(df[kron_err_col], errors="coerce")
            derived[f"ps1_{b}_kron_mag_err"] = kerr.where((kerr > 0) & (kerr < 5))
        if n_col:
            n = pd.to_numeric(df[n_col], errors="coerce")
            derived[f"ps1_n_{b}"] = n.where(n >= 0)

    ndet = ps1_col("nDetections")
    if ndet:
        n = pd.to_numeric(df[ndet], errors="coerce")
        derived["ps1_n_detections"] = n.where(n >= 0)

    # Data-quality flags only. These do not imply an astronomical class.
    # A band is usable when it has a physical PSF magnitude, a finite positive
    # uncertainty, and at least one contributing detection.
    for b in ps1_bands:
        if psf_mag[b] is None:
            continue
        err = derived.get(f"ps1_{b}_psf_mag_err")
        n = derived.get(f"ps1_n_{b}")
        if err is not None and n is not None:
            derived[f"ps1_{b}_photometry_valid"] = (psf_mag[b].notna() & err.notna() & (n > 0)).astype("Int64")

    # Colour uncertainties/significances.  These preserve the measurement
    # uncertainty so colour-selection rules can demand statistically meaningful
    # separation from their literature boundaries.
    for b1, b2 in zip(ps1_bands, ps1_bands[1:]):
        e1 = derived.get(f"ps1_{b1}_psf_mag_err")
        e2 = derived.get(f"ps1_{b2}_psf_mag_err")
        col = derived.get(f"ps1_{b1}_{b2}_color")
        if e1 is not None and e2 is not None and col is not None:
            ce = np.sqrt(e1 * e1 + e2 * e2)
            derived[f"ps1_{b1}_{b2}_color_err"] = ce
    # Legacy Surveys DR10 dereddened AB colours (Dey+2019): grz Tractor fluxes
    # and unWISE forced W1/W2, in nanomaggies (m = 22.5 - 2.5 log10 f).  Quasars
    # are separated from stars by their mid-IR excess (z-W1, W1-W2) and blue
    # optical colours (Chaussidon+2023).  A band enters a colour only at S/N>=3.
    ls = lambda n: field("desi_legacy_surveys_dr10", n)

    def ls_mag(band):
        f, iv, t = ls(f"flux_{band}"), ls(f"flux_ivar_{band}"), ls(f"mw_transmission_{band}")
        if not f or not iv:
            return None
        flux = pd.to_numeric(df[f], errors="coerce")
        ivar = pd.to_numeric(df[iv], errors="coerce")
        trans = pd.to_numeric(df[t], errors="coerce").where(lambda x: x > 0) if t else 1.0
        ok = (flux > 0) & (flux * np.sqrt(ivar.clip(lower=0)) >= 3)
        return (22.5 - 2.5 * np.log10((flux / trans).where(ok))).where(ok)

    ls_mags = {b: ls_mag(b) for b in ("g", "r", "z", "w1", "w2")}
    if ls_mags["r"] is not None:
        # Dereddened r (AB) for flux ratios against radio / X-ray (2.26.0).
        derived["ls_r_mag"] = ls_mags["r"]
    for b1, b2 in (("g", "r"), ("r", "z"), ("z", "w1"), ("w1", "w2")):
        if ls_mags[b1] is not None and ls_mags[b2] is not None:
            derived[f"ls_{b1}_{b2}_color"] = ls_mags[b1] - ls_mags[b2]
    # Distance from the stellar locus in z-W1 vs r-z (2.44.0): stars follow
    # z-W1 ~ 0.8(r-z) - 0.6 (AB) and are removed below it in the DESI LRG
    # selection (Zhou et al. 2023, AJ 165, 58, eq. 1); galaxies and quasars lie
    # above it through their K-corrected or power-law near-IR light.
    if {"ls_r_z_color", "ls_z_w1_color"} <= derived.keys():
        derived["ls_zw1_excess"] = derived["ls_z_w1_color"] - (0.8 * derived["ls_r_z_color"] - 0.6)

    # Tractor fit quality beyond the discrete TYPE (2.44.0).  dchisq_1..5 are
    # the chi^2 gains of the PSF, REX, DEV, EXP and SER models over no source
    # (Dey et al. 2019, AJ 157, 168, sec. 6); the relative REX - PSF gain
    # measures extent continuously -- DESI keeps quasars with (REX - PSF) / PSF
    # < 0.015 (Chaussidon et al. 2023, ApJ 944, 107) and Liu et al. (2025,
    # PASP 137, 084501) separate faint stars and galaxies with dchisq
    # differences.  The half-light radius over its error is the significance
    # of the size.  Log scale, as both span decades.
    def ls_num(n):
        c = ls(n)
        return pd.to_numeric(df[c], errors="coerce") if c else None

    d_psf, d_rex = ls_num("dchisq_1"), ls_num("dchisq_2")
    if d_psf is not None and d_rex is not None:
        rel = ((d_rex - d_psf) / d_psf.where(d_psf > 0)).clip(lower=0)
        derived["ls_dchisq_rex_rel_log"] = np.log10(rel + 1e-4)
    r_e, r_iv = ls_num("shape_r"), ls_num("shape_r_ivar")
    if r_e is not None and r_iv is not None:
        sig = r_e.clip(lower=0) * np.sqrt(r_iv.where(r_iv >= 0))
        derived["ls_size_sig_log"] = np.log10(1.0 + sig)

    # WISE Vega colours and propagated errors.
    wise = lambda n: field("allwise", n)
    if wise("W1mag") and wise("W2mag"):
        w1 = pd.to_numeric(df[wise("W1mag")], errors="coerce")
        w2 = pd.to_numeric(df[wise("W2mag")], errors="coerce")
        derived["wise_w1_w2_color"] = w1 - w2
        if wise("e_W1mag") and wise("e_W2mag"):
            e1 = pd.to_numeric(df[wise("e_W1mag")], errors="coerce")
            e2 = pd.to_numeric(df[wise("e_W2mag")], errors="coerce")
            derived["wise_w1_w2_color_err"] = np.sqrt(e1 * e1 + e2 * e2)
    # W2-W3 (Vega) where W3 is detected (snr3 >= 3): stellar photospheres sit
    # near 0, star-forming galaxies at 2-4 and quasars at 2-3.5 (Wright et
    # al. 2010, AJ 140, 1868, fig. 12; Jarrett et al. 2011, ApJ 735, 112),
    # the axis of the WISE colour-colour diagram that W1-W2 alone lacks (2.44.0).
    if wise("W2mag") and wise("W3mag"):
        w2 = pd.to_numeric(df[wise("W2mag")], errors="coerce")
        w3 = pd.to_numeric(df[wise("W3mag")], errors="coerce")
        s3 = pd.to_numeric(df[wise("snr3")], errors="coerce") if wise("snr3") else None
        c = w2 - w3
        derived["wise_w2_w3_color"] = c.where(s3 >= 3) if s3 is not None else c

    # Catalog observation-confidence indices. These are [0,1] project quality
    # indices anchored to published catalog quality diagnostics; they are NOT
    # posterior class probabilities. Missing catalog/quality information stays NaN.
    conf = {}
    catalogs = df["catalogs"].fillna("").astype(str) if "catalogs" in df.columns else pd.Series("", index=df.index)

    def ncol(name, prefix):
        col = field(prefix, name)
        return pd.to_numeric(df[col], errors="coerce") if col else pd.Series(np.nan, index=df.index)

    def tcol(name, prefix):
        col = field(prefix, name)
        return df[col] if col else pd.Series(np.nan, index=df.index, dtype=object)

    def hascat(name):
        return catalogs.str.contains(name, regex=False)

    # Gaia: RUWE near unity indicates a good single-source astrometric fit;
    # >1.4 is documented as potentially problematic. Penalize continuously above 1.4.
    if gaia("ruwe"):
        ruwe = ncol("ruwe", "gaia_dr3")
        g = np.minimum(1.0, 1.4 / ruwe.where(ruwe > 0))
        conf["catalog_confidence_gaia_astrometry"] = g.where(hascat("Gaia DR3"))
    dsc_cols = [
        "classprob_dsc_combmod_quasar",
        "classprob_dsc_combmod_galaxy",
        "classprob_dsc_combmod_star",
        "classprob_dsc_combmod_whitedwarf",
        "classprob_dsc_combmod_binarystar",
    ]
    if any(gaia(x) for x in dsc_cols):
        # DSC probabilities already encode classifier uncertainty; this flag only
        # records whether the catalog probability vector is usable.
        ok = pd.concat([ncol(x, "gaia_dr3") for x in dsc_cols if gaia(x)], axis=1).notna().all(axis=1)
        conf["catalog_confidence_gaia_dsc"] = ok.astype(float).where(hascat("Gaia DR3"))

    # PS1 morphology: propagate PSF and Kron magnitude errors into the separator
    # and use distance from the documented 0.05-mag boundary in sigma units.
    delta = derived.get("ps1_i_psf_minus_kron")
    pe = derived.get("ps1_i_psf_mag_err")
    ke = derived.get("ps1_i_kron_mag_err")
    imag = psf_mag.get("i")
    if delta is not None and pe is not None and ke is not None and imag is not None:
        sig = np.sqrt(pe * pe + ke * ke)
        z = (delta - 0.05).abs() / sig.where(sig > 0)
        q = (z / (z + 1)).where((imag >= 14) & (imag <= 21))
        conf["catalog_confidence_ps1_morphology"] = q.where(hascat("Pan-STARRS1"))

    # AllWISE: Stern et al. AGN selection used W1/W2 SNR>=10, isolated sources
    # (nb<=2), and artifact-free W1/W2 photometry. The index measures how fully
    # a source satisfies that measurement-quality envelope.
    if wise("snr1") and wise("snr2"):
        s1 = ncol("snr1", "allwise")
        s2 = ncol("snr2", "allwise")
        q = np.minimum(1.0, np.minimum(s1, s2) / 10.0).clip(lower=0)
        if wise("nb"):
            nb = ncol("nb", "allwise")
            q = q.where(nb.isna() | (nb <= 2), 0.0)  # missing nb is unknown, not blended
        if wise("ccf"):
            cc = df[wise("ccf")].fillna("").astype(str).str.replace(".0", "", regex=False).str.zfill(4)
            q = q.where(cc.str[:2].eq("00"), 0.0)
        conf["catalog_confidence_allwise"] = q.where(hascat("AllWISE"))

    # 2MASS PSC: ph_qual grades A-D are valid detections of decreasing quality;
    # cc_flg!=000 marks potentially biased/contaminated measurements.
    if field("2mass_psc", "Qflg"):
        grade = {"A": 1.0, "B": 0.7, "C": 0.5, "D": 0.25}

        def q2(s):
            vals = [grade.get(ch, 0.0) for ch in str(s)[:3]]
            nz = [v for v in vals if v > 0]
            return float(sum(nz) / len(nz)) if nz else 0.0

        q = df[field("2mass_psc", "Qflg")].map(q2)
        if field("2mass_psc", "Cflg"):
            cc = df[field("2mass_psc", "Cflg")].fillna("").astype(str).str.replace(".0", "", regex=False).str.zfill(3)
            q = q.where(cc.eq("000"), q * 0.5)
        conf["catalog_confidence_2mass"] = q.where(hascat("2MASS PSC"))

    # GALEX: convert magnitude uncertainty to approximate S/N (1.0857/sigma_mag);
    # artifact flags suppress affected bands. Five-sigma reaches index 1.
    if field("galex_ais", "NUVmag") or field("galex_ais", "FUVmag"):
        qs = []
        for band, err, af in (("NUVmag", "e_NUVmag", "Nafl"), ("FUVmag", "e_FUVmag", "Fafl")):
            if field("galex_ais", err):
                e = ncol(err, "galex_ais")
                snr = 1.0857 / e.where(e > 0)
                qb = np.minimum(1.0, snr / 5.0)
                if field("galex_ais", af):
                    qb = qb.where(ncol(af, "galex_ais").fillna(0).eq(0), 0.0)
                qs.append(qb)
        if qs:
            conf["catalog_confidence_galex"] = pd.concat(qs, axis=1).mean(axis=1).where(hascat("GALEX AIS"))

    # SDSS spectroscopy: ZWARNING=0 means no pipeline warning. Nonzero warnings
    # retain reduced confidence rather than being discarded.
    if field("sdss_dr18_spectroscopy", "zwarning"):
        zw = ncol("zwarning", "sdss_dr18_spectroscopy")
        conf["catalog_confidence_sdss_spectroscopy"] = pd.Series(
            np.where(zw.eq(0), 1.0, np.where(zw.notna(), 0.5, np.nan)), index=df.index
        ).where(hascat("SDSS DR18 spectroscopy"))
    # DESI DR1 Redrock (V/161; DESI Collaboration 2025, arXiv:2503.14745):
    # ZWARN = 0 and DELTACHI2 >= 25 (the best template ~5 sigma better than
    # the next; the DR1 reliable-redshift cut) -> 1.0, any other spectrum 0.5.
    # Backup-programme GALAXY fits are mostly misfit faint stars (~65 %,
    # DESI MWS backup paper, arXiv:2505.17230), so they keep 0.5 only.
    if field("desi_dr1_spectroscopy", "OType"):
        zw, dc = ncol("ZWARN", "desi_dr1_spectroscopy"), ncol("delChi2", "desi_dr1_spectroscopy")
        good = zw.eq(0) & dc.ge(25)
        backup_gal = tcol("Prog", "desi_dr1_spectroscopy").astype(str).str.strip().str.lower().eq("backup") & tcol(
            "OType", "desi_dr1_spectroscopy"
        ).astype(str).str.strip().str.upper().eq("GALAXY")
        conf["catalog_confidence_desi_spectroscopy"] = pd.Series(
            np.where(good & ~backup_gal, 1.0, 0.5), index=df.index
        ).where(hascat("DESI DR1 spectroscopy"))
    # LAMOST DR5 1D pipeline class (Luo et al. 2015, RAA 15, 1095): spectra
    # with S/N > 10 in g or i are the survey's good-quality set.  Against the
    # other spectroscopic surveys of the 18 independent fields (2.36.0) the
    # class agreed for 44/45 at S/N >= 10 and 16/18 below; "Unknown" is no class.
    if field("lamost_dr_catalog", "Class"):
        snr = pd.concat([ncol("snrg", "lamost_dr_catalog"), ncol("snri", "lamost_dr_catalog")], axis=1).max(axis=1)
        conf["catalog_confidence_lamost_spectroscopy"] = pd.Series(
            np.where(snr.ge(10), 1.0, 0.5), index=df.index
        ).where(hascat("LAMOST DR catalog"))
    # SDSS imaging: official guidance recommends clean=1 for clean star/galaxy samples.
    if field("sdss_dr18_photoobj", "clean"):
        cl = ncol("clean", "sdss_dr18_photoobj")
        conf["catalog_confidence_sdss_photometry"] = cl.eq(1).astype(float).where(hascat("SDSS DR18 PhotoObj"))

    # NED/SIMBAD are curated literature databases rather than homogeneous surveys.
    # Their indices are provenance weights, deliberately below direct spectroscopy.
    if field("ned", "Type"):
        physical = {"G", "QSO", "*", "WD*"}
        conf["catalog_confidence_ned_type"] = (
            tcol("Type", "ned").astype(str).isin(physical).astype(float).mul(0.8).where(hascat("NED"))
        )
    if field("simbad", "otype"):
        # Same hierarchy as Stage 4's SIMBAD-TYPE-001 (2.22.0): every child of
        # a mapped type is curated evidence; the old exact-code set gave the
        # children reliability 0, so Stage 4 emitted nothing for them (2.23.0).
        coarse = {"QSO": "QSO", "AGN": "EXTRAGALACTIC", "G": "GALAXY", "*": "STAR"}
        typed = tcol("otype", "simbad").astype(str).map(lambda t: OTYPES.resolve(str(t).strip(), coarse)[0] is not None)
        conf["catalog_confidence_simbad_type"] = typed.astype(float).mul(0.8).where(hascat("SIMBAD"))

    if derived:
        df = pd.concat([df, pd.DataFrame(derived, index=df.index)], axis=1)
    if conf:
        df = pd.concat([df, pd.DataFrame(conf, index=df.index)], axis=1)

    available = [c for c in required if c in df.columns]
    coverage = df[available].notna().sum(axis=1) if available else pd.Series(0, index=df.index)
    metadata = pd.DataFrame(
        {
            "rule_feature_coverage": coverage.astype(int),
            "rule_feature_total": len(required),
        },
        index=df.index,
    )
    df = pd.concat([df, metadata], axis=1)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] required_features={len(required)} objects={len(df)} -> {out}")
    return out


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--objects", type=Path, default=root / "integrated_objects.csv")
    p.add_argument("--rules", type=Path, default=root / "classification_rules.csv")
    p.add_argument("--out", type=Path, default=root / "features.csv")
    a = p.parse_args()
    run(a.objects, a.rules, a.out)


if __name__ == "__main__":
    main()

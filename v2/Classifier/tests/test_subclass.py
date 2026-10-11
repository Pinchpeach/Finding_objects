"""Second-stage sub-class classifier (Classifier/subclass.py)."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sc():
    spec = importlib.util.spec_from_file_location("v2_subclass_test", ROOT / "subclass.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_mk_parsing_and_reference_sequence():
    sc = _sc()
    assert sc.spt_number("K3V") == 53 and sc.spt_number("M2.5") == 62.5 and sc.spt_label(53.0) == "K3"
    ref = sc.sequence().set_index("SpT")
    assert ref.loc["G2V", "Teff"] == 5770 and abs(ref.loc["M0V", "Bp-Rp"] - 1.84) < 1e-9


def test_star_type_and_luminosity_from_gaia():
    sc = _sc()
    # A solar twin at 100 pc: (BP-RP)0 = 0.82, Teff 5770 K, M_G = 4.6
    sun = {"primary_class": "STAR", "gaia_dr3__bp_rp": 0.82, "gaia_dr3__ebpminrp_gspphot": 0.0,
           "gaia_dr3__teff_gspphot": 5770, "gaia_dr3__parallax": 10.0, "gaia_dr3__parallax_error": 0.05,
           "gaia_dr3__phot_g_mean_mag": 9.6, "gaia_dr3__ag_gspphot": 0.0}
    r = sc.classify(sun)
    assert r["spectral_type"] == "G2" and r["luminosity_class"] == "V" and r["code"] == "STAR:G:V"
    giant = dict(sun, **{"gaia_dr3__bp_rp": 1.25, "gaia_dr3__teff_gspphot": 4700, "gaia_dr3__phot_g_mean_mag": 5.8})
    g = sc.classify(giant)                                   # M_G = 0.8 at K3 colour: ~5 mag above the MS
    assert g["spectral_letter"] == "K" and g["luminosity_class"] == "III"


def test_spectroscopic_labels_outrank_photometry():
    sc = _sc()
    assert sc.classify({"primary_class": "STAR", "simbad__sp_type": "K2III", "gaia_dr3__bp_rp": 0.5})["code"] == "STAR:K:III"
    # SDSS "CarbonWD" is the DQ white-dwarf template, "Carbon" a carbon star.
    assert sc.classify({"primary_class": "STAR", "sdss_dr18_spectroscopy__subclass": "CarbonWD"})["code"] == "STAR:WD"
    r = sc.classify({"primary_class": "STAR", "sdss_dr18_spectroscopy__subclass": "Carbon"})
    assert r["code"] == "STAR:C:?" and r["rule"] == "SDSS_CSTAR"
    assert sc.classify({"primary_class": "STAR", "physical_class": "WD", "gaia_dr3__bp_rp": 0.0})["code"] == "STAR:WD"


def test_galaxy_activity_rules():
    sc = _sc()
    assert sc.classify({"primary_class": "GALAXY", "sdss_dr18_spectroscopy__subclass": "STARFORMING"})["code"].startswith("GALAXY:STAR_FORMING")
    sf = sc.classify({"primary_class": "GALAXY", "allwise__W1mag": 14.0, "allwise__W2mag": 13.9,
                      "allwise__W3mag": 10.4, "allwise__e_W3mag": 0.05})
    assert sf["activity"] == "STAR_FORMING" and sf["rule"] == "WISE_W23_SF"
    q = sc.classify({"primary_class": "GALAXY", "allwise__W1mag": 14.0, "allwise__W2mag": 13.9, "allwise__W3mag": 12.6})
    assert q["activity"] == "QUIESCENT" and q["rule"] == "WISE_W23_UL"      # W3 upper limit
    agn = sc.classify({"primary_class": "GALAXY", "allwise__W1mag": 14.0, "allwise__W2mag": 13.0})
    assert agn["activity"] == "AGN"
    none = sc.classify({"primary_class": "GALAXY"})
    assert none["subclass"] is None and none["status"] == "NO_SUBCLASS_EVIDENCE"


def test_qso_radio_loudness():
    sc = _sc()
    # i = 18, F = 10 mJy -> t = 13.9, R_i = 0.4 * 4.1 = 1.64 -> radio-loud
    loud = sc.classify({"primary_class": "QSO", "first__Fint": 10.0, "pan_starrs1_dr2_meanobject__iMeanPSFMag": 18.0,
                        "sdss_dr18_spectroscopy__z": 2.5, "catalogs": "FIRST|eROSITA eRASS1"})
    assert loud["radio"] == "RADIO_LOUD" and loud["redshift_class"] == "HIGH_Z" and loud["xray"]
    quiet = sc.classify({"primary_class": "QSO", "first__Fint": 1.0, "pan_starrs1_dr2_meanobject__iMeanPSFMag": 16.0})
    assert quiet["radio"] == "RADIO_QUIET"


def test_star_population_binarity_and_subdwarf():
    sc = _sc()
    base = {"primary_class": "STAR", "gaia_dr3__bp_rp": 0.82, "gaia_dr3__ebpminrp_gspphot": 0.0, "gaia_dr3__ag_gspphot": 0.0,
            "gaia_dr3__teff_gspphot": 5770, "gaia_dr3__parallax": 10.0, "gaia_dr3__parallax_error": 0.05,
            "gaia_dr3__phot_g_mean_mag": 9.6}
    thin = sc.classify(dict(base, **{"gaia_dr3__pmra": 30.0, "gaia_dr3__pmdec": 40.0}))          # V_T = 23.7 km/s
    assert [t["tag"] for t in thin["tags"]] == ["THIN_DISC"]
    halo = sc.classify(dict(base, **{"gaia_dr3__pmra": 400.0, "gaia_dr3__pmdec": 300.0, "gaia_dr3__ruwe": 2.1}))
    tags = {t["tag"] for t in halo["tags"]}
    assert tags == {"HALO", "ASTROMETRIC_BINARY", "HIGH_PM"}           # 500 mas/yr is also a high proper motion
    sd = sc.classify(dict(base, **{"gaia_dr3__phot_g_mean_mag": 11.4}))                          # 1.8 mag below the MS
    assert sd["luminosity_class"] == "VI" and "subdwarf" in sd["subclass"]
    var = sc.classify(dict(base, variability_class="RR_LYRAE", variability_subtype="RRAB"))
    assert any(t["tag"] == "VAR_RR_LYRAE" for t in var["tags"])


def test_galaxy_green_valley_dwarf_and_agn_type():
    sc = _sc()
    gv = sc.classify({"primary_class": "GALAXY", "galex_ais__NUVmag": 21.5, "pan_starrs1_dr2_meanobject__rMeanKronMag": 17.0})
    assert gv["activity"] == "GREEN_VALLEY"
    # g = 17.0, r = 16.6 at z = 0.01 (DM 33.18): M_B ~ -15.8 -> dwarf
    f = lambda m: 10 ** ((22.5 - m) / 2.5)
    dw = sc.classify({"primary_class": "GALAXY", "desi_legacy_surveys_dr10__flux_g": f(17.0),
                      "desi_legacy_surveys_dr10__flux_r": f(16.6), "sdss_dr18_spectroscopy__z": 0.01})
    assert any(t["tag"] == "DWARF" for t in dw["tags"]) and dw["subclass"].lower().startswith("dwarf galaxy")
    t1 = sc.classify({"primary_class": "GALAXY", "sdss_dr18_spectroscopy__subclass": "AGN BROADLINE"})
    assert any(t["tag"] == "AGN_TYPE1" for t in t1["tags"])
    t2 = sc.classify({"primary_class": "GALAXY", "sdss_dr18_spectroscopy__subclass": "AGN"})
    assert any(t["tag"] == "AGN_TYPE2" for t in t2["tags"])


def test_qso_luminosity_and_distance():
    sc = _sc()
    assert abs(sc.luminosity_distance_mpc(1.0) - 6607.7) < 1.0          # flat LCDM, H0 = 70, Om = 0.3
    bright = sc.classify({"primary_class": "QSO", "pan_starrs1_dr2_meanobject__iMeanPSFMag": 19.0, "sdss_dr18_spectroscopy__z": 2.0})
    assert any(t["tag"] == "QUASAR_LUMINOSITY" for t in bright["tags"])
    faint = sc.classify({"primary_class": "QSO", "pan_starrs1_dr2_meanobject__iMeanPSFMag": 19.0, "sdss_dr18_spectroscopy__z": 0.05})
    assert any(t["tag"] == "SEYFERT_LUMINOSITY" for t in faint["tags"])


def test_luminosity_needs_a_spectroscopic_redshift_and_a_physical_value():
    sc = _sc()
    f = lambda m: 10 ** ((22.5 - m) / 2.5)
    row = {"primary_class": "GALAXY", "desi_legacy_surveys_dr10__flux_g": f(24.0), "desi_legacy_surveys_dr10__flux_r": f(23.6)}
    lum = lambda r: {t["tag"] for t in sc.classify(r)["tags"]} & {"DWARF", "LUMINOUS", "SPEC_Z"}
    assert not lum(dict(row, simbad__rvz_redshift=0.01))                          # SIMBAD z: source unknown
    assert lum(dict(row, sdss_dr18_spectroscopy__z=0.01)) == {"SPEC_Z"}            # M_B ~ -8.8: no luminosity label


def test_more_star_galaxy_qso_attributes():
    sc = _sc()
    near = {"primary_class": "STAR", "gaia_dr3__bp_rp": 1.25, "gaia_dr3__ebpminrp_gspphot": 0.0, "gaia_dr3__ag_gspphot": 0.0,
            "gaia_dr3__parallax": 20.0, "gaia_dr3__parallax_error": 0.05, "gaia_dr3__phot_g_mean_mag": 9.7,
            "gaia_dr3__pmra": 300.0, "gaia_dr3__pmdec": 0.0, "catalogs": "Gaia DR3|eROSITA eRASS1",
            "allwise__W1mag": 7.0, "allwise__W2mag": 6.6, "allwise__W3mag": 5.0, "allwise__e_W3mag": 0.05}
    tags = {t["tag"] for t in sc.classify(near)["tags"]}
    assert {"NEARBY", "HIGH_PM", "XRAY", "IR_EXCESS"} <= tags
    # K giant at 1 kpc with M_G = 0.5 and G - Ks = 2.1: red clump
    rc = {"primary_class": "STAR", "gaia_dr3__bp_rp": 1.2, "gaia_dr3__ebpminrp_gspphot": 0.0, "gaia_dr3__ag_gspphot": 0.0,
          "gaia_dr3__parallax": 1.0, "gaia_dr3__parallax_error": 0.02, "gaia_dr3__phot_g_mean_mag": 10.5, "2mass_psc__Kmag": 8.4}
    assert any(t["tag"] == "RED_CLUMP" for t in sc.classify(rc)["tags"])
    edge = sc.classify({"primary_class": "GALAXY", "sga_2020__catalog_object_id": 1.0, "sga_2020__sga_ba": 0.25})
    assert any(t["tag"] == "EDGE_ON" for t in edge["tags"])
    f = lambda m: 10 ** ((22.5 - m) / 2.5)
    red = sc.classify({"primary_class": "QSO", "desi_legacy_surveys_dr10__flux_g": f(23.5), "desi_legacy_surveys_dr10__flux_r": f(22.8),
                       "allwise__W2mag": 15.5, "sdss_dr18_spectroscopy__z": 5.3, "pan_starrs1_dr2_meanobject__iMeanPSFMag": 21.0})
    tags = {t["tag"] for t in red["tags"]}
    assert {"OBSCURED", "VERY_HIGH_Z"} <= tags


def test_from_paper_for_unknown_objects_only():
    import pandas as pd
    sc = _sc()
    rows = pd.DataFrame([
        {"primary_class": "UNKNOWN", "simbad__otype": "GiG", "simbad__main_id": "NGC  4522", "simbad__simbad_nbref": 250,
         "simbad__simbad_ref_bibcodes": "2004AJ....127.3361K|2006ApJ...645.1047V",
         "simbad__simbad_ref_titles": "Ram pressure stripping|HI in Virgo", "simbad__simbad_ref_years": "2004|2006"},
        {"primary_class": "UNKNOWN", "ned__Type": "IrS", "ned__Object Name": "WISEA J1", "ned__References": 2},
        {"primary_class": "UNKNOWN", "catalogs": "HASH PN Catalog|Gaia DR3"},
        {"primary_class": "GALAXY", "simbad__otype": "G"},
        {"primary_class": "UNKNOWN"},
    ])
    out = sc.annotate(rows)
    assert out.loc[0, "subclass"] == "from paper: Galaxy in a group" and out.loc[0, "subclass_status"] == "FROM_PAPER"
    assert "NGC  4522" in out.loc[0, "subclass_basis"] and "250 papers" in out.loc[0, "subclass_basis"]
    assert out.loc[0, "paper_refs"].startswith("2004AJ....127.3361K (2004) Ram pressure stripping")
    assert out.loc[0, "paper_ads"].split("|")[0] == "https://ui.adsabs.harvard.edu/abs/2004AJ....127.3361K"
    assert out.loc[1, "subclass"] == "from paper: Infrared source (detection only)"
    assert out.loc[2, "paper_class"] == "Planetary nebula" and "2016JPhCS.728c2008P" in out.loc[2, "paper_refs"]
    # A classified object keeps its own sub-class; the paper class is reported alongside.
    assert out.loc[3, "subclass_status"] != "FROM_PAPER" and out.loc[3, "paper_class"] == "Galaxy"
    assert pd.isna(out.loc[4, "paper_class"]) and out.loc[4, "subclass_status"] != "FROM_PAPER"


def test_unknown_reason_explains_abstentions():
    import pandas as pd
    sc = _sc()
    rows = pd.DataFrame([
        {"primary_class": "UNKNOWN", "classification_status": "NO_EVIDENCE", "catalogs": "Pan-STARRS1 DR2 MeanObject",
         "pan_starrs1_dr2_meanobject__rMeanPSFMag": -999.0, "pan_starrs1_dr2_meanobject__nDetections": 2},
        {"primary_class": "UNKNOWN", "classification_status": "NO_EVIDENCE", "catalogs": "SDSS DR18 PhotoObj",
         "sdss_dr18_photoobj__modelMag_r": 24.3},
        {"primary_class": "UNKNOWN", "classification_status": "LOW_CONFIDENCE", "p_star": 0.45, "p_qso": 0.40, "p_galaxy": 0.15},
        {"primary_class": "STAR", "classification_status": "CLASSIFIED"},
    ])
    import importlib.util
    spec = importlib.util.spec_from_file_location("v2_units_t", ROOT.parent / "Preprocess" / "units.py")
    units = importlib.util.module_from_spec(spec); spec.loader.exec_module(units)
    out = sc.annotate(units.harmonize(rows))
    assert out.loc[0, "unknown_reason"] == "Pan-STARRS1 detection without valid mean photometry (2 detections)"
    assert "beyond the r = 22.2" in out.loc[1, "unknown_reason"]
    assert out.loc[2, "unknown_reason"].startswith("STAR or QSO")
    assert pd.isna(out.loc[3, "unknown_reason"])


def test_agb_chemistry_rules():
    sc = _sc()
    base = {"primary_class": "STAR", "variability_class": "LPV"}
    phot = lambda bp, rp, j, k, w3: {"gaia_dr3__phot_bp_mean_mag": bp, "gaia_dr3__phot_rp_mean_mag": rp,
                                     "2mass_psc__Jmag": j, "2mass_psc__Kmag": k, "allwise__W3mag": w3}
    # dW = (RP - 1.3 (BP - RP)) - (Ks - 0.686 (J - Ks)); fitted model GAIA_2MASS_WISE (dW, Ks - W3)
    c = dict(base, **phot(14.0, 10.5, 7.5, 5.5, 5.0))          # dW = 1.82, Ks - W3 = 0.5 -> P(C) ~ 0.95
    r = sc.classify(c)
    assert r["code"] == "STAR:C:AGB" and r["rule"] == "AGB_GAIA_2MASS_WISE" and r["confidence"] > 0.9
    o = dict(base, **phot(10.0, 8.0, 7.0, 5.8, 4.2))           # dW = 0.42, Ks - W3 = 1.6 -> P(C) ~ 0.27
    r = sc.classify(o)
    assert r["code"] == "STAR:M:AGB" and "silicate" in r["subclass"]
    # Near P = 0.5 the chemistry is not decided.
    u = dict(base, **phot(10.0, 8.0, 7.0, 5.8, 4.2))
    u["allwise__W3mag"] = 5.8 - 1.0                             # Ks - W3 = 1.0 with dW = 0.42 -> P(C) ~ 0.55
    assert sc.classify(u)["code"] == "STAR:?:AGB"
    # Without an AGB candidate gate the photometric models are not applied.
    plain = {k: v for k, v in c.items() if k != "variability_class"}
    assert not str(sc.classify(plain)["rule"]).startswith("AGB_")
    # Catalogue / spectral labels win over photometry.
    assert sc.classify(dict(o, suh_2021_agb_catalog__agb_subclass="CAGB_WISE"))["code"] == "STAR:C:AGB"
    assert sc.classify(dict(base, gaia_lpv_is_cstar=1))["rule"] == "GAIA_LPV_CSTAR"
    assert sc.classify(dict(base, simbad__sp_type="S4/3"))["code"] == "STAR:S:AGB"
    # A carbon dwarf / CH star from SIMBAD without AGB evidence is not called AGB.
    assert sc.classify({"primary_class": "STAR", "simbad__sp_type": "C-H4"})["code"] == "STAR:C:?"
    # Luminosity veto: with a good parallax, fainter than the red clump is not AGB.
    near = {"gaia_dr3__parallax": 2.0, "gaia_dr3__parallax_error": 0.05, "gaia_dr3__ruwe": 1.0}   # DM = 8.49
    assert sc.classify(dict(c, **near))["code"] == "STAR:C:AGB"             # M_Ks = 5.5 - 8.49 = -2.99
    assert sc.agb_chemistry(dict(c, **near, **{"2mass_psc__Kmag": 8.0, "2mass_psc__Jmag": 9.0})) is None   # M_Ks = -0.49
    dwarf = dict(base, **near, simbad__otype="C*", **{"2mass_psc__Kmag": 10.0, "gaia_dr3__phot_g_mean_mag": 14.0})
    r = sc.classify(dwarf)                                                   # M_Ks = +1.5, M_G = +5.5
    assert r["code"] == "STAR:C:V" and r["subclass"] == "Dwarf carbon star (dC)"
    giant = dict(dwarf, **{"gaia_dr3__phot_g_mean_mag": 12.0})               # M_G = +3.5: CH / subgiant carbon star
    assert sc.classify(giant)["code"] == "STAR:C:?"
    bright = dict(dwarf, **{"2mass_psc__Kmag": 5.0})                         # M_Ks = -3.5: AGB allowed
    assert sc.classify(bright)["code"] == "STAR:C:AGB"
    # WISE colours alone were 47 % correct on the Suh (2021) stars: not used.
    w = dict(base, **{"allwise__W1mag": 6.0, "allwise__W2mag": 4.6, "allwise__W3mag": 3.5, "allwise__W4mag": 3.2})
    assert sc.agb_chemistry(w) is None


def test_galaxy_emission_line_rules():
    sc = _sc()
    P = "sdss_dr18_spectroscopy__"
    def g(ha, hb, o3, n2, ew_ha, ew_n2=-1.0, d4=None, err=1.0):
        r = {"primary_class": "GALAXY", P + "line_ha_flux": ha, P + "line_hb_flux": hb, P + "line_oiii5007_flux": o3,
             P + "line_nii6584_flux": n2, P + "line_ha_ew": -ew_ha, P + "line_nii6584_ew": -ew_n2}
        for k in ("ha", "hb", "oiii5007", "nii6584"):
            r[P + "line_" + k + "_flux_err"] = err
        if d4 is not None:
            r[P + "d4000_n"] = d4
        return r
    # Test values are given negative in emission (MPA-JHU style); the row stores them positive.
    assert sc.galaxy_lines(g(100, 30, 15, 30, -20.0))[0] == "STAR_FORMING"      # x = -0.52, y = -0.30
    assert sc.galaxy_lines(g(100, 30, 150, 120, -20.0))[0] == "AGN"             # x = 0.08, y = 0.70 (Seyfert)
    assert sc.galaxy_lines(g(100, 30, 25, 60, -20.0))[0] == "COMPOSITE"         # x = -0.22, y = -0.08
    # LINER-like ratios with EW(Ha) < 3 A: retired, not AGN (WHAN).
    r = sc.galaxy_lines(g(100, 30, 60, 150, -2.0))
    assert r[0] == "QUIESCENT" and "retired" in r[2]
    assert "passive" in sc.galaxy_lines(g(1, 1, 1, 1, -0.2, -0.3, err=10))[2]
    # Weak H-beta / [O III]: WHAN on [N II]/Ha.
    assert sc.galaxy_lines(g(100, 1, 1, 20, -12.0, err=5))[0] == "STAR_FORMING"
    assert sc.galaxy_lines(g(100, 1, 1, 80, -4.0, err=5))[:2] == ("AGN", "SDSS_WHAN")          # x = -0.10
    assert sc.galaxy_lines(g(100, 1, 1, 45, -12.0, err=5))[0] == "COMPOSITE"                  # x = -0.35 (Stasinska+2006)
    # The SDSS pipeline subclass keeps precedence.
    row = dict(g(100, 30, 150, 120, -20.0), **{P + "subclass": "STARFORMING"})
    assert sc.classify(row)["activity"] == "STAR_FORMING"
    # Dn4000 alone (no line measurement).
    assert sc.galaxy_lines({P + "d4000_n": 1.8})[1] == "SDSS_D4000"


def test_spectroscopic_star_parameters_and_emission_lines():
    sc = _sc()
    base = {"primary_class": "STAR", "gaia_dr3__bp_rp": 1.2, "gaia_dr3__teff_gspphot": 4600.0, "gaia_dr3__logg_gspphot": 4.5}
    # LAMOST LASP log g outranks GSP-Phot log g (no parallax).
    r = sc.classify(dict(base, lamost_dr_catalog__lasp_teff=4600.0, lamost_dr_catalog__lasp_logg=2.4, lamost_dr_catalog__lasp_feh=-1.6))
    assert r["luminosity_class"] == "III" and r["luminosity_rule"] == "LAMOST_LOGG"
    tags = {t["tag"]: t for t in sc.star_tags(dict(base, lamost_dr_catalog__lasp_teff=4600.0, lamost_dr_catalog__lasp_logg=2.4,
                                                     lamost_dr_catalog__lasp_feh=-2.3, gaia_dr3__mh_gspphot=-0.2,
                                                     gaia_dr3__phot_g_mean_mag=14.0))}
    assert "VERY_METAL_POOR" in tags and tags["VERY_METAL_POOR"]["rule"] == "LAMOST_FEH"
    # GSP-Spec only with clean flags (positions 2, 5, 8, 13 for log g).
    good, bad = "0" * 41, "0" + "1" + "0" * 39
    gs = dict(base, gaia_dr3__teff_gspspec=4700.0, gaia_dr3__logg_gspspec=2.6)
    assert sc.classify(dict(gs, gaia_dr3__flags_gspspec=good))["luminosity_rule"] == "GSPSPEC_LOGG"
    assert sc.classify(dict(gs, gaia_dr3__flags_gspspec=bad))["luminosity_rule"] == "GAIA_LOGG"
    # ESP-ELS: young stars and WR stars get their own class; Be stars a tag.
    assert sc.classify(dict(base, gaia_dr3__classlabel_espels="TTauri", gaia_dr3__classlabel_espels_flag=1))["code"] == "STAR:YSO"
    assert sc.classify(dict(base, gaia_dr3__classlabel_espels="wN", gaia_dr3__classlabel_espels_flag=0))["code"] == "STAR:WR"
    assert sc.classify(dict(base, gaia_dr3__classlabel_espels="TTauri", gaia_dr3__classlabel_espels_flag=4))["code"] != "STAR:YSO"
    be = {t["tag"] for t in sc.star_tags(dict(base, gaia_dr3__classlabel_espels="beStar", gaia_dr3__classlabel_espels_flag=2))}
    assert "EMISSION_LINE" in be
    # A YSO or a spectroscopic dwarf in the AGB gate is not an AGB star.
    lpv = {"primary_class": "STAR", "variability_class": "LPV", "gaia_dr3__phot_bp_mean_mag": 10.0, "gaia_dr3__phot_rp_mean_mag": 8.0,
           "2mass_psc__Jmag": 7.0, "2mass_psc__Kmag": 5.8, "allwise__W3mag": 4.2}
    assert sc.classify(lpv)["code"] == "STAR:M:AGB"
    assert sc.agb_chemistry(dict(lpv, gaia_dr3__classlabel_espels="TTauri", gaia_dr3__classlabel_espels_flag=1)) is None
    assert sc.agb_chemistry(dict(lpv, lamost_dr_catalog__lasp_teff=3900.0, lamost_dr_catalog__lasp_logg=4.6)) is None

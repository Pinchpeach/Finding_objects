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
    assert sc.classify({"primary_class": "STAR", "sdss_dr18_spectroscopy__subclass": "CarbonWD"})["code"] == "STAR:C"
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
    assert tags == {"HALO", "ASTROMETRIC_BINARY"}
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
    assert not sc.classify(dict(row, simbad__rvz_redshift=0.01))["tags"]          # SIMBAD z: source unknown
    assert not sc.classify(dict(row, sdss_dr18_spectroscopy__z=0.01))["tags"]     # M_B ~ -8.8: inconsistent, no label

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

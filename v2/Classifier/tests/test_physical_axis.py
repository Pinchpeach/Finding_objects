#!/usr/bin/env python3
"""Dependency-light smoke tests for physical-axis routing."""

from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "axes" / "physical.py"
spec = importlib.util.spec_from_file_location("physical_axis", path)
physical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(physical)


def check(name, row, label, status=None):
    result = physical.classify(row)
    assert result["label"] == label, (name, result)
    if status is not None:
        assert result["status"] == status, (name, result)
    print(f"[OK] {name}: {result['label']} / {result['status']}")


# Strong Gaia DSC WD posterior on the GF21 HR locus (M_G = 10.5 at BP-RP 0)
# routes WD ...
check(
    "dsc_wd",
    {
        "primary_class": "STAR",
        "classprob_dsc_combmod_whitedwarf": 0.95,
        "classprob_dsc_combmod_star": 0.02,
        "parallax": 20.0,
        "parallax_error": 0.1,
        "phot_g_mean_mag": 14.0,
        "bp_rp": 0.0,
    },
    "WD",
    "CLASSIFIED_WD",
)
# ... but the DSC WD class alone (purity 0.25; Delchambre+2023) does not.
check(
    "dsc_wd_only",
    {
        "primary_class": "STAR",
        "classprob_dsc_combmod_whitedwarf": 0.95,
        "classprob_dsc_combmod_star": 0.02,
    },
    "UNKNOWN",
    "INSUFFICIENT_PHYSICAL_EVIDENCE",
)
# A Suh (2021) match fainter than the red clump (M_Ks = 3.0) is not AGB.
check(
    "suh_dwarf_carbon",
    {
        "primary_class": "STAR",
        "catalogs": "Suh 2021 AGB Catalog",
        "gaia_dr3__parallax": 10.0,
        "gaia_dr3__parallax_error": 0.1,
        "gaia_dr3__ruwe": 1.0,
        "2mass_psc__Kmag": 8.0,
    },
    "UNKNOWN",
    "SUH2021_MATCH_BELOW_RED_CLUMP",
)

# A cool star below the Ciardi giant log g boundary is a red giant (RGB or
# AGB; GSP-Phot luminosity class 96.9 % vs APOGEE, 2.13.0) ...
check(
    "cool_giant",
    {
        "primary_class": "STAR",
        "classprob_dsc_combmod_star": 0.96,
        "teff_gspphot": 4800,
        "logg_gspphot": 2.2,
    },
    "RED_GIANT",
    "RED_GIANT_GAIA_LOGG",
)
# ... while a secure stellar posterior alone (a dwarf) does not fabricate a
# physical/evolutionary state.
check(
    "ordinary_star",
    {
        "primary_class": "STAR",
        "classprob_dsc_combmod_star": 0.96,
        "teff_gspphot": 5600,
        "logg_gspphot": 4.4,
    },
    "UNKNOWN",
    "STAR_LIKE_NO_VALIDATED_PHYSICAL_STATE",
)

# Non-stellar coarse classes must not enter the stellar physical branch.
check("qso_route", {"primary_class": "QSO"}, "UNKNOWN", "NOT_STELLAR_ROUTE")

# No evidence must abstain.
check("missing_evidence", {"primary_class": "STAR"}, "UNKNOWN", "INSUFFICIENT_PHYSICAL_EVIDENCE")


def test_hot_subdwarf_gaia_cmd_culpan2022():
    import importlib.util
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "axes" / "physical.py"
    s = importlib.util.spec_from_file_location("phys_hsd_t", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    base = {"primary_class": "STAR", "gaia_dr3__parallax_error": 0.05, "gaia_dr3__phot_bp_rp_excess_factor": 1.15}
    sdo = dict(base, gaia_dr3__bp_rp=-0.35, gaia_dr3__phot_g_mean_mag=11.6, gaia_dr3__parallax=2.5)  # M_G 3.6
    r = m.classify(sdo)
    assert r["label"] == "HOT_SUBDWARF" and r["status"] == "GAIA_CMD_HOT_SUBLUMINOUS"
    # main-sequence A0V (M_G 0.6), white dwarf (M_G 11), poor parallax, blended photometry: not selected
    assert (
        m.hot_subdwarf_evidence(dict(base, gaia_dr3__bp_rp=0.0, gaia_dr3__phot_g_mean_mag=7.1, gaia_dr3__parallax=5))
        is None
    )
    assert (
        m.hot_subdwarf_evidence(dict(base, gaia_dr3__bp_rp=0.0, gaia_dr3__phot_g_mean_mag=17.5, gaia_dr3__parallax=5))
        is None
    )
    assert m.hot_subdwarf_evidence(dict(sdo, gaia_dr3__parallax_error=1.0)) is None
    assert m.hot_subdwarf_evidence(dict(sdo, gaia_dr3__phot_bp_rp_excess_factor=1.9)) is None


def test_galaxy_zoo_desi_morphology():
    import importlib.util
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "subclass.py"
    s = importlib.util.spec_from_file_location("sc_gz", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    g = "galaxy_zoo_desi__gz_"
    assert m.galaxy_profile({g + "SFSM": 0.8, g + "SFFDF": 0.2})[0] == "EARLY_TYPE"
    assert m.galaxy_profile({g + "SFSM": 0.1, g + "SFFDF": 0.85, g + "SAYes": 0.9})[0] == "SPIRAL"
    assert m.galaxy_profile({g + "SFSM": 0.1, g + "SFFDF": 0.85, g + "SAYes": 0.2})[0] == "DISK"
    # no majority: falls back to the Legacy Surveys profile
    assert m.galaxy_profile({g + "SFSM": 0.45, g + "SFFDF": 0.45, "desi_legacy_surveys_dr10__type": "DEV"})[1] == "LS_DEV"
    assert m.galaxy_merger({g + "MMaD": 0.3, g + "MM": 0.3}) is not None
    assert m.galaxy_merger({g + "MMaD": 0.1, g + "MM": 0.1}) is None


def test_provenance_separates_lookup_from_inference():
    import importlib.util
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "provenance.py"
    s = importlib.util.spec_from_file_location("prov_t", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    assert m.of_rule("SIMBAD_CURATED_WD") == "CATALOG"
    assert m.of_rule("LAMOST_SUBCLASS") == "CATALOG"
    assert m.of_rule("GAIA_DR3_SOS_RRLYRAE") == "EXTERNAL_CLASSIFIER"
    assert m.of_rule("GZ_DESI_SPIRAL") == "EXTERNAL_CLASSIFIER"
    assert m.of_rule("GAIA_CMD_HOT_SUBLUMINOUS") == "INFERRED"
    assert m.of_rule("RADIO_STEEP_COMPACT") == "INFERRED"
    assert m.of_rule("NO_VARIABILITY_EVIDENCE") == "NONE"
    spec = json.dumps([{"rule_id": "SPC-SDSS-003", "class": "QSO", "score": 0.9}])
    assert m.of_primary("QSO", spec) == "CATALOG"
    assert m.of_primary("STAR", json.dumps([{"rule_id": "DSC-001", "class": "STAR", "score": 0.99}])) == "INFERRED"


def test_lamost_double_star_is_not_a_white_dwarf():
    import importlib.util
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "subclass.py"
    s = importlib.util.spec_from_file_location("sc_ds", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    r = m.classify_star({"lamost_dr_catalog__SubClass": "DoubleStar"})
    assert not (r and r.get("code") == "STAR:WD")
    assert m.classify_star({"lamost_dr_catalog__SubClass": "DA"})["code"] == "STAR:WD"
    # dust in front of a star: continuous through the plane, unchanged at high latitude
    f = m.dust_fraction_in_front
    assert abs(f(1000, 30, 0.0) - f(1000, 30, 0.001)) < 1e-3 and 0 < f(1000, 30, 0.0) < 0.2
    # sech^2 layer, h = 188 pc at the solar circle (Drimmel & Spergel 2001; 2.53.0): tanh(100 sin 60 / 188)
    assert abs(f(100, 30, 60) - 0.4307) < 1e-3


def test_2_53_error_aware_wd_locus():
    """GF21 decide with an error-aware probability; the gate uses P(on the WD
    side of M_G = 6 + 5(BP-RP)) >= 0.75, off it at <= 0.25, else abstains."""
    import importlib.util
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "branches" / "star.py"
    s = importlib.util.spec_from_file_location("star_wd_p", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    assert m.DEFAULT_HR_GATE == "plx4_or_pm10_p75"
    wd = {"parallax": 20.0, "parallax_error": 0.2, "phot_g_mean_mag": 15.0, "bp_rp": 0.0}  # M_G = 11.5
    assert m._wd_hr_signal(wd) is True
    ms = dict(wd, phot_g_mean_mag=8.0)  # M_G = 4.5: main sequence side
    assert m._wd_hr_signal(ms) is False
    # 0.1 mag below the line with a 20 % parallax error: P = 0.59, abstain
    near = {"parallax": 5.0, "parallax_error": 1.0, "phot_g_mean_mag": 12.6, "bp_rp": 0.0}  # M_G = 6.1
    prob = m.wd_locus_probability(5.0, 1.0, 12.6, 0.0)
    assert 0.25 < prob < 0.75 and m._wd_hr_signal(near) is None
    # a colour error widens the probability towards 0.5
    assert abs(m.wd_locus_probability(5.0, 1.0, 12.6, 0.0, 0.3) - 0.5) < abs(prob - 0.5)

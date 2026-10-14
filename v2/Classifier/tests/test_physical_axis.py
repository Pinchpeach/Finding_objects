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

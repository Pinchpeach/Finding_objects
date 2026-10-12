#!/usr/bin/env python3
"""Dependency-light smoke tests for physical-axis routing."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"axes"/"physical.py"
spec=importlib.util.spec_from_file_location("physical_axis",path)
physical=importlib.util.module_from_spec(spec); spec.loader.exec_module(physical)

def check(name,row,label,status=None):
    result=physical.classify(row)
    assert result["label"]==label,(name,result)
    if status is not None:
        assert result["status"]==status,(name,result)
    print(f"[OK] {name}: {result['label']} / {result['status']}")

# Strong Gaia DSC WD posterior: validated existing STAR branch should route WD.
check("dsc_wd",{
    "primary_class":"STAR",
    "classprob_dsc_combmod_whitedwarf":0.95,
    "classprob_dsc_combmod_star":0.02,
},"WD","CLASSIFIED_WD")

# A cool star below the Ciardi giant log g boundary is a red giant (RGB or
# AGB; GSP-Phot luminosity class 96.9 % vs APOGEE, 2.13.0) ...
check("cool_giant",{
    "primary_class":"STAR",
    "classprob_dsc_combmod_star":0.96,
    "teff_gspphot":4800,
    "logg_gspphot":2.2,
},"RED_GIANT","RED_GIANT_GAIA_LOGG")
# ... while a secure stellar posterior alone (a dwarf) does not fabricate a
# physical/evolutionary state.
check("ordinary_star",{
    "primary_class":"STAR",
    "classprob_dsc_combmod_star":0.96,
    "teff_gspphot":5600,
    "logg_gspphot":4.4,
},"UNKNOWN","STAR_LIKE_NO_VALIDATED_PHYSICAL_STATE")

# Non-stellar coarse classes must not enter the stellar physical branch.
check("qso_route",{"primary_class":"QSO"},"UNKNOWN","NOT_STELLAR_ROUTE")

# No evidence must abstain.
check("missing_evidence",{"primary_class":"STAR"},"UNKNOWN","INSUFFICIENT_PHYSICAL_EVIDENCE")

#!/usr/bin/env python3
"""Smoke tests for Gaia-backed multi-axis routes."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(rel,name):
    path=ROOT/rel
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

physical=load("axes/physical.py","physical")
variability=load("axes/variability.py","variability")
phenomenon=load("axes/phenomenon.py","phenomenon")

def expect(module,row,label,status):
    result=module.classify(row)
    assert result["label"]==label,result
    assert result["status"]==status,result
    return result

# Gaia FLAME: RGB base..tip plus validated giant guardrails.
expect(physical,{
    "primary_class":"STAR",
    "classprob_dsc_combmod_star":0.96,
    "evolstage_flame":700,
    "logg_gspphot":2.4,
    "mass_flame":1.2,
    "age_flame":5.0,
},"RGB","GAIA_FLAME_RGB")

# Same stage but outside validated mass regime must abstain from RGB/AGB.
r=physical.classify({
    "primary_class":"STAR",
    "classprob_dsc_combmod_star":0.96,
    "evolstage_flame":700,
    "logg_gspphot":2.4,
    "mass_flame":2.5,
    "age_flame":1.5,
})
assert r["label"]=="OTHER_STELLAR",r

# Published Gaia DR3 variability groups.
expect(variability,{"best_class_name":"RR","best_class_score":0.91},"RR_LYRAE","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"CEP","best_class_score":0.88},"CEPHEID","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"LPV","best_class_score":0.85},"LPV","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"ECL","best_class_score":0.82},"ECLIPSING","GAIA_DR3_VARIABLE_CANDIDATE")

# SN is an event route, not a stellar variability subtype.
expect(variability,{"best_class_name":"SN","best_class_score":0.93},"UNKNOWN","ROUTED_TO_PHENOMENON")
expect(phenomenon,{"best_class_name":"SN","best_class_score":0.93},"SN","GAIA_DR3_SN_CANDIDATE")
expect(phenomenon,{"best_class_name":"MICROLENSING","best_class_score":0.90},"MICROLENSING","GAIA_DR3_MICROLENSING_CANDIDATE")

# Gaia score must not be copied into calibrated confidence.
assert variability.classify({"best_class_name":"RR","best_class_score":0.99})["confidence"] is None
assert phenomenon.classify({"best_class_name":"SN","best_class_score":0.99})["confidence"] is None

print("[OK] Gaia-backed RGB/variability/phenomenon routes")

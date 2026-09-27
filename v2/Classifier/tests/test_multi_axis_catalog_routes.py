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
compact=load("axes/compact.py","compact")
extragalactic=load("axes/extragalactic.py","extragalactic")

def expect(module,row,label,status):
    result=module.classify(row)
    assert result["label"]==label,result
    assert result["status"]==status,result
    return result

expect(physical,{
    "primary_class":"STAR","classprob_dsc_combmod_star":0.96,
    "evolstage_flame":700,"logg_gspphot":2.4,"mass_flame":1.2,"age_flame":5.0,
},"RGB","GAIA_FLAME_RGB")

r=physical.classify({
    "primary_class":"STAR","classprob_dsc_combmod_star":0.96,
    "evolstage_flame":700,"logg_gspphot":2.4,"mass_flame":2.5,"age_flame":1.5,
})
assert r["label"]=="OTHER_STELLAR",r

expect(variability,{"otype":"Mi*"},"MIRA","SIMBAD_CURATED_VARIABLE_TYPE")
expect(variability,{"otype":"RR*"},"RR_LYRAE","SIMBAD_CURATED_VARIABLE_TYPE")
expect(variability,{"otype":"Ce*"},"CEPHEID","SIMBAD_CURATED_VARIABLE_TYPE")
expect(variability,{"otype":"EB*"},"ECLIPSING","SIMBAD_CURATED_VARIABLE_TYPE")
expect(variability,{"best_class_name":"RR","best_class_score":0.91},"RR_LYRAE","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"CEP","best_class_score":0.88},"CEPHEID","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"LPV","best_class_score":0.85},"LPV","GAIA_DR3_VARIABLE_CANDIDATE")
expect(variability,{"best_class_name":"ECL","best_class_score":0.82},"ECLIPSING","GAIA_DR3_VARIABLE_CANDIDATE")

expect(variability,{"best_class_name":"SN","best_class_score":0.93},"UNKNOWN","ROUTED_TO_PHENOMENON")
expect(phenomenon,{"best_class_name":"SN","best_class_score":0.93},"SN","GAIA_DR3_SN_CANDIDATE")
expect(phenomenon,{"best_class_name":"MICROLENSING","best_class_score":0.90},"MICROLENSING","GAIA_DR3_MICROLENSING_CANDIDATE")

expect(compact,{"catalogs":"ATNF Pulsar Catalog","association_confidence__atnf_pulsar_catalog":0.97},"PULSAR","ATNF_CATALOG_MATCH")
expect(compact,{"otype":"N*"},"NS","SIMBAD_CURATED_NS")
expect(compact,{"otype":"Psr"},"PULSAR","SIMBAD_CURATED_PULSAR")
expect(compact,{"otype":"XB*"},"XRB","SIMBAD_CURATED_XRB")
expect(compact,{"in_vari_compact_companion":True},"COMPACT_COMPANION_CANDIDATE","GAIA_DR3_COMPACT_COMPANION_CANDIDATE")
expect(compact,{},"UNKNOWN","NO_VALIDATED_COMPACT_EVIDENCE")

expect(physical,{"catalogs":"Suh 2021 AGB Catalog","agb_subclass":"OAGB_WISE","association_confidence__suh_2021_agb_catalog":0.93},"AGB","SUH2021_AGB_CATALOG_MATCH")
expect(physical,{"otype":"AGB*","primary_class":"STAR"},"AGB","SIMBAD_CURATED_AGB")
expect(phenomenon,{"otype":"SN*"},"SN","SIMBAD_CURATED_SN")
expect(phenomenon,{"otype":"PN"},"PN","SIMBAD_CURATED_PN")
expect(phenomenon,{"otype":"No*"},"NOVA","SIMBAD_CURATED_NOVA")

expect(extragalactic,{"best_class_name":"AGN","in_vari_agn":True,"primary_class":"QSO"},"AGN","GAIA_DR3_AGN_CANDIDATE")
expect(extragalactic,{"primary_class":"QSO"},"QSO","COARSE_QSO_ROUTE")
expect(extragalactic,{"primary_class":"GALAXY"},"GALAXY","COARSE_GALAXY_ROUTE")

assert variability.classify({"best_class_name":"RR","best_class_score":0.99})["confidence"] is None
assert phenomenon.classify({"best_class_name":"SN","best_class_score":0.99})["confidence"] is None
assert compact.classify({"in_vari_compact_companion":True})["label"]!="NS"

print("[OK] Gaia-backed physical/variability/compact/extragalactic/phenomenon routes")

"""Physical/evolutionary-state axis.

Evidence priority:
1. Dedicated AGB catalog / exact curated SIMBAD physical type.
2. Validated WD routing from branches/star.py.
3. Gaia FLAME RGB refinement.
Unsupported/candidate labels abstain rather than being promoted.
"""
from __future__ import annotations
import importlib.util
import math
from pathlib import Path

AXIS="physical"
CLASSES=("WD","RGB","AGB","OTHER_STELLAR","UNKNOWN")
ROOT=Path(__file__).resolve().parents[1]

def _load_branch(name):
    path=ROOT/"branches"/f"{name}.py"
    spec=importlib.util.spec_from_file_location(f"classifier_branch_{name}",path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load classifier branch: {path}")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def _text(row,key):
    value=row.get(key)
    if value is None:return None
    value=str(value).strip()
    return None if not value or value.lower()=="nan" else value

def _num(row,key):
    try:
        value=float(row.get(key))
        return value if math.isfinite(value) else None
    except Exception:return None

STAR=_load_branch("star")
EVOLVED=_load_branch("evolved_star")

def classify(row):
    catalogs=_text(row,"catalogs") or ""
    if "Suh 2021 AGB Catalog" in catalogs:
        assoc=_num(row,"association_confidence__suh_2021_agb_catalog")
        subclass=_text(row,"agb_subclass")
        return {
            "axis":AXIS,"label":"AGB","confidence":None,"status":"SUH2021_AGB_CATALOG_MATCH",
            "evidence":[{
                "kind":"suh2021_agb_catalog_counterpart",
                "agb_subclass":subclass,
                "association_confidence":assoc,
                "note":"Counterpart is listed in the Suh (2021) Galactic O-rich/C-rich AGB compilation.",
            }],
        }

    simbad=_text(row,"otype")
    if simbad=="AGB*":
        return {
            "axis":AXIS,"label":"AGB","confidence":None,"status":"SIMBAD_CURATED_AGB",
            "evidence":[{"kind":"simbad_physical_type","otype":"AGB*","note":"Exact SIMBAD Asymptotic Giant Branch Star physical type."}],
        }

    coarse=str(row.get("primary_class","")).strip().upper()
    # A coarse UNKNOWN must not veto stronger stellar-physics evidence.  Only a
    # positive extragalactic coarse route blocks the stellar physical branch.
    if coarse in {"GALAXY","QSO"}:
        return {
            "axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_STELLAR_ROUTE",
            "evidence":[{"kind":"coarse_route","primary_class":coarse}],
        }

    star=STAR.classify(row)
    family=star.get("stellar_family")
    evidence=[{
        "kind":"star_branch",
        "stellar_family":family,
        "stellar_family_score":star.get("stellar_family_score"),
        "basis":star.get("basis"),
        "wd_hr_locus_signal":star.get("wd_hr_locus_signal"),
        "spectral_type":star.get("spectral_type"),
        "spectral_type_confidence":star.get("spectral_type_confidence"),
    }]

    if family=="WHITE_DWARF_CANDIDATE":
        return {"axis":AXIS,"label":"WD","confidence":star.get("stellar_family_score"),"status":"CLASSIFIED_WD","evidence":evidence}

    evolved=EVOLVED.classify(row)
    evidence.extend(evolved.get("evidence",[]))
    if evolved.get("label") in {"RGB","AGB"}:
        return {"axis":AXIS,"label":evolved["label"],"confidence":evolved.get("confidence"),"status":evolved.get("status","CLASSIFIED"),"evidence":evidence}

    if family in {"STAR_LIKE","BINARY_CANDIDATE"}:
        return {"axis":AXIS,"label":"OTHER_STELLAR","confidence":star.get("stellar_family_score"),"status":"STELLAR_UNREFINED","evidence":evidence}

    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"INSUFFICIENT_PHYSICAL_EVIDENCE","evidence":evidence}

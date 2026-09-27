"""Physical/evolutionary-state axis.

Validated WD routing is reused from branches/star.py. RGB/AGB refinement is kept
in a separate evolved-star branch and abstains until its model is validated.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

AXIS="physical"
CLASSES=("WD","RGB","AGB","OTHER_STELLAR","UNKNOWN")
ROOT=Path(__file__).resolve().parents[1]

def _load_branch(name):
    path=ROOT/"branches"/f"{name}.py"
    spec=importlib.util.spec_from_file_location(f"classifier_branch_{name}",path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load classifier branch: {path}")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

STAR=_load_branch("star")
EVOLVED=_load_branch("evolved_star")

def classify(row):
    coarse=str(row.get("primary_class","")).strip().upper()
    if coarse not in {"STAR",""}:
        return {
            "axis":AXIS,
            "label":"UNKNOWN",
            "confidence":None,
            "status":"NOT_STELLAR_ROUTE",
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
        confidence=star.get("stellar_family_score")
        status="CLASSIFIED_WD"
        # HR-only WD evidence is scientifically useful but not a calibrated
        # probability, so confidence remains None rather than inventing one.
        return {
            "axis":AXIS,
            "label":"WD",
            "confidence":confidence,
            "status":status,
            "evidence":evidence,
        }

    evolved=EVOLVED.classify(row)
    evidence.extend(evolved.get("evidence",[]))
    if evolved.get("label") in {"RGB","AGB"}:
        return {
            "axis":AXIS,
            "label":evolved["label"],
            "confidence":evolved.get("confidence"),
            "status":evolved.get("status","CLASSIFIED"),
            "evidence":evidence,
        }

    if family in {"STAR_LIKE","BINARY_CANDIDATE"}:
        return {
            "axis":AXIS,
            "label":"OTHER_STELLAR",
            "confidence":star.get("stellar_family_score"),
            "status":"STELLAR_UNREFINED",
            "evidence":evidence,
        }

    return {
        "axis":AXIS,
        "label":"UNKNOWN",
        "confidence":None,
        "status":"INSUFFICIENT_PHYSICAL_EVIDENCE",
        "evidence":evidence,
    }

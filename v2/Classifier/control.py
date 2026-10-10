#!/usr/bin/env python3
"""Main detailed-classifier controller.

Runs legacy coarse-class detail branches for compatibility, then all independent
multi-axis classifiers (physical, variability, compact, extragalactic,
phenomenon). One failed/unsupported scientific branch should abstain rather than
invent a class.
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
from common import load_module, read_table, records, write_table  # noqa: E402

BRANCH = {"STAR": "star.py", "GALAXY": "galaxy.py", "QSO": "qso.py"}


def load_branch(name):
    return load_module(ROOT / "branches" / name, "detail_" + name.replace(".py", ""))


def load_axes_controller():
    return load_module(ROOT / "control_axes.py", "classifier_control_axes")


def annotate_legacy(d: pd.DataFrame, rows=None) -> pd.DataFrame:
    mods = {k: load_branch(v) for k, v in BRANCH.items()}
    payload = []
    labels = []
    conf = []
    stellar_family = []
    spectral_type = []
    variability_class = []
    for row in (rows if rows is not None else records(d)):
        coarse = str(row.get("primary_class", "UNKNOWN"))
        if coarse in mods:
            res = mods[coarse].classify(row)
        else:
            res = {
                "detailed_class": "UNRESOLVED",
                "confidence": None,
                "basis": "coarse class UNKNOWN; detailed classification skipped",
            }
        payload.append(json.dumps(res, separators=(",", ":")))
        labels.append(res.get("detailed_class", "UNRESOLVED"))
        conf.append(res.get("confidence"))
        stellar_family.append(res.get("stellar_family"))
        spectral_type.append(res.get("spectral_type"))
        var = res.get("variability") if isinstance(res.get("variability"), dict) else {}
        variability_class.append(var.get("class"))
    return d.assign(
        detailed_class=labels,
        detailed_confidence=conf,
        stellar_family=stellar_family,
        spectral_type=spectral_type,
        variability_class_legacy=variability_class,
        detailed_result_json=payload,
    )


def load_subclass():
    return load_module(ROOT / "subclass.py", "classifier_subclass")


def run(inp, out=None) -> pd.DataFrame:
    """Coarse-classified objects (file or DataFrame) -> detailed classification."""
    d = read_table(inp)
    if "primary_class" not in d.columns:
        raise KeyError("primary_class is required from v2/Preprocess")
    # One dict conversion shared by the legacy branches, the axes and the
    # sub-class step; none of them reads another's output columns.
    rows = records(d)
    d = annotate_legacy(d, rows)
    d = load_axes_controller().annotate(d, rows)
    d = load_subclass().annotate(d, rows)
    return write_table(d, out, f"[OK] full classifier rows={len(d)} axes=5")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, default=ROOT / "classified_objects.csv")
    a = p.parse_args()
    run(a.input, a.out)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the independent classifier axes, then apply per-axis calibration."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
from common import load_module, read_table, records, write_table  # noqa: E402

AXES = ("physical", "variability", "compact", "extragalactic", "phenomenon")


def annotate(df: pd.DataFrame, rows=None) -> pd.DataFrame:
    """Add ``<axis>_class/_subtype/_confidence/_status/_evidence_json`` per axis."""
    rows = records(df) if rows is None else rows
    additions = {}
    for name in AXES:
        results = [load_module(ROOT / "axes" / f"{name}.py", f"classifier_axis_{name}").classify(row) for row in rows]
        additions[f"{name}_class"] = [r["label"] for r in results]
        additions[f"{name}_subtype"] = [r.get("subtype") for r in results]
        additions[f"{name}_confidence"] = [r["confidence"] for r in results]
        additions[f"{name}_status"] = [r["status"] for r in results]
        additions[f"{name}_evidence_json"] = [
            json.dumps(r["evidence"], ensure_ascii=False, separators=(",", ":")) for r in results
        ]
    result = pd.concat([df.reset_index(drop=True), pd.DataFrame(additions)], axis=1)
    calibration = load_module(ROOT / "calibration" / "per_axis.py", "classifier_per_axis_calibration")
    return calibration.annotate(result, ROOT / "calibration" / "models.json", AXES)


def run(inp, out=None) -> pd.DataFrame:
    result = annotate(read_table(inp))
    return write_table(result, out, f"[OK] full multi-axis classification rows={len(result)} axes={len(AXES)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=ROOT / "classifier_input.csv")
    p.add_argument("--out", type=Path, default=ROOT / "multi_axis_classification.csv")
    a = p.parse_args()
    run(a.input, a.out)


if __name__ == "__main__":
    main()

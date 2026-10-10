#!/usr/bin/env python3
"""Check that the coarse classifier output can enter the detailed classifier.

``validate`` only checks (the pipeline passes the table on unchanged); the
command line copies the checked table to ``--out`` as before.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
if str(V2) not in sys.path:
    sys.path.insert(0, str(V2))
from common import read_table, write_table  # noqa: E402

ALLOWED = {"STAR", "GALAXY", "QSO", "UNKNOWN"}


def validate(d: pd.DataFrame) -> pd.DataFrame:
    if "primary_class" not in d:
        raise KeyError("primary_class is required from v2/Preprocess")
    bad = sorted(set(d.primary_class.dropna().astype(str)) - ALLOWED)
    if bad:
        raise ValueError(f"unsupported coarse classes: {bad}")
    return d


def run(inp, out=None) -> pd.DataFrame:
    d = validate(read_table(inp))
    return write_table(d, out, f"[OK] prepared {len(d)} rows")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "classifier_input.csv")
    a = p.parse_args()
    run(a.input, a.out)


if __name__ == "__main__":
    main()

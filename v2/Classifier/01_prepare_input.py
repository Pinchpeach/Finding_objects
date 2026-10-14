#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import importlib.util as _tio_u

_tio_s = _tio_u.spec_from_file_location(
    "v2_table_io", Path(__file__).resolve().parents[1] / "Preprocess" / "table_io.py"
)
TABLE_IO = _tio_u.module_from_spec(_tio_s)
_tio_s.loader.exec_module(TABLE_IO)

ALLOWED = {"STAR", "GALAXY", "QSO", "UNKNOWN"}


def run(inp: Path, out: Path):
    d = TABLE_IO.read_table(inp)
    if "primary_class" not in d:
        raise KeyError("primary_class is required from v2/Preprocess")
    bad = sorted(set(d.primary_class.dropna().astype(str)) - ALLOWED)
    if bad:
        raise ValueError(f"unsupported coarse classes: {bad}")
    out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(out, index=False)
    print(f"[OK] prepared {len(d)} rows -> {out}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "classifier_input.csv")
    a = p.parse_args()
    run(a.input, a.out)


if __name__ == "__main__":
    main()

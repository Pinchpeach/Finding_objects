"""Helpers shared by the v2 pipeline, classifier and app.

* ``load_module``: import a file by path, once. Stage scripts are named
  ``01_...py`` (not importable by name), and before this helper each module
  carried its own copy of the importlib boilerplate.
* ``num`` / ``row_num`` / ``text``: tolerant readers for catalogue values.
  NaN, None, empty strings and non-numeric text all mean "no value".
* ``records``: table rows as dicts **without empty cells**. The integrated
  object table is wide (~1300 columns: every catalogue's fields) and mostly
  empty (each object is in a few catalogues; 83 % of cells are empty on the
  NGC 4522 test field). Full ``to_dict("records")`` rows held ~4 million
  Python objects for 3000 objects and set the pipeline's peak memory. Code
  reading rows uses ``.get`` and treats a missing key like NaN.
* ``read_table`` / ``write_table``: stages accept a path or a DataFrame and
  write only when given an output path, so ``pipeline.py`` can pass tables in
  memory while the stage scripts keep their file-to-file command line.
"""

from __future__ import annotations
import importlib.util
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_module(path, name: str | None = None):
    """Import the Python file at ``path`` (once per path) and return the module.

    The file's folder is put on ``sys.path`` so it can import its neighbours.
    """
    path = Path(path).resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name or f"v2_{path.parent.name}_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def num(value) -> float | None:
    """A finite float, or None."""
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def row_num(row, *keys) -> float | None:
    """The first finite number among ``row[key]`` for ``keys``."""
    for key in keys:
        x = num(row.get(key))
        if x is not None:
            return x
    return None


def text(row, *keys) -> str | None:
    """The first of ``row[key]`` for ``keys`` that is a non-empty string (stripped)."""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        s = str(value).strip()
        if s and s.lower() not in {"nan", "none", "<na>"}:
            return s
    return None


def records(df: pd.DataFrame, columns=None) -> list[dict]:
    """Rows of ``df`` as dicts holding only the non-empty cells."""
    rows: list[dict] = [{} for _ in range(len(df))]
    for col in (df.columns if columns is None else columns):
        s = df[col]
        present = np.flatnonzero(s.notna().to_numpy())
        if len(present) == 0:
            continue
        for i, v in zip(present.tolist(), s.iloc[present].tolist()):
            rows[i][col] = v
    return rows


def read_table(source, **read_csv_kwargs) -> pd.DataFrame:
    """A DataFrame as given, or read from a CSV path."""
    return source if isinstance(source, pd.DataFrame) else pd.read_csv(source, **read_csv_kwargs)


def write_table(df: pd.DataFrame, out, message: str = "") -> pd.DataFrame:
    """Write ``df`` to ``out`` when a path is given; return ``df``."""
    if out is not None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
    if message:
        print(message + (f" -> {out}" if out is not None else ""))
    return df

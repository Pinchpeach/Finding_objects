"""CSV reading that keeps catalogue identifiers exact (2.23.0).

Gaia source_id, SDSS objID / specObjID, PS1 objID, Legacy Surveys ls_id and
DESI TARGETID are 64-bit integers.  Read as float64 they lose their last
digits (3902903753300361600 -> 3.9029037533003617e+18 -> ...728), so every
stage reads these columns as text.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Column (or the part after "<catalog>__") that holds a 64-bit identifier.
ID_NAMES = {"catalog_object_id", "source_id", "objid", "specobjid", "bestobjid", "targetid", "ls_id",
            "parent_object_id", "object_id", "designation"}


def id_columns(columns) -> list[str]:
    return [c for c in columns if str(c).split("__")[-1].lower() in ID_NAMES]


def read_table(path, **kwargs) -> pd.DataFrame:
    """``pd.read_csv`` with identifier columns as text.  ``str`` (object), not
    pandas "string": missing values stay NaN, which the rules test as "nan"."""
    path = Path(path)
    head = pd.read_csv(path, nrows=0).columns
    dtype = {c: str for c in id_columns(head)}
    dtype.update(kwargs.pop("dtype", None) or {})
    kwargs.setdefault("low_memory", False)
    return pd.read_csv(path, dtype=dtype, **kwargs)

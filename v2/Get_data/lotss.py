"""Independent v2 catalog adapter skeleton."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

STANDARD_COLUMNS = ["catalog", "catalog_object_id", "object_name", "ra", "dec"]

@dataclass(frozen=True)
class QueryRegion:
    ra: float
    dec: float
    radius_arcmin: float

def validate_output(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in STANDARD_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing standard columns: {missing}")
    if df["catalog_object_id"].astype(str).duplicated().any():
        raise ValueError("catalog_object_id must be unique within one catalog result")
    return df


CATALOG_NAME = "LoTSS"
DESCRIPTION = "low-frequency radio measurements"

def fetch(region: QueryRegion) -> pd.DataFrame:
    """Fetch sources in region. Query logic belongs only to this adapter."""
    raise NotImplementedError("LoTSS adapter query is not implemented yet")

def save(df: pd.DataFrame, path: str | Path) -> None:
    validate_output(df).to_csv(path, index=False)

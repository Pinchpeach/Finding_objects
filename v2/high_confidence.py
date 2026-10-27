"""High-confidence objects of a search (2.36.0).

An object is flagged ``high_confidence`` when its coarse class is either

* confirmed by a good pipeline spectrum of the same class at its position:
  SDSS (ZWARNING = 0), DESI DR1 Redrock (ZWARN = 0, DELTACHI2 >= 25, not a
  backup-programme GALAXY) or LAMOST DR5 (S/N >= 10 in g or i), i.e.
  ``catalog_confidence_*_spectroscopy`` = 1 (Stage 3) with an association
  confidence >= SPEC_MIN_ASSOCIATION; or
* photometric with a confidence at or above the threshold of its class and
  magnitude bin in Classifier/high_confidence.json, where the estimated
  real-sky purity is >= 98 % (one-sided 1 sigma; v2/benchmark/
  natural_purity.py).  Faint galaxies outnumber quasars ~100:1, so no
  photometric QSO reaches it (2.36.0 measurement: 4-30 % real-sky purity);
  only a spectrum makes a quasar high-confidence.

The photometric route is withheld when a key archive (catalog_coverage.py)
failed for the search: the thresholds were measured with those data.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

TABLE = Path(__file__).resolve().parent / "Classifier" / "high_confidence.json"
SPEC_MIN_ASSOCIATION = 0.8
# (catalogue prefix, class column, confidence column, label)
SPECTRA = (
    ("sdss_dr18_spectroscopy", "class", "catalog_confidence_sdss_spectroscopy", "SDSS"),
    ("desi_dr1_spectroscopy", "OType", "catalog_confidence_desi_spectroscopy", "DESI DR1"),
    ("lamost_dr_catalog", "Class", "catalog_confidence_lamost_spectroscopy", "LAMOST DR5"),
)
CLASSES = ("STAR", "GALAXY", "QSO")


def load_table(path: Path = TABLE) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)


def magnitude(df, columns):
    r = pd.Series(np.nan, index=df.index)
    for c in columns:
        if c in df:
            r = r.fillna(_num(df, c))
    return r


def spectroscopic(df) -> pd.Series:
    """Label of the good spectrum that confirms primary_class ("" if none)."""
    out = pd.Series("", index=df.index, dtype=object)
    cls = df.get("primary_class", pd.Series("", index=df.index)).astype(str)
    for prefix, ccol, qcol, label in SPECTRA:
        col = f"{prefix}__{ccol}"
        if col not in df:
            continue
        sc = df[col].astype(str).str.strip().str.upper().replace({"QUASAR": "QSO"})
        assoc = _num(df, f"association_confidence__{prefix}").fillna(1.0)
        good = sc.eq(cls) & _num(df, qcol).ge(1.0) & assoc.ge(SPEC_MIN_ASSOCIATION) & out.eq("")
        out[good] = label
    return out


def apply(df: pd.DataFrame, coverage: dict | None = None, table: dict | None = None) -> pd.DataFrame:
    """Add ``high_confidence`` (bool) and ``high_confidence_basis`` (text)."""
    df = df.copy()
    table = table if table is not None else load_table()
    n = len(df)
    flag = np.zeros(n, bool)
    basis = np.array([""] * n, dtype=object)
    if n == 0 or "primary_class" not in df:
        df["high_confidence"], df["high_confidence_basis"] = flag, basis
        return df
    classified = df.get("classification_status", pd.Series("CLASSIFIED", index=df.index)).eq("CLASSIFIED").to_numpy()
    spec = spectroscopic(df).to_numpy()
    s = classified & (spec != "")
    flag[s] = True
    basis[s] = [f"spectrum ({x})" for x in spec[s]]
    if table and not (coverage or {}).get("key_failed"):
        edges = [-np.inf if e is None and i == 0 else np.inf if e is None else float(e) for i, e in enumerate(table["edges"])]
        mag = magnitude(df, table["magnitude_columns"])
        bins = pd.cut(mag, edges, labels=table["labels"]).astype(object).to_numpy()
        conf = _num(df, "primary_confidence").to_numpy()
        # Classes set by the 2MASS count prior (2.41.0) were not part of the
        # purity measurement behind the thresholds.
        conf = np.where(df.get("classification_basis", pd.Series("", index=df.index)).astype(str).str.startswith("2MASS"), np.nan, conf)
        cls = df.primary_class.astype(str).to_numpy()
        lower = table.get("purity_lower_bound", {})
        for b, per_class in table["thresholds"].items():
            for c, t in per_class.items():
                if t is None:
                    continue
                hit = classified & ~flag & (bins == b) & (cls == c) & (conf >= t)  # NaN confidence -> False
                if hit.any():
                    p = lower.get(b, {}).get(c)
                    flag[hit] = True
                    basis[hit] = f"photometry ({b}, p >= {t:g}" + (f", real-sky purity >= {100 * p:.1f} %)" if p else ")")
    df["high_confidence"] = flag
    df["high_confidence_basis"] = basis
    return df

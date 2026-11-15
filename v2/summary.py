"""Compact result tables for reading a search without the app (2.54.0).

``classified_objects.csv`` keeps every stage's columns (1,500-2,400 columns,
~12 MB for a 2' COSMOS search): it is the full record, not a table to read.
``write()`` adds two small tables with the columns a user reads first:

  objects_summary.csv         one row per independent object with a survey
                              detection: the parts of large galaxies (already
                              grouped under their host, ``parent_object_id``)
                              and literature-only entries are left out
  literature_only_entries.csv entries known only from the NED / SIMBAD
                              literature compilations, with no detection in
                              the collected surveys (in a 2' COSMOS search 370
                              of the 422 UNKNOWN rows were NED-only, mostly
                              deep-field redshift catalogues)

The app hides the same rows by default (galaxy parts since 2.17.0,
literature-only entries since 2.54.0); the full table stays the reference.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# NED and SIMBAD compile the literature; they are not detections of the
# collected surveys (the same set as detection_quality.py / radio_sources.py).
LITERATURE = frozenset({"NED", "SIMBAD"})
# Best available r-band (or Gaia G) magnitude, in the order of high_confidence.json.
MAGNITUDES = ("std_mag__ls_r", "std_mag__ps1_r", "std_mag__sdss_r", "gaia_dr3__phot_g_mean_mag")
COLUMNS = [
    "designation",
    "ra",
    "dec",
    "separation_arcmin",
    "mag",
    "mag_band",
    "primary_class",
    "primary_confidence",
    "p_star",
    "p_galaxy",
    "p_qso",
    "classification_status",
    "primary_provenance",
    "classification_basis",
    "high_confidence",
    "high_confidence_basis",
    "secondary_class",
    "subclass",
    "subclass_provenance",
    "subclass_tags",
    "unknown_reason",
    "n_components",
    "host_redshift",
    "designation_catalog",
    "catalogs",
    "object_id",
]
SUMMARY = "objects_summary.csv"
LITERATURE_ONLY = "literature_only_entries.csv"


def literature_only(df: pd.DataFrame) -> pd.Series:
    """Rows whose catalogues are all literature compilations (NED / SIMBAD)."""
    if "catalogs" not in df:
        return pd.Series(False, index=df.index)
    cats = df["catalogs"].fillna("").astype(str).map(lambda s: frozenset(c for c in s.split("|") if c))
    return cats.map(lambda c: bool(c) and c <= LITERATURE)


def part(df: pd.DataFrame) -> pd.Series:
    """Rows grouped under a host galaxy (host_groups.py)."""
    return df["parent_object_id"].notna() if "parent_object_id" in df else pd.Series(False, index=df.index)


def compact(df: pd.DataFrame) -> pd.DataFrame:
    """The COLUMNS of ``df`` (those present) plus the best magnitude."""
    out = df.copy()
    mag = pd.Series(float("nan"), index=df.index)
    band = pd.Series("", index=df.index, dtype=object)
    for c in MAGNITUDES:
        if c in df:
            v = pd.to_numeric(df[c], errors="coerce")
            fill = mag.isna() & v.notna()
            mag[fill] = v[fill]
            band[fill] = "G (Gaia)" if c.startswith("gaia") else "r (" + c.split("__")[1].split("_")[0].upper() + ")"
    out["mag"], out["mag_band"] = mag.round(3), band
    for c in ("primary_confidence", "p_star", "p_galaxy", "p_qso"):
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(4)
    if "separation_arcmin" in out:
        out["separation_arcmin"] = pd.to_numeric(out["separation_arcmin"], errors="coerce").round(4)
    return out[[c for c in COLUMNS if c in out]]


def write(df: pd.DataFrame, work: Path) -> dict:
    """Write both tables into ``work``; the row counts."""
    work = Path(work)
    lit = literature_only(df)
    parts = part(df)
    main = compact(df[~parts & ~lit])
    litonly = compact(df[~parts & lit])
    main.to_csv(work / SUMMARY, index=False)
    litonly.to_csv(work / LITERATURE_ONLY, index=False)
    return {"objects": len(main), "galaxy_parts": int(parts.sum()), "literature_only": len(litonly)}

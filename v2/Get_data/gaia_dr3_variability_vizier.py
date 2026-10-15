"""Lightweight Gaia DR3 variability collector for large independent validation.

Reads the official Gaia DR3 variability classification table through VizieR.
It preserves the production column names/semantics while avoiding multiple TAP
round-trips per truth object. This module is validation infrastructure, not a
different evidence source.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, empty_frame, pick, save_csv, vizier_cone

save = save_csv  # collector API: save(df, path)

CATALOG = "Gaia DR3"
TABLE = "I/358/vclassre"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(TABLE, ra, dec, radius_arcmin, ["Source", "Class", "ClassSc", "RA_ICRS", "DE_ICRS"])
    if df is None or df.empty:
        return empty_frame("best_class_name", "best_class_score")
    sid = pick(df, ["Source"])
    cl = pick(df, ["Class"])
    sc = pick(df, ["ClassSc"])
    rav, dev = coordinates(df, ["RA_ICRS", "RAJ2000", "_RAJ2000"], ["DE_ICRS", "DEJ2000", "_DEJ2000"])
    ids = df[sid].astype("string") if sid else df.index.astype(str)
    out = pd.DataFrame(
        {
            "catalog": CATALOG,
            "catalog_object_id": ids,
            "object_name": "Gaia DR3 " + ids,
            "ra": rav,
            "dec": dev,
            "best_class_name": df[cl].astype("string") if cl else pd.NA,
            "best_class_score": pd.to_numeric(df[sc], errors="coerce") if sc else pd.NA,
        }
    )
    out = add_standard_metadata(
        out, radius_arcmin=radius_arcmin, ref_epoch=2016.0, poserr_arcsec=0.1, psf_fwhm_arcsec=0.18
    )
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)

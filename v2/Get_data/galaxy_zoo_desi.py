"""Galaxy Zoo DESI (Walmsley et al. 2023, MNRAS 526, 4768; VizieR J/MNRAS/526/4768).

Deep-learning predictions of Galaxy Zoo volunteer vote fractions for 8.7 M
DESI Legacy Surveys DR8 galaxies with r < 19 (models predict the vote
fractions to within 5-10 %).  Kept columns (vote fractions, 0-1):
SFSM smooth, SFFDF featured or disc, SAYes / SANo spiral arms,
DEOYes edge-on disc, MNo / MMiD / MMaD / MM merging: none, minor
disturbance, major disturbance, merger.  The rows describe galaxies already
detected by the Legacy Surveys, so Stage 1 treats them as annotations.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, empty_frame, numeric, save_csv, vizier_cone

CATALOG = "Galaxy Zoo DESI"
VIZIER_CATALOG = "J/MNRAS/526/4768/catalog"
FRACTIONS = ("SFSM", "SFFDF", "SFAF", "SAYes", "SANo", "DEOYes", "MNo", "MMiD", "MMaD", "MM")


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None or df.empty:
        return empty_frame(*(f"gz_{c}" for c in FRACTIONS))
    ra_v, dec_v = coordinates(df, ["RAJ2000", "_RAJ2000"], ["DEJ2000", "_DEJ2000"])
    ids = df["dr8Id"].astype("string")
    out = pd.DataFrame({"catalog": CATALOG, "catalog_object_id": ids, "object_name": "GZD " + ids, "ra": ra_v, "dec": dec_v})
    for c in FRACTIONS:
        out[f"gz_{c}"] = numeric(df[c]) if c in df else pd.NA
    out = add_standard_metadata(out, radius_arcmin=radius_arcmin, poserr_arcsec=0.1)
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id").reset_index(drop=True)


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "GZD")

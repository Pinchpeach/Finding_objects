"""Independent LAMOST DR catalog cone-search collector. No cross-match/classification."""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, numeric, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "LAMOST DR catalog"
VIZIER_CATALOG = "V/164/dr5"
STELLAR_CATALOG = "V/164/stellar5"
LASP = {
    "Teff": "lasp_teff",
    "e_Teff": "lasp_teff_err",
    "logg": "lasp_logg",
    "e_logg": "lasp_logg_err",
    "[Fe/H]": "lasp_feh",
    "e_[Fe/H]": "lasp_feh_err",
}


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    if "ObsID" not in df:
        raise KeyError("identifier column missing: " + "ObsID")
    ident = df["ObsID"].astype("string")
    df = with_base(df, CATALOG, ident, ident, numeric(df["RAJ2000"]), numeric(df["DEJ2000"]))
    # LASP Teff / log g / [Fe/H] of A, F, G, K stars (V/164/stellar5; Luo et al.
    # 2015).  A failed query leaves them empty and keeps the spectra.
    df["lasp_query_status"] = "ok"  # a failure is recorded so the archive cache does not keep a partial result
    try:
        p = vizier_cone(STELLAR_CATALOG, ra, dec, radius_arcmin, ["ObsID", *LASP])
        if p is not None:
            p = p.rename(columns=LASP)
            p["catalog_object_id"] = p.pop("ObsID").astype("string")
            df = df.merge(
                p.drop_duplicates("catalog_object_id")[["catalog_object_id", *[c for c in LASP.values() if c in p]]],
                on="catalog_object_id",
                how="left",
            )
    except Exception as exc:
        print(f"[lamost_spectroscopy] LASP parameter query failed: {type(exc).__name__}: {str(exc)[:120]}")
        df["lasp_query_status"] = "error:" + type(exc).__name__
    for c in LASP.values():
        if c not in df:
            df[c] = pd.NA
    return df

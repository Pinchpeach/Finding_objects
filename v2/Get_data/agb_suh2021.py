"""Suh (2021) Galactic AGB catalog collector via CDS VizieR.

Tables 9-12 contain O-rich/C-rich AGB samples based on IRAS/WISE positions.
The output carries the positional basis, epoch, and conservative uncertainty so
Stage-1 can use a survey-aware association model rather than a universal radius.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import BASE, add_standard_metadata, coordinates, empty_frame, pick, save_csv, vizier_query

CATALOG = "Suh 2021 AGB Catalog"
TABLES = {
    "J/ApJS/256/43/table9": "OAGB_IRAS",
    "J/ApJS/256/43/table10": "CAGB_IRAS",
    "J/ApJS/256/43/table11": "OAGB_WISE",
    "J/ApJS/256/43/table12": "CAGB_WISE",
}
# Position metadata per basis: epoch, conservative 1-sigma error and PSF FWHM.
META = {
    "IRAS": dict(ref_epoch=1983.5, poserr_arcsec=12.0, psf_fwhm_arcsec=30.0),
    "WISE": dict(ref_epoch=2010.5, poserr_arcsec=1.0, psf_fwhm_arcsec=6.1),
}


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    frames = []
    failed = []
    for table_id, subtype in TABLES.items():
        # A failed table is recorded, not skipped silently: its rows would be
        # missing from a result that the archive cache keeps for 90 days.
        try:
            tabs = vizier_query(table_id, ra, dec, radius_arcmin)
        except Exception as exc:
            failed.append(f"{table_id.rsplit('/',1)[-1]}:{type(exc).__name__}")
            continue
        df = tabs[0].to_pandas() if tabs else None
        if df is None or df.empty:
            continue
        idc = pick(df, ["WISEA", "IRAS", "OI-N", "CI-N", "OW-N", "CW-N", "recStar"])
        try:
            raval, decval = coordinates(
                df, ["RAdeg", "RAJ2000", "RA_ICRS", "_RAJ2000"], ["DEdeg", "DEJ2000", "DE_ICRS", "_DEJ2000"]
            )
        except Exception as exc:
            failed.append(f"{table_id.rsplit('/',1)[-1]}:{type(exc).__name__}")
            continue
        out = df.copy()
        out["ra"] = raval
        out["dec"] = decval
        out["agb_subclass"] = subtype
        basis = "IRAS" if "IRAS" in subtype else "WISE"
        out["position_basis"] = basis
        ids = out[idc].astype("string") if idc else pd.Series(range(len(out)), index=out.index).astype("string")
        out.insert(0, "catalog", CATALOG)
        out.insert(1, "catalog_object_id", subtype + ":" + ids.fillna(""))
        out.insert(2, "object_name", out["catalog_object_id"])
        out = add_standard_metadata(out, radius_arcmin=radius_arcmin, **META[basis])
        frames.append(out)
    if failed and not frames:
        # Nothing to return and at least one table unknown: an error, not "empty".
        raise RuntimeError("Suh 2021 AGB tables failed: " + ", ".join(failed))
    if not frames:
        return empty_frame("agb_subclass", "position_basis")
    out = (
        pd.concat(frames, ignore_index=True, sort=False)
        .dropna(subset=["ra", "dec"])
        .drop_duplicates("catalog_object_id", keep="last")
        .reset_index(drop=True)
    )
    out["agb_query_status"] = "error:" + ",".join(failed) if failed else "ok"  # partial results are not cached (2.23.0)
    return out


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "Suh AGB", [*BASE, "agb_subclass"])

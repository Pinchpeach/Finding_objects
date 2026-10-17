"""HASH planetary-nebula catalogue collector via CDS VizieR."""

from __future__ import annotations
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, empty_frame, pick, save_csv, vizier_cone

CATALOG = "HASH PN Catalog"
VIZIER_CATALOG = "V/163/pnmain"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None or df.empty:
        return empty_frame()
    idc = pick(df, ["HASH", "PNG", "Name"])
    namec = pick(df, ["Name", "PNG", "HASH"])
    statusc = pick(df, ["Status", "stat", "PNstat"])
    if idc is None:
        raise KeyError(f"HASH PN required identifier missing; got {list(df.columns)}")
    raval, decval = coordinates(
        df, ["RAJ2000", "RA_ICRS", "RAdeg", "_RAJ2000"], ["DEJ2000", "DE_ICRS", "DEdeg", "_DEJ2000"]
    )
    out = df.copy()
    out["ra"] = raval
    out["dec"] = decval
    out["pn_catalog_status"] = out[statusc].astype("string") if statusc else pd.NA
    out.insert(0, "catalog", CATALOG)
    out.insert(1, "catalog_object_id", out[idc].astype("string"))
    out.insert(2, "object_name", out[namec].astype("string") if namec else out[idc].astype("string"))
    out = add_standard_metadata(out, radius_arcmin=radius_arcmin, ref_epoch=2000.0, poserr_arcsec=1.0)
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "HASH PN")

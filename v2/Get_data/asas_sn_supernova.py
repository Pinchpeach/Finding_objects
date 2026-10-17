"""ASAS-SN bright-supernova catalogue collector via CDS VizieR.

Neumann et al. (2023), J/MNRAS/520/4356, covers bright SNe from 2018-2020.
Rows are represented as transient events, not persistent host-galaxy sources.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, empty_frame, pick, save_csv, vizier_query

CATALOG = "ASAS-SN Supernova Catalog"
TABLES = ("J/MNRAS/520/4356/table1", "J/MNRAS/520/4356/table2")


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    frames = []
    failed = []
    for table in TABLES:
        try:
            tabs = vizier_query(table, ra, dec, radius_arcmin)
        except Exception as exc:
            failed.append(f"{table}:{type(exc).__name__}")  # recorded, not silently dropped (2.23.0)
            continue
        df = tabs[0].to_pandas() if tabs else None
        if df is None or df.empty:
            continue
        idc = pick(df, ["IAUName", "SNName", "Name", "ASASSN"])
        typec = pick(df, ["SpType", "Type", "SNType"])
        datec = pick(df, ["DiscDate", "DiscoveryDate", "Date", "MJD"])
        if idc is None:
            continue
        try:
            raval, decval = coordinates(
                df, ["RAJ2000", "RA_ICRS", "RAdeg", "_RAJ2000", "RA"], ["DEJ2000", "DE_ICRS", "DEdeg", "_DEJ2000", "DE"]
            )
        except Exception:
            continue
        out = df.copy()
        out["ra"] = raval
        out["dec"] = decval
        out["sn_subtype"] = out[typec].astype("string") if typec else pd.NA
        out["event_time_raw"] = out[datec].astype("string") if datec else pd.NA
        if datec and datec.upper() == "MJD":
            out["event_mjd"] = pd.to_numeric(out[datec], errors="coerce")
        elif datec:
            parsed = pd.to_datetime(out[datec], errors="coerce", utc=True)
            out["event_mjd"] = parsed.map(lambda x: (x.timestamp() / 86400.0 + 40587.0) if pd.notna(x) else pd.NA)
        else:
            out["event_mjd"] = pd.NA
        out["sn_catalog_table"] = table
        out.insert(0, "catalog", CATALOG)
        out.insert(1, "catalog_object_id", out[idc].astype("string"))
        out.insert(2, "object_name", out[idc].astype("string"))
        out = add_standard_metadata(
            out, radius_arcmin=radius_arcmin, ref_epoch=2000.0, poserr_arcsec=1.0, entity_kind="transient_event"
        )
        frames.append(out)
    if failed and not frames:
        raise RuntimeError("ASAS-SN tables failed: " + ", ".join(failed))
    if not frames:
        return empty_frame("sn_subtype", "event_mjd", "entity_kind")
    out = (
        pd.concat(frames, ignore_index=True, sort=False)
        .dropna(subset=["ra", "dec"])
        .drop_duplicates("catalog_object_id", keep="last")
        .reset_index(drop=True)
    )
    out["sn_query_status"] = "error:" + ",".join(failed) if failed else "ok"
    return out


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "ASAS-SN")

"""HASH planetary-nebula catalogue collector via CDS VizieR."""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick, coordinates, add_standard_metadata

CATALOG = "HASH PN Catalog"
VIZIER_CATALOG = "V/163/pnmain"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    result = Vizier(columns=["**"], row_limit=-1).query_region(
        SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs"),
        radius=float(radius_arcmin) * u.arcmin,
        catalog=VIZIER_CATALOG,
    )
    if not result:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df = result[0].to_pandas()
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
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


def save(df: pd.DataFrame, path: str | Path) -> None:
    required = {"catalog", "catalog_object_id", "object_name", "ra", "dec"}
    if not required.issubset(df.columns):
        raise ValueError("invalid HASH PN output")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

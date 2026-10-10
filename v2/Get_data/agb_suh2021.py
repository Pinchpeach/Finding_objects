"""Suh (2021) Galactic AGB catalog collector via CDS VizieR.

Tables 9-12 contain O-rich/C-rich AGB samples based on IRAS/WISE positions.
The output carries the positional basis, epoch, and conservative uncertainty so
Stage-1 can use a survey-aware association model rather than a universal radius.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick, coordinates, add_standard_metadata

CATALOG = "Suh 2021 AGB Catalog"
TABLES = {
    "J/ApJS/256/43/table9": "OAGB_IRAS",
    "J/ApJS/256/43/table10": "CAGB_IRAS",
    "J/ApJS/256/43/table11": "OAGB_WISE",
    "J/ApJS/256/43/table12": "CAGB_WISE",
}


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    coord = SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs")
    frames = []
    for table_id, subtype in TABLES.items():
        try:
            result = Vizier(columns=["**"], row_limit=-1).query_region(
                coord, radius=float(radius_arcmin) * u.arcmin, catalog=table_id
            )
        except Exception:
            continue
        if not result:
            continue
        df = result[0].to_pandas()
        if df.empty:
            continue
        idc = pick(df, ["WISEA", "IRAS", "OI-N", "CI-N", "OW-N", "CW-N", "recStar"])
        try:
            raval, decval = coordinates(
                df, ["RAdeg", "RAJ2000", "RA_ICRS", "_RAJ2000"], ["DEdeg", "DEJ2000", "DE_ICRS", "_DEJ2000"]
            )
        except Exception:
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
        if basis == "IRAS":
            out = add_standard_metadata(
                out, radius_arcmin=radius_arcmin, ref_epoch=1983.5, poserr_arcsec=12.0, psf_fwhm_arcsec=30.0
            )
        else:
            out = add_standard_metadata(
                out, radius_arcmin=radius_arcmin, ref_epoch=2010.5, poserr_arcsec=1.0, psf_fwhm_arcsec=6.1
            )
        frames.append(out)
    if not frames:
        return pd.DataFrame(
            columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", "agb_subclass", "position_basis"]
        )
    return (
        pd.concat(frames, ignore_index=True, sort=False)
        .dropna(subset=["ra", "dec"])
        .drop_duplicates("catalog_object_id", keep="last")
        .reset_index(drop=True)
    )


def save(df: pd.DataFrame, path: str | Path) -> None:
    required = {"catalog", "catalog_object_id", "object_name", "ra", "dec", "agb_subclass"}
    if not required.issubset(df.columns):
        raise ValueError("invalid Suh AGB output")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

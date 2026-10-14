"""Lightweight Gaia DR3 FLAME collector for large independent validation.

Reads Gaia DR3 astrophysical_parameters through VizieR in a single cone query.
The fields and catalogue identity match production Gaia evidence; only the
transport path is optimized for validation throughput.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick, coordinates, add_standard_metadata

CATALOG = "Gaia DR3"
TABLE = "I/355/paramp"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    cols = [
        "Source",
        "RA_ICRS",
        "DE_ICRS",
        "Pstar",
        "PWD",
        "Pbin",
        "Teff",
        "logg",
        "[M/H]",
        "Mass-Flame",
        "Age-Flame",
        "Evol",
    ]
    tabs = Vizier(columns=cols, row_limit=-1).query_region(
        SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs"),
        radius=float(radius_arcmin) * u.arcmin,
        catalog=TABLE,
    )
    if not tabs:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df = tabs[0].to_pandas()
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    sid = pick(df, ["Source"])
    rav, dev = coordinates(df, ["RA_ICRS", "RAJ2000"], ["DE_ICRS", "DEJ2000"])

    def val(names, numeric=True):
        c = pick(df, names)
        if c is None:
            return pd.Series(pd.NA, index=df.index)
        return pd.to_numeric(df[c], errors="coerce") if numeric else df[c]

    ids = df[sid].astype("string") if sid else df.index.astype(str)
    out = pd.DataFrame(
        {
            "catalog": CATALOG,
            "catalog_object_id": ids,
            "object_name": "Gaia DR3 " + ids,
            "ra": rav,
            "dec": dev,
            "classprob_dsc_combmod_star": val(["Pstar"]),
            "classprob_dsc_combmod_whitedwarf": val(["PWD"]),
            "classprob_dsc_combmod_binarystar": val(["Pbin"]),
            "teff_gspphot": val(["Teff"]),
            "logg_gspphot": val(["logg", "logg-GSP-Phot"]),
            "mh_gspphot": val(["[M/H]", "[Fe/H]"]),
            "mass_flame": val(["Mass-Flame"]),
            "age_flame": val(["Age-Flame"]),
            "evolstage_flame": val(["Evol"]),
        }
    )
    out = add_standard_metadata(
        out, radius_arcmin=radius_arcmin, ref_epoch=2016.0, poserr_arcsec=0.1, psf_fwhm_arcsec=0.18
    )
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

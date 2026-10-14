"""ZTF periodic variable stars (Chen et al. 2020, ApJS 249, 18; VizieR
J/ApJS/249/18/table2) cone-search collector (2.8.0).  No classification here.

781,602 periodic variables from ZTF DR2 g/r light curves (Dec > -28, about
11-20 mag; brighter stars saturate), each with a period (Lomb-Scargle),
g/r amplitudes, Fourier parameters R21 / phi21 and a type from period,
amplitude and light-curve shape: EW, EA, BYDra, RSCVN, SR, Mira, RR, RRc,
DSCT, CEP, CEPII.  Classifier/axes/variability.py maps the type.
"""

from pathlib import Path
import pandas as pd

CATALOG = "ZTF periodic variables"
VIZIER_CATALOG = "J/ApJS/249/18/table2"
COLUMNS = ["ID", "RAJ2000", "DEJ2000", "Type", "Per", "gAmp", "rAmp", "R21", "phi21", "gmag", "rmag", "Ng", "Nr"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    tables = Vizier(columns=COLUMNS, row_limit=-1).query_region(
        SkyCoord(ra * u.deg, dec * u.deg, frame="icrs"), radius=radius_arcmin * u.arcmin, catalog=VIZIER_CATALOG
    )
    if not tables:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df = tables[0].to_pandas()
    if "ID" not in df.columns:
        raise KeyError("catalog identifier column missing")
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["ID"].astype("string").str.strip())
    df.insert(2, "object_name", df["catalog_object_id"])
    df.insert(3, "ra", pd.to_numeric(df["RAJ2000"], errors="coerce"))
    df.insert(4, "dec", pd.to_numeric(df["DEJ2000"], errors="coerce"))
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

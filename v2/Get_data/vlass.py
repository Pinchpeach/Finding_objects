"""Independent VLASS cone-search collector. No cross-match/classification."""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import pick, coordinates

CATALOG = "VLASS"
VIZIER_CATALOG = "J/ApJS/255/30"
ID_COLUMNS = ["CompName", "Component_name", "Name", "VLASS", "CompId", "Component_id"]
RA_COLUMNS = ["RAJ2000", "RA_ICRS", "_RAJ2000", "RAdeg"]
DEC_COLUMNS = ["DEJ2000", "DE_ICRS", "_DEJ2000", "DEdeg"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    tabs = Vizier(columns=["**"], row_limit=-1).query_region(
        SkyCoord(ra * u.deg, dec * u.deg), radius=radius_arcmin * u.arcmin, catalog=VIZIER_CATALOG
    )
    if not tabs:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    # J/ApJS/255/30 (Gordon et al. 2021) has several tables; use the one with
    # positions.  Its component name column is not "Name" in every VizieR
    # release (2.26.0: every VLASS match failed with "identifier column
    # missing: Name"), so the identifier is picked from known names and
    # otherwise built from the position.
    df = next((t.to_pandas() for t in tabs if pick(t.to_pandas(), RA_COLUMNS) is not None), tabs[0].to_pandas())
    rv, dv = coordinates(df, RA_COLUMNS, DEC_COLUMNS)
    idc = pick(df, ID_COLUMNS)
    if idc is not None:
        ident = df[idc].astype("string").str.strip()
    else:
        ident = pd.Series([f"J{r:.5f}{d:+.5f}" for r, d in zip(rv, dv)], index=df.index, dtype="string")
    df["_vlass_id"] = ident
    idc = "_vlass_id"
    df["_ra"], df["_dec"] = rv, dv
    rac, dcc = "_ra", "_dec"
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df[idc].astype("string"))
    df.insert(2, "object_name", CATALOG + " " + df["catalog_object_id"].astype("string"))
    df.insert(3, "ra", pd.to_numeric(df[rac], errors="coerce"))
    df.insert(4, "dec", pd.to_numeric(df[dcc], errors="coerce"))
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

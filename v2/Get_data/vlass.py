"""Independent VLASS cone-search collector. No cross-match/classification."""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import coordinates, empty_frame, numeric, pick, save_csv, vizier_query, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "VLASS"
VIZIER_CATALOG = "J/ApJS/255/30"
ID_COLUMNS = ["CompName", "Component_name", "Name", "VLASS", "CompId", "Component_id"]
RA_COLUMNS = ["RAJ2000", "RA_ICRS", "_RAJ2000", "RAdeg"]
DEC_COLUMNS = ["DEJ2000", "DE_ICRS", "_DEJ2000", "DEdeg"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    tabs = vizier_query(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if not tabs:
        return empty_frame()
    # J/ApJS/255/30 (Gordon et al. 2021) has several tables; use the one with
    # positions.  Its component name column is not "Name" in every VizieR
    # release (2.26.0: every VLASS match failed with "identifier column
    # missing: Name"), so the identifier is picked from known names and
    # otherwise built from the position.
    frames = [t.to_pandas() for t in tabs]
    df = next((f for f in frames if pick(f, RA_COLUMNS) is not None), frames[0])
    rv, dv = coordinates(df, RA_COLUMNS, DEC_COLUMNS)
    idc = pick(df, ID_COLUMNS)
    if idc is not None:
        ident = df[idc].astype("string").str.strip()
    else:
        ident = pd.Series([f"J{r:.5f}{d:+.5f}" for r, d in zip(rv, dv)], index=df.index, dtype="string")
    df["_vlass_id"] = ident
    df["_ra"], df["_dec"] = rv, dv
    ident = df["_vlass_id"].astype("string")
    return with_base(df, CATALOG, ident, CATALOG + " " + ident, numeric(df["_ra"]), numeric(df["_dec"]))

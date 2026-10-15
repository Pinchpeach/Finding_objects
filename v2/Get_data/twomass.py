"""Independent 2MASS PSC cone-search collector via VizieR."""

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, numeric, pick, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "2MASS PSC"
VIZIER_CATALOG = "II/246/out"


def fetch(ra, dec, radius_arcmin):
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    idc = pick(df, ["_2MASS", "2MASS", "2MASS_name"])
    rac = pick(df, ["RAJ2000", "RA_ICRS"])
    dcc = pick(df, ["DEJ2000", "DE_ICRS"])
    if not all([idc, rac, dcc]):
        raise KeyError(f"2MASS required columns missing; got {list(df.columns)}")
    ident = df[idc].astype("string")
    return with_base(df, CATALOG, ident, CATALOG + " " + ident, numeric(df[rac]), numeric(df[dcc]))

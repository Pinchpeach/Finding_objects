"""Independent LoTSS DR2 cone-search collector via VizieR. No cross-match/classification."""

import pandas as pd
from _catalog_utils import empty_frame, numeric, pick, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "LoTSS DR2"
VIZIER_CATALOG = "J/A+A/659/A1"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    # The live VizieR table names the identifier "Source" (2.20.0; the old exact
    # "Source_Name" made every query with rows raise, so LoTSS never contributed).
    idc = pick(df, ["Source", "Source_Name", "LoTSS"])
    if idc is None:
        raise KeyError(f"catalog identifier column missing; got {list(df.columns)[:25]}")
    ident = df[idc].astype("string")
    return with_base(df, CATALOG, ident, CATALOG + " " + ident, numeric(df["RAJ2000"]), numeric(df["DEJ2000"]))

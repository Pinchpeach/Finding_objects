"""Independent FIRST cone-search collector via VizieR. No cross-match/classification."""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, j2000_degrees as _degrees, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "FIRST"
VIZIER_CATALOG = "VIII/92/first14"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin, ["**", "_RAJ2000", "_DEJ2000"])
    if df is None:
        return empty_frame()
    if "FIRST" not in df.columns:
        raise KeyError("catalog identifier column missing")
    ident = df["FIRST"].astype("string")
    return with_base(df, CATALOG, ident, CATALOG + " " + ident, *_degrees(df))

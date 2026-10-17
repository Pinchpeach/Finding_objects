"""Independent TGSS ADR1 (GMRT 150 MHz; Intema et al. 2017, A&A 598, A78) cone-search
collector via VizieR.  No cross-match/classification.

150 MHz with NVSS 1.4 GHz gives the radio spectral index used by the pulsar
rule (Frail et al. 2018: alpha <= -1.5 and compactness S_total / S_peak <= 1.5).
"""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, numeric, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "TGSS ADR1"
VIZIER_CATALOG = "J/A+A/598/A78/table3"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    if "TGSSADR" not in df.columns:
        raise KeyError("catalog identifier column missing")
    ident = df["TGSSADR"].astype("string")
    return with_base(df, CATALOG, ident, "TGSS " + ident, numeric(df["RAJ2000"]), numeric(df["DEJ2000"]))

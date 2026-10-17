"""ZTF periodic variable stars (Chen et al. 2020, ApJS 249, 18; VizieR
J/ApJS/249/18/table2) cone-search collector (2.8.0).  No classification here.

781,602 periodic variables from ZTF DR2 g/r light curves (Dec > -28, about
11-20 mag; brighter stars saturate), each with a period (Lomb-Scargle),
g/r amplitudes, Fourier parameters R21 / phi21 and a type from period,
amplitude and light-curve shape: EW, EA, BYDra, RSCVN, SR, Mira, RR, RRc,
DSCT, CEP, CEPII.  Classifier/axes/variability.py maps the type.
"""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, numeric, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "ZTF periodic variables"
VIZIER_CATALOG = "J/ApJS/249/18/table2"
COLUMNS = ["ID", "RAJ2000", "DEJ2000", "Type", "Per", "gAmp", "rAmp", "R21", "phi21", "gmag", "rmag", "Ng", "Nr"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin, COLUMNS)
    if df is None:
        return empty_frame()
    if "ID" not in df.columns:
        raise KeyError("catalog identifier column missing")
    ident = df["ID"].astype("string").str.strip()
    return with_base(df, CATALOG, ident, ident, numeric(df["RAJ2000"]), numeric(df["DEJ2000"]))

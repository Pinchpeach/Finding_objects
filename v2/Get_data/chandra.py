"""Independent Chandra CSC 2.0 cone-search collector. No cross-match/classification.

VizieR column names are matched case-insensitively from candidate lists
(2.19.1): the live tables name the identifier "2CXO" (not "name"), and the old exact
names made every query raise, so this catalogue never reached a result.
"""

import pandas as pd
from _catalog_utils import id_cone, save_csv

save = save_csv  # collector API: save(df, path)

CATALOG = "Chandra CSC 2.0"
VIZIER_CATALOG = "IX/57/csc2master"
ID_COLUMNS = ["2CXO", "name", "Name"]
RA_COLUMNS = ["RAICRS", "RA_ICRS", "RAJ2000", "_RAJ2000"]
DEC_COLUMNS = ["DEICRS", "DE_ICRS", "DEJ2000", "_DEJ2000"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    return id_cone(CATALOG, VIZIER_CATALOG, ID_COLUMNS, RA_COLUMNS, DEC_COLUMNS, ra, dec, radius_arcmin)

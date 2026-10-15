"""Independent eROSITA eRASS1 cone-search collector. No cross-match/classification.

VizieR column names are matched case-insensitively from candidate lists
(2.19.1): the live tables name the identifier "IAUName" (not "IAUNAME"), and the old exact
names made every query raise, so this catalogue never reached a result.
"""

import pandas as pd
from _catalog_utils import id_cone, save_csv

save = save_csv  # collector API: save(df, path)

CATALOG = "eROSITA eRASS1"
VIZIER_CATALOG = "J/A+A/682/A34"
ID_COLUMNS = ["IAUName", "IAUNAME", "DetUId"]
RA_COLUMNS = ["RA_ICRS", "RAJ2000", "_RAJ2000"]
DEC_COLUMNS = ["DE_ICRS", "DEJ2000", "_DEJ2000"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    return id_cone(CATALOG, VIZIER_CATALOG, ID_COLUMNS, RA_COLUMNS, DEC_COLUMNS, ra, dec, radius_arcmin)

"""DESI DR1 redshift catalog cone-search collector (DESI Collaboration 2025; VizieR V/161).

No cross-match/classification.  ``OType`` is Redrock's SPECTYPE.
"""

import sys
from pathlib import Path
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _catalog_utils import empty_frame, numeric, save_csv, unique_positions, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "DESI DR1 spectroscopy"
VIZIER_CATALOG = "V/161/zcatdr1"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    if "TargetID" not in df.columns:
        raise KeyError("identifier column missing: " + "TargetID")
    if "ZCAT_PRIM" in df.columns:
        df = df[pd.to_numeric(df["ZCAT_PRIM"], errors="coerce").eq(1)]
    # OBJTYPE: keep science targets; SKY/BAD fibres sample blank sky, not objects.
    if "Type" in df.columns:
        df = df[df["Type"].astype(str).str.strip().eq("TGT")]
    df = df.copy()
    ident = df["TargetID"].astype("string")
    df = with_base(df, CATALOG, ident, CATALOG + " " + ident, numeric(df["RAICRS"]), numeric(df["DEICRS"]))
    # One sky object can carry several TARGETIDs (different programs); keep the
    # most confident spectrum within 0.5" so one object stays one row.  A
    # rounded 0.5" grid key kept both of a pair straddling a cell edge, and
    # the second spectrum then displaced the first from its LS target in
    # association (field RA 20, 2.28.0).
    df = unique_positions(df, 0.5, df["delChi2"] if "delChi2" in df.columns else None)
    return df.reset_index(drop=True)

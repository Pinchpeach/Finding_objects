"""Independent DESI Legacy Surveys DR10 cone-search collector.

Uses the NOIRLab Astro Data Lab TAP service and the combined ls_dr10.tractor
catalog (DR10 South + DR9 North).  No classification/truth labels are queried.
"""
from pathlib import Path
import pandas as pd

CATALOG = "DESI Legacy Surveys DR10"
TAP_URL = "https://datalab.noirlab.edu/tap"
TABLE = "ls_dr10.tractor"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    import pyvo
    radius_deg = float(radius_arcmin) / 60.0
    # Keep the feature set compact and purely photometric/morphological.  In
    # particular, do not join spectroscopy or any truth/classification table.
    query = f"""
        SELECT ls_id, ra, dec, type, release, brickid, objid,
               flux_g, flux_r, flux_i, flux_z,
               flux_ivar_g, flux_ivar_r, flux_ivar_i, flux_ivar_z,
               mw_transmission_g, mw_transmission_r,
               mw_transmission_i, mw_transmission_z,
               nobs_g, nobs_r, nobs_i, nobs_z, maskbits
        FROM {TABLE}
        WHERE 't' = Q3C_RADIAL_QUERY(
            ra, dec, {float(ra):.10f}, {float(dec):.10f}, {radius_deg:.10f}
        )
    """
    result = pyvo.dal.TAPService(TAP_URL).search(query)
    df = result.to_table().to_pandas()
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df.columns = [str(c).strip() for c in df.columns]
    if "ls_id" not in df.columns or "ra" not in df.columns or "dec" not in df.columns:
        raise KeyError("DESI Legacy TAP result missing ls_id/ra/dec")
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["ls_id"].astype("string"))
    df.insert(2, "object_name", "LS DR10 " + df["catalog_object_id"].astype("string"))
    df["ra"] = pd.to_numeric(df["ra"], errors="coerce")
    df["dec"] = pd.to_numeric(df["dec"], errors="coerce")
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

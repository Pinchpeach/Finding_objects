"""Independent DESI Legacy Surveys DR10 cone-search collector.

Uses the NOIRLab Astro Data Lab TAP service and the combined ls_dr10.tractor
catalog (DR10 South + DR9 North).  No classification/truth labels are queried.
"""
from pathlib import Path
import pandas as pd

CATALOG = "DESI Legacy Surveys DR10"
TAP_URL = "https://datalab.noirlab.edu/tap"
TABLE = "ls_dr10.tractor"


# The Data Lab TAP service intermittently stalls for minutes and then
# errors; short bounded attempts recover far more often than one long wait.
ATTEMPT_BUDGET_S = 80.0
ATTEMPTS = 3


def _query_with_retries(run):
    import threading, time
    last = None
    for attempt in range(ATTEMPTS):
        box = {}
        def target():
            try:
                box["value"] = run()
            except BaseException as exc:  # reported below
                box["error"] = exc
        t = threading.Thread(target=target, daemon=True)
        t.start(); t.join(ATTEMPT_BUDGET_S)
        if "value" in box:
            return box["value"]
        last = box.get("error") or TimeoutError(f"Data Lab TAP exceeded {ATTEMPT_BUDGET_S:.0f} s")
        if attempt + 1 < ATTEMPTS:
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"Legacy Surveys TAP failed after {ATTEMPTS} attempts: {last!r}")


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    import pyvo
    radius_deg = float(radius_arcmin) / 60.0
    # Keep the feature set compact and purely photometric/morphological.  In
    # particular, do not join spectroscopy or any truth/classification table.
    # W1/W2 are unWISE forced photometry at the optical positions (Dey+2019),
    # far deeper than AllWISE; quasars' mid-IR excess separates them from
    # stars where astrometry is unavailable (Chaussidon+2023).  The Tractor
    # Sersic index and half-light radius give the galaxy light profile.
    query = f"""
        SELECT ls_id, ra, dec, type, release, brickid, objid,
               flux_g, flux_r, flux_i, flux_z,
               flux_ivar_g, flux_ivar_r, flux_ivar_i, flux_ivar_z,
               mw_transmission_g, mw_transmission_r,
               mw_transmission_i, mw_transmission_z,
               nobs_g, nobs_r, nobs_i, nobs_z, maskbits,
               flux_w1, flux_w2, flux_ivar_w1, flux_ivar_w2,
               mw_transmission_w1, mw_transmission_w2,
               sersic, shape_r
        FROM {TABLE}
        WHERE 't' = Q3C_RADIAL_QUERY(
            ra, dec, {float(ra):.10f}, {float(dec):.10f}, {radius_deg:.10f}
        )
    """
    df = _query_with_retries(lambda: pyvo.dal.TAPService(TAP_URL).search(query).to_table().to_pandas())
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

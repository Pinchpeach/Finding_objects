"""ATNF Pulsar Catalog collector via NASA HEASARC TAP.

The HEASARC ATNFPULSAR table is updated from the ATNF public catalogue. This
collector performs only cone retrieval; counterpart association remains in
v2/Preprocess.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

CATALOG = "ATNF Pulsar Catalog"


def _pick(df: pd.DataFrame, names):
    low = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return None


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.heasarc import Heasarc
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    pos = SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs")
    table = Heasarc.query_region(
        pos,
        catalog="atnfpulsar",
        radius=float(radius_arcmin) * u.arcmin,
        columns="*",
        maxrec=10000,
    )
    df = table.to_pandas() if hasattr(table, "to_pandas") else pd.DataFrame(table)
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])

    name_col = _pick(df, ["name", "psrj", "alt_name"])
    ra_col = _pick(df, ["ra", "raj2000"])
    dec_col = _pick(df, ["dec", "dej2000"])
    if not all([name_col, ra_col, dec_col]):
        raise KeyError(f"ATNF required columns missing; got {list(df.columns)}")

    out = df.copy()
    out["ra"] = pd.to_numeric(out[ra_col], errors="coerce")
    out["dec"] = pd.to_numeric(out[dec_col], errors="coerce")
    out.insert(0, "catalog", CATALOG)
    out.insert(1, "catalog_object_id", out[name_col].astype("string"))
    out.insert(2, "object_name", out[name_col].astype("string"))
    out = out.dropna(subset=["ra", "dec"])
    return out.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    required = {"catalog", "catalog_object_id", "object_name", "ra", "dec"}
    if not required.issubset(df.columns):
        raise ValueError("invalid ATNF output")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

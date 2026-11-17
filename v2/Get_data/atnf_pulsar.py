"""ATNF Pulsar Catalog collector via NASA HEASARC TAP.

The HEASARC ATNFPULSAR table is updated from the ATNF public catalogue. This
collector performs only cone retrieval; counterpart association remains in
v2/Preprocess.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

import sys

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import throttle  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

CATALOG = "ATNF Pulsar Catalog"


def _pick(df: pd.DataFrame, names):
    low = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return None


# HEASARC first, then the VizieR copy of the same catalogue (2.55.0).  In the
# 2.54.0 re-evaluation the HEASARC TAP failed every search after 66-146 s, and
# on 2026-11-17 it answered "System overloaded" after 66 s (archive health);
# a re-run waited for it again.  Healthy HEASARC answers a cone in 5-7 s, so it gets
# HEASARC_BUDGET_S; then VizieR B/psr (ATNF Pulsar Catalogue, Manchester et
# al. 2005, AJ 129, 1993, kept current by CDS) gives the same pulsar names and
# positions, which is all the pipeline uses (axes/compact.py: catalogue match).
HEASARC_BUDGET_S = 30.0
VIZIER_FALLBACK = "B/psr/psr"


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    import threading

    box = {}

    def heasarc():
        try:
            box["df"] = _fetch_heasarc(ra, dec, radius_arcmin)
        except BaseException as exc:
            box["error"] = exc

    t = threading.Thread(target=heasarc, daemon=True)
    t.start()
    t.join(HEASARC_BUDGET_S)
    if "df" in box:
        return box["df"]
    why = repr(box["error"])[:160] if "error" in box else f"no answer in {HEASARC_BUDGET_S:.0f} s"
    print(f"[atnf_pulsar] HEASARC failed ({why}); VizieR {VIZIER_FALLBACK} instead", flush=True)
    return _fetch_vizier(ra, dec, radius_arcmin)


def _fetch_vizier(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from _catalog_utils import coordinates, vizier_cone

    v = vizier_cone(VIZIER_FALLBACK, ra, dec, radius_arcmin, ["**", "_RAJ2000", "_DEJ2000"])
    if v is None or v.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", "atnf_query_status"])
    name_col = _pick(v, ["PSRJ", "JName", "PSRB", "Name"])
    if name_col is None:
        raise KeyError(f"ATNF (VizieR) name column missing; got {list(v.columns)[:20]}")
    r, d = coordinates(v, ["_RAJ2000", "RAJ2000", "RAdeg"], ["_DEJ2000", "DEJ2000", "DEdeg"])
    out = v.copy()
    out.insert(0, "catalog", CATALOG)
    names = out[name_col].astype("string").str.strip()
    out.insert(1, "catalog_object_id", names)
    out.insert(2, "object_name", names)
    out.insert(3, "ra", pd.to_numeric(pd.Series(r, index=out.index), errors="coerce"))
    out.insert(4, "dec", pd.to_numeric(pd.Series(d, index=out.index), errors="coerce"))
    out["atnf_query_status"] = "vizier_fallback"  # cached one day (archive_cache.FALLBACK_STATUS)
    out = out.dropna(subset=["ra", "dec"])
    return out.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def _fetch_heasarc(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
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

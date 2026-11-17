"""Pan-STARRS1 DR2 independent photometry collector. No cross-match/classification."""

from io import StringIO
from pathlib import Path
import pandas as pd, requests

import sys

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import throttle  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

MIN_DETECTIONS = 2
CATALOG = "Pan-STARRS1 DR2 MeanObject"
API = "https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/mean.csv"
COLUMNS = [
    "objID",
    "objName",
    "raMean",
    "decMean",
    "raMeanErr",
    "decMeanErr",
    "nDetections",
    "ng",
    "nr",
    "ni",
    "nz",
    "ny",
    "gMeanPSFMag",
    "gMeanPSFMagErr",
    "rMeanPSFMag",
    "rMeanPSFMagErr",
    "iMeanPSFMag",
    "iMeanPSFMagErr",
    "zMeanPSFMag",
    "zMeanPSFMagErr",
    "yMeanPSFMag",
    "yMeanPSFMagErr",
    "gMeanKronMag",
    "gMeanKronMagErr",
    "rMeanKronMag",
    "rMeanKronMagErr",
    "iMeanKronMag",
    "iMeanKronMagErr",
    "zMeanKronMag",
    "zMeanKronMagErr",
    "yMeanKronMag",
    "yMeanKronMagErr",
    "gMeanApMag",
    "gMeanApMagErr",
    "rMeanApMag",
    "rMeanApMagErr",
    "iMeanApMag",
    "iMeanApMagErr",
    "zMeanApMag",
    "zMeanApMagErr",
    "yMeanApMag",
    "yMeanApMagErr",
]
# epochMean (MJD of the mean position) lets Gaia proper motions be propagated
# to the PS1 epoch (2.16.0); objInfoFlag carries the PS1 known-Solar-System
# matches (HAS_SOLSYS_DET 512, MOST_SOLSYS_DET 1024; Flewelling et al. 2020)
# and qualityFlag the measurement quality (2.29.0).  The per-band standard
# deviation and number of the single-epoch PSF magnitudes measure multi-epoch
# variability (~12 epochs per band over ~4 yr in 3pi; Chambers et al. 2016;
# quasar variability: MacLeod et al. 2010; PS1 3pi quasar selection:
# Hernitschek et al. 2016) (2.36.0).  Optional, dropped if the service
# rejects them.
OPTIONAL_COLUMNS = ["epochMean", "objInfoFlag", "qualityFlag"] + [
    f"{b}MeanPSFMag{k}" for b in "grizy" for k in ("Std", "Npt")
]


# VizieR copy of the same PS1 DR2 MeanObject + ObjectThin tables (II/389/ps1_dr2,
# built by CDS from MAST with nDetections > 2), used when the MAST API fails
# (2.54.0).  Practical-use probe 2026-11-15 (COSMOS 2', a b = -2 field 1'):
# every object it holds matches MAST by objID with the same PSF / Kron
# magnitudes (|diff| < 1e-6 mag), nDetections, qualityFlag, objInfoFlag and
# epochMean; the objects it lacks are those with nDetections = 2 (83 of 210
# and 54 of 698 rows).  No aperture magnitudes.  The DR1 copy II/349 has the
# same rows but DR1 flags and epochs, so it is not used.  Rows carry
# ps1_query_status = vizier_fallback (cached one day, archive_cache.py).
VIZIER_FALLBACK = "II/389/ps1_dr2"
VIZIER_MAP = {
    "objID": ("objID",),
    "raMean": ("RAJ2000", "RAdeg"),
    "decMean": ("DEJ2000", "DEdeg"),
    "raMeanErr": ("e_RAJ2000",),
    "decMeanErr": ("e_DEJ2000",),
    "nDetections": ("Nd",),
    "epochMean": ("Epoch",),
    "objInfoFlag": ("f_objID",),
    "qualityFlag": ("Qual",),
    **{f"n{b}": (f"N{b}",) for b in "grizy"},
    **{f"{b}MeanPSFMag": (f"{b}mag",) for b in "grizy"},
    **{f"{b}MeanPSFMagErr": (f"e_{b}mag",) for b in "grizy"},
    **{f"{b}MeanPSFMagStd": (f"{b}magStd",) for b in "grizy"},
    **{f"{b}MeanPSFMagNpt": (f"o_{b}mag",) for b in "grizy"},
    **{f"{b}MeanKronMag": (f"{b}Kmag",) for b in "grizy"},
    **{f"{b}MeanKronMagErr": (f"e_{b}Kmag",) for b in "grizy"},
}


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    try:
        return _fetch_mast(ra, dec, radius_arcmin)
    except Exception as exc:  # SSL / connection / 5xx / timeout at MAST
        print(
            f"[panstarrs1] MAST failed ({type(exc).__name__}: {str(exc)[:160]}); VizieR {VIZIER_FALLBACK} instead",
            flush=True,
        )
        return _fetch_vizier(ra, dec, radius_arcmin)


def _fetch_vizier(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from _catalog_utils import vizier_cone

    v = vizier_cone(VIZIER_FALLBACK, ra, dec, radius_arcmin)
    cols = ["catalog", "catalog_object_id", "object_name", "ra", "dec", *COLUMNS, "ps1_query_status"]
    if v is None or v.empty:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(index=v.index)
    for out, cands in VIZIER_MAP.items():
        src = next((c for c in cands if c in v.columns), None)
        df[out] = v[src] if src is not None else pd.NA
    df["objID"] = pd.to_numeric(df["objID"], errors="coerce").astype("Int64").astype("string")
    df = df[pd.to_numeric(df["nDetections"], errors="coerce").ge(MIN_DETECTIONS)]
    if df.empty:
        return pd.DataFrame(columns=cols)
    for c in COLUMNS:
        if c not in df:
            df[c] = pd.NA
    df["objName"] = df["objName"].astype("string")
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["objID"])
    df.insert(2, "object_name", "PS1 " + df["objID"])
    df.insert(3, "ra", pd.to_numeric(df["raMean"], errors="coerce"))
    df.insert(4, "dec", pd.to_numeric(df["decMean"], errors="coerce"))
    df["ps1_query_status"] = "vizier_fallback"
    df = df.drop_duplicates("catalog_object_id", keep="last")
    return dedupe_positions(df).reset_index(drop=True)


def _fetch_mast(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    # nDetections >= 2 (STScI PS1 guidance): single-detection MeanObject rows are
    # mostly spurious/moving; they duplicated real sources and made Stage-1
    # association ambiguous in real fields.
    p = {
        # Fixed-point text: str() of a coordinate within 1e-4 deg of 0 is in
        # exponent notation, which NED misread (2.33.0); not left to chance here.
        "ra": f"{float(ra):.10f}",
        "dec": f"{float(dec):.10f}",
        "radius": f"{float(radius_arcmin) / 60.0:.10f}",
        "nDetections.gte": MIN_DETECTIONS,
        "columns": "[" + ",".join(COLUMNS + OPTIONAL_COLUMNS) + "]",
    }
    r = requests.get(API, params=p, timeout=120)
    if 400 <= r.status_code < 500:
        p["columns"] = "[" + ",".join(COLUMNS) + "]"
        r = requests.get(API, params=p, timeout=120)
    r.raise_for_status()
    # MAST answers a cone without matching rows with an empty 200 body (no CSV
    # header); that is "no sources", not a failure (2.26.0: 486 of 8257 faint
    # DESI benchmark targets were counted as query errors).
    if not r.text.strip():
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", *COLUMNS])
    df = pd.read_csv(StringIO(r.text), dtype={"objID": "string", "objName": "string"})
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", *COLUMNS])
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["objID"].astype("string"))
    df.insert(2, "object_name", df["objName"].fillna("PS1 " + df["objID"].astype("string")))
    df.insert(3, "ra", df["raMean"])
    df.insert(4, "dec", df["decMean"])
    df = df.drop_duplicates("catalog_object_id", keep="last")
    return dedupe_positions(df).reset_index(drop=True)


DEDUPE_ARCSEC = 0.5


def dedupe_positions(df: pd.DataFrame, radius_arcsec: float = DEDUPE_ARCSEC) -> pd.DataFrame:
    """Drop duplicate MeanObject rows of one source (several objIDs, e.g. across
    projection-cell overlaps, at < 0.5 arcsec -- well below PS1's ~1 arcsec seeing,
    so not separate sources).  Keeps the row with the most detections."""
    import math

    if len(df) < 2:
        return df
    d = df.assign(_n=pd.to_numeric(df.get("nDetections"), errors="coerce").fillna(0)).sort_values(
        "_n", ascending=False, kind="stable"
    )
    cell = radius_arcsec / 3600.0
    grid = {}
    keep = []
    ras = pd.to_numeric(d["ra"], errors="coerce")
    # RA relative to one row of the cone, wrapped to (-180, 180]: rows at 359.9999
    # and 0.0001 deg are neighbours, not 360 deg apart (2.23.0).
    ref = float(ras.dropna().iloc[0]) if ras.notna().any() else 0.0
    for idx, ra, dec in zip(d.index, ((ras - ref + 180.0) % 360.0) - 180.0, pd.to_numeric(d["dec"], errors="coerce")):
        if ra != ra or dec != dec:
            keep.append(idx)
            continue
        c = math.cos(math.radians(dec))
        kx, ky = int(math.floor(ra * c / cell)), int(math.floor(dec / cell))
        dup = False
        for i in (kx - 1, kx, kx + 1):
            for j in (ky - 1, ky, ky + 1):
                for r2, d2 in grid.get((i, j), ()):
                    if math.hypot((ra - r2) * c, dec - d2) * 3600.0 < radius_arcsec:
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if not dup:
            keep.append(idx)
            grid.setdefault((kx, ky), []).append((ra, dec))
    return df.loc[df.index.isin(keep)]


def save(df: pd.DataFrame, path: str | Path) -> None:
    if not {"catalog", "catalog_object_id", "object_name", "ra", "dec"}.issubset(df.columns):
        raise ValueError("invalid Pan-STARRS output")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)

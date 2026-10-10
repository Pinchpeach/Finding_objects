"""Pan-STARRS1 DR2 independent photometry collector. No cross-match/classification."""

from io import StringIO
from pathlib import Path
import pandas as pd, requests

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


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    # nDetections >= 2 (STScI PS1 guidance): single-detection MeanObject rows are
    # mostly spurious/moving; they duplicated real sources and made Stage-1
    # association ambiguous in real fields.
    p = {
        "ra": ra,
        "dec": dec,
        "radius": radius_arcmin / 60.0,
        "nDetections.gte": MIN_DETECTIONS,
        "columns": "[" + ",".join(COLUMNS) + "]",
    }
    r = requests.get(API, params=p, timeout=120)
    r.raise_for_status()
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
    for idx, ra, dec in zip(d.index, pd.to_numeric(d["ra"], errors="coerce"), pd.to_numeric(d["dec"], errors="coerce")):
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

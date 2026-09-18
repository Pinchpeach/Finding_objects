"""Real-data SDSS SED validation with independent, retryable queries."""
from io import StringIO
import json
from pathlib import Path
import time

import pandas as pd
import requests

from finding_objects.catalog import save_classification
from finding_objects.sed import build_sed

RA, DEC = 150.114557, 2.203106
TIMEOUT = 30
RETRIES = 5
BACKOFF = 1.0
BASE = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
BANDS = {"u": 3551.0, "g": 4686.0, "r": 6165.0, "i": 7481.0, "z": 8931.0}


def sdss_sql(sql: str, retries: int = RETRIES) -> pd.DataFrame:
    """Run one SDSS query with bounded exponential backoff."""
    last = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                BASE, params={"cmd": sql, "format": "csv"}, timeout=TIMEOUT
            )
            response.raise_for_status()
            return pd.read_csv(StringIO(response.text))
        except (requests.RequestException, pd.errors.ParserError) as exc:
            last = exc
            if attempt >= retries:
                break
            time.sleep(BACKOFF * (2 ** attempt))
    raise RuntimeError(f"SDSS query failed after {retries + 1} attempts") from last


def photometry_from_sdss_row(row: pd.Series) -> pd.DataFrame:
    """Use only bands actually returned by SDSS; missing bands are not failures."""
    normalized = row.copy()
    normalized.index = [str(name).strip().lower() for name in row.index]
    points = []
    for band, wavelength in BANDS.items():
        value = normalized.get(band, pd.NA)
        if pd.isna(value):
            continue
        try:
            magnitude = float(value)
        except (TypeError, ValueError):
            continue
        if not pd.api.types.is_number(magnitude) or not pd.notna(magnitude):
            continue
        points.append({
            "band": band,
            "effective_wavelength_angstrom": wavelength,
            "ab_mag": magnitude,
        })
    return pd.DataFrame(points)


def main() -> None:
    out = Path("results/spectral")
    out.mkdir(parents=True, exist_ok=True)

    photo_sql = f"""SELECT TOP 1 p.objid,p.ra,p.dec,p.u,p.g,p.r,p.i,p.z
FROM dbo.fGetNearbyObjEq({RA},{DEC},0.02) AS n
JOIN PhotoObj AS p ON p.objid=n.objid
ORDER BY n.distance"""
    photo = sdss_sql(photo_sql)
    photo.columns = [str(name).strip().lower() for name in photo.columns]
    if photo.empty:
        raise RuntimeError("No SDSS photometric counterpart found")
    if "objid" not in photo.columns:
        raise RuntimeError(f"Unexpected SDSS photometry columns: {list(photo.columns)}")

    row = photo.iloc[0]
    phot = photometry_from_sdss_row(row)
    if phot.empty:
        raise RuntimeError(
            f"SDSS counterpart has no usable ugriz photometry; columns={list(photo.columns)}"
        )
    sed = build_sed(phot)
    sed.to_csv(out / "candidate1_sed.csv", index=False)

    spec = pd.DataFrame()
    spec_error = None
    try:
        spec_sql = f"""SELECT TOP 1 s.specobjid,s.z as redshift,s.class,s.subclass
FROM SpecObj AS s
WHERE s.bestobjid={int(row['objid'])}"""
        spec = sdss_sql(spec_sql)
        spec.columns = [str(name).strip().lower() for name in spec.columns]
    except Exception as exc:
        spec_error = str(exc)

    has_spec = not spec.empty
    record = {
        "object_id": "candidate-1",
        "ra": RA,
        "dec": DEC,
        "sdss_objid": str(row["objid"]),
        "object_type": "sdss_spectroscopic_object" if has_spec else "photometry_only",
        "redshift": (
            float(spec.iloc[0]["redshift"])
            if has_spec and "redshift" in spec.columns
            and pd.notna(spec.iloc[0]["redshift"])
            else None
        ),
        "line_tags": [],
        "object_tags": [
            "survey:sdss",
            "object:sdss_spectroscopic_object" if has_spec else "object:photometry_only",
        ],
        "spectrum_status": (
            "available" if has_spec else ("no_response" if spec_error else "not_observed")
        ),
    }
    record["object_tags"].append(f"spectrum:{record['spectrum_status']}")
    if has_spec:
        record["sdss_class"] = str(spec.iloc[0].get("class", "unknown"))
        record["sdss_subclass"] = str(spec.iloc[0].get("subclass", ""))
    if spec_error:
        record["spectrum_error"] = spec_error

    save_classification(record, out / "candidate1_classification.json")
    print(sed.to_string(index=False))
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()

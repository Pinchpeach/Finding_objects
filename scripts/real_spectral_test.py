"""Real-data SDSS SED validation with independent, retryable queries."""
from io import StringIO
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests

from finding_objects.catalog import save_classification
from finding_objects.sed import build_sed
from finding_objects.sdss import photometry_from_sdss_row, read_skyserver_csv
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u

RA, DEC = 150.114557, 2.203106
TIMEOUT = 30
RETRIES = 5
BACKOFF = 1.0
BASE = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def sdss_sql(sql: str, retries: int = RETRIES) -> pd.DataFrame:
    """Run one SDSS query with bounded exponential backoff."""
    last = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                BASE, params={"cmd": sql, "format": "csv"}, timeout=TIMEOUT
            )
            response.raise_for_status()
            text = response.text.lstrip("\ufeff")
            lines = text.splitlines()
            # SkyServer CSV may prepend metadata markers such as "#Table1".
            header_idx = next(
                (i for i, line in enumerate(lines)
                 if "," in line and not line.lstrip().startswith("#")),
                None,
            )
            if header_idx is None:
                return pd.DataFrame()
            return read_skyserver_csv(text)
        except (requests.RequestException, pd.errors.ParserError) as exc:
            last = exc
            if attempt >= retries:
                break
            time.sleep(BACKOFF * (2 ** attempt))
    raise RuntimeError(f"SDSS query failed after {retries + 1} attempts") from last


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

    # Independent multi-survey photometry check. Failure/no coverage is non-fatal.
    multi = []
    coord = SkyCoord(RA * u.deg, DEC * u.deg)
    Vizier.TIMEOUT = TIMEOUT
    survey_specs = {
        "GALEX": ("II/335/galex_ais", ["FUVmag", "NUVmag"]),
        "Pan-STARRS_DR1": ("II/349/ps1", ["gmag", "rmag", "imag", "zmag", "ymag"]),
        "2MASS": ("II/246/out", ["Jmag", "Hmag", "Kmag"]),
        "AllWISE": ("II/328/allwise", ["W1mag", "W2mag", "W3mag", "W4mag"]),
        "NVSS": ("VIII/65/nvss", ["S1.4"]),
        "FIRST": ("VIII/92/first14", ["Fpeak", "Fint"]),
        "Planck_PCCS2": ("VIII/100/pcnt", ["S30", "S44", "S70", "S100"]),
        "XMM_4XMM": ("IX/65/xmm4dr13s", ["Flux1", "Flux2", "Flux3", "Flux4", "Flux5"]),
    }
    survey_status = {}
    survey_match_radius = {}
    for survey, (catalog, magcols) in survey_specs.items():
        try:
            tables = None
            matched_radius = None
            for radius_arcsec in (1.0, 2.0, 5.0, 15.0, 30.0):
                candidate_tables = Vizier(columns=["*", "+_r"], row_limit=5).query_region(
                    coord, radius=radius_arcsec * u.arcsec, catalog=catalog
                )
                if candidate_tables and len(candidate_tables[0]) > 0:
                    tables = candidate_tables
                    matched_radius = radius_arcsec
                    break
            if not tables or len(tables[0]) == 0:
                survey_status[survey] = "not_observed"
                survey_match_radius[survey] = None
                continue
            survey_match_radius[survey] = matched_radius
            tab = tables[0]
            j = int(np.nanargmin(np.asarray(tab["_r"], dtype=float))) if "_r" in tab.colnames else 0
            actual_sep = float(tab["_r"][j]) if "_r" in tab.colnames else None
            used = 0
            for col in magcols:
                if col not in tab.colnames:
                    continue
                value = tab[col][j]
                try:
                    mag = float(value)
                except (TypeError, ValueError):
                    continue
                if not np.isfinite(mag):
                    continue
                multi.append({"survey": survey, "band": col.replace("mag", ""), "ab_or_catalog_mag": mag, "separation_arcsec": actual_sep})
                used += 1
            survey_status[survey] = "available" if used else "not_observed"
        except Exception as exc:
            survey_status[survey] = "no_response"
            multi.append({"survey": survey, "band": "ERROR", "ab_or_catalog_mag": str(exc)})
    pd.DataFrame(multi).to_csv(out / "candidate1_multisurvey_photometry.csv", index=False)

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
        "photometry_survey_status": survey_status,
        "photometry_match_radius_arcsec": survey_match_radius,
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

from __future__ import annotations

import pandas as pd

BANDS = {"u": 3551.0, "g": 4686.0, "r": 6165.0, "i": 7481.0, "z": 8931.0}


def photometry_from_sdss_row(row: pd.Series) -> pd.DataFrame:
    """Convert whatever usable ugriz values are present; missing bands are allowed."""
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
        if not pd.notna(magnitude):
            continue
        points.append({
            "band": band,
            "effective_wavelength_angstrom": wavelength,
            "ab_mag": magnitude,
        })
    return pd.DataFrame(points)


def read_skyserver_csv(text: str) -> pd.DataFrame:
    """Parse SkyServer CSV while preserving identifier columns exactly."""
    from io import StringIO
    cleaned = text.lstrip("\ufeff")
    lines = cleaned.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines)
         if "," in line and not line.lstrip().startswith("#")),
        None,
    )
    if header_idx is None:
        return pd.DataFrame()
    return pd.read_csv(
        StringIO("\n".join(lines[header_idx:])),
        dtype=str,
        keep_default_na=True,
    )

from __future__ import annotations

import numpy as np
import pandas as pd

def build_sed(photometry: pd.DataFrame) -> pd.DataFrame:
    """Normalize heterogeneous photometry into wavelength-sorted SED points.

    Required columns: band, effective_wavelength_angstrom and either
    flux_density_jy or ab_mag.
    """
    sed = photometry.copy()
    if "flux_density_jy" not in sed:
        if "ab_mag" not in sed:
            raise ValueError("Need flux_density_jy or ab_mag")
        sed["flux_density_jy"] = 3631.0 * 10 ** (-0.4 * sed["ab_mag"].astype(float))
    required = {"band", "effective_wavelength_angstrom", "flux_density_jy"}
    missing = required - set(sed.columns)
    if missing:
        raise ValueError(f"Missing SED columns: {sorted(missing)}")
    sed = sed.sort_values("effective_wavelength_angstrom").reset_index(drop=True)
    sed["nu_hz"] = 2.99792458e18 / sed["effective_wavelength_angstrom"].astype(float)
    sed["nu_fnu_jy_hz"] = sed["nu_hz"] * sed["flux_density_jy"].astype(float)
    return sed

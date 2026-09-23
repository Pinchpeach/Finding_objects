from __future__ import annotations

import numpy as np
import pandas as pd

from .classification import LINE_LIBRARY, SpectralLine

def identify_lines(spectrum: pd.DataFrame, redshift: float = 0.0,
                   sigma_threshold: float = 4.0, window: int = 21) -> list[SpectralLine]:
    """Identify candidate emission/absorption features near known rest lines."""
    wave = spectrum["wavelength_angstrom"].to_numpy(dtype=float)
    flux = spectrum["flux"].to_numpy(dtype=float)
    continuum = pd.Series(flux).rolling(window, center=True, min_periods=3).median().to_numpy()
    resid = flux - continuum
    noise = np.nanstd(resid)
    if not np.isfinite(noise) or noise <= 0:
        return []
    found = []
    for name, rest in LINE_LIBRARY.items():
        obs = rest * (1.0 + redshift)
        j = int(np.nanargmin(np.abs(wave - obs)))
        if abs(wave[j] - obs) > max(3.0, obs * 3e-4):
            continue
        significance = resid[j] / noise
        if abs(significance) >= sigma_threshold:
            found.append(SpectralLine(name, rest, float(wave[j]),
                                      kind="emission" if significance > 0 else "absorption"))
    return found

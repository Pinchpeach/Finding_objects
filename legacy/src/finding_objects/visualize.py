from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.visualization import AsinhStretch, ImageNormalize, PercentileInterval
from astropy.wcs import WCS


def render_candidate_pngs(
    fits_path: Path,
    candidates_csv: Path,
    output_dir: Path,
    candidate_label: str = "high_snr_unmatched",
    zoom_radius: int = 18,
) -> list[Path]:
    """Render a survey field and zoomed candidate PNGs from FITS + catalogue."""
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(candidates_csv)
    selected = df[df["candidate_label"].eq(candidate_label)]
    if selected.empty:
        raise ValueError(f"No candidate with label {candidate_label!r}")
    candidate = selected.iloc[0]

    with fits.open(fits_path) as hdul:
        data = np.squeeze(np.asarray(hdul[0].data, dtype=float))
        wcs = WCS(hdul[0].header).celestial
    if data.ndim != 2:
        raise ValueError(f"Expected 2-D FITS image; got {data.shape}")

    x, y = wcs.world_to_pixel_values(float(candidate.ra), float(candidate.dec))
    norm = ImageNormalize(data, interval=PercentileInterval(99.5), stretch=AsinhStretch())

    field_path = output_dir / "candidate_field.png"
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(data, origin="lower", cmap="gray", norm=norm)
    ax.scatter([x], [y], facecolors="none", edgecolors="red", s=220, linewidths=2)
    ax.set_title("Legacy Surveys r-band — candidate field")
    ax.set_xlabel("x pixel")
    ax.set_ylabel("y pixel")
    fig.tight_layout()
    fig.savefig(field_path, dpi=180)
    plt.close(fig)

    r = zoom_radius
    x0, x1 = max(0, int(x) - r), min(data.shape[1], int(x) + r + 1)
    y0, y1 = max(0, int(y) - r), min(data.shape[0], int(y) + r + 1)
    cut = data[y0:y1, x0:x1]
    zoom_norm = ImageNormalize(cut, interval=PercentileInterval(99.0), stretch=AsinhStretch())

    zoom_path = output_dir / "candidate_zoom.png"
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(cut, origin="lower", cmap="gray", norm=zoom_norm)
    ax.scatter([x - x0], [y - y0], facecolors="none", edgecolors="red", s=260, linewidths=2)
    ax.set_title(f"Candidate zoom — S/N {float(candidate.snr):.1f}")
    ax.set_xlabel("x pixel")
    ax.set_ylabel("y pixel")
    fig.tight_layout()
    fig.savefig(zoom_path, dpi=200)
    plt.close(fig)
    return [field_path, zoom_path]

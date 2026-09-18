import numpy as np
import pandas as pd
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from finding_objects.pipeline import RunConfig, detect_sources, label_candidates


def test_label_candidates():
    cfg = RunConfig(ra=10.0, dec=20.0, high_snr=10.0)
    sources = pd.DataFrame({
        "source_id": [1, 2, 3],
        "snr": [20.0, 5.0, 15.0],
        "gaia_sep_arcsec": [0.2, np.nan, np.nan],
    })
    result = label_candidates(sources, cfg)
    assert result["candidate_label"].tolist() == [
        "gaia_matched", "unmatched_source", "high_snr_unmatched"
    ]


def test_detect_sources_on_synthetic_fits(tmp_path):
    rng = np.random.default_rng(42)
    image = rng.normal(100.0, 1.0, (64, 64))
    yy, xx = np.mgrid[:64, :64]
    image += 100.0 * np.exp(-((xx - 32.0) ** 2 + (yy - 31.0) ** 2) / (2 * 1.3 ** 2))

    w = WCS(naxis=2)
    w.wcs.crpix = [32.0, 32.0]
    w.wcs.cdelt = np.array([-0.262 / 3600, 0.262 / 3600])
    w.wcs.crval = [150.0, 2.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    path = tmp_path / "synthetic.fits"
    fits.writeto(path, image, w.to_header())
    result = detect_sources(path, RunConfig(ra=150.0, dec=2.0))
    assert len(result) >= 1
    nearest = result.iloc[((result.x - 32) ** 2 + (result.y - 31) ** 2).argmin()]
    assert nearest.snr > 10
    assert nearest.ra == pytest.approx(150.0, abs=0.01)
    assert nearest.dec == pytest.approx(2.0, abs=0.01)

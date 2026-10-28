"""DESI BGS Gaia star-galaxy test (2.42.0)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import bgs_galaxy  # noqa: E402

LS = "desi_legacy_surveys_dr10__"


def _field(n_gaia=40, spread=0.05):
    """A high-latitude search: n_gaia Gaia stars plus five test sources."""
    rng = np.random.default_rng(1)
    stars = pd.DataFrame(
        {
            "ra": 10 + rng.uniform(-spread, spread, n_gaia),
            "dec": -30 + rng.uniform(-spread, spread, n_gaia),
            "gaia_dr3__phot_g_mean_mag": rng.uniform(15, 20, n_gaia),
            f"{LS}type": "PSF",
        }
    )
    test = pd.DataFrame(
        {
            "ra": [10.0] * 5,
            "dec": [-30.0] * 5,
            f"{LS}type": ["SER", "EXP", "PSF", "SER", "DEV"],
            # resolved, no Gaia, r = 19 | resolved, G - r = 1.0 | PSF, no Gaia | resolved, no Gaia, r = 21 | resolved, no r, z = 18.5
            "std_mag__ls_r": [19.0, 18.0, 19.0, 21.0, np.nan],
            "std_mag__ls_z": [18.5, 17.5, 18.5, 20.5, 18.5],
            "std_mag__ls_g": [19.8, 18.8, 19.8, 21.8, np.nan],
            "gaia_dr3__phot_g_mean_mag": [np.nan, 19.0, np.nan, np.nan, np.nan],
        }
    )
    return pd.concat([stars, test], ignore_index=True)


def test_resolved_sources_without_gaia_or_faint_in_gaia_are_galaxies():
    t = bgs_galaxy.galaxy_test(_field())[-5:]
    assert t.tolist() == [True, True, False, False, True]


def test_no_claim_without_gaia_coverage_or_in_crowded_fields():
    assert not bgs_galaxy.galaxy_test(_field(n_gaia=5))[-5:].any()  # Gaia not reached
    assert not bgs_galaxy.galaxy_test(_field(n_gaia=400, spread=0.005))[-5:].any()  # ~10^7 deg^-2

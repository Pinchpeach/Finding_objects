"""Single coarse GBM (2.51.0): features from survey-prefixed columns, numpy inference."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_p = Path(__file__).resolve().parents[1] / "coarse_gbm.py"
_s = importlib.util.spec_from_file_location("coarse_gbm_t", _p)
CG = importlib.util.module_from_spec(_s)
_s.loader.exec_module(CG)


def _rows():
    return pd.DataFrame(
        {
            "gaia_dr3__parallax": [12.0, 0.01, np.nan],
            "gaia_dr3__parallax_error": [0.05, 0.4, np.nan],
            "gaia_dr3__pmra": [80.0, 0.1, np.nan],
            "gaia_dr3__pmra_error": [0.05, 0.4, np.nan],
            "gaia_dr3__pmdec": [-40.0, 0.2, np.nan],
            "gaia_dr3__pmdec_error": [0.05, 0.4, np.nan],
            "gaia_dr3__classprob_dsc_combmod_star": [0.9, 0.0, np.nan],
            "gaia_dr3__classprob_dsc_combmod_whitedwarf": [0.05, 0.0, np.nan],
            "gaia_dr3__classprob_dsc_combmod_binarystar": [0.05, 0.0, np.nan],
            "gaia_dr3__classprob_dsc_combmod_quasar": [0.0, 0.99, np.nan],
            "gaia_dr3__classprob_dsc_combmod_galaxy": [0.0, 0.01, np.nan],
            "desi_legacy_surveys_dr10__type": ["PSF", "PSF", np.nan],
        }
    )


def test_features_sum_dsc_star_and_mark_missing():
    x = CG.features(_rows())
    assert x.dsc_star.iloc[0] == pytest.approx(1.0)
    assert x.plx_snr.iloc[0] == pytest.approx(240.0)
    assert x.ls_psf.iloc[0] == 1.0 and np.isnan(x.ls_psf.iloc[2])
    assert x.iloc[2].isna().all()


def test_predict_proba_sums_to_one_and_skips_empty_rows():
    out = CG.predict_proba(_rows())
    if out is None:
        pytest.skip("coarse_gbm_model.npz not present")
    P, has = out
    assert list(has) == [True, True, False]
    assert np.allclose(P[has].sum(axis=1), 1.0)
    # a 240-sigma parallax / proper motion is a star; a DSC quasar with zero motion is not
    assert P[0].argmax() == 0 and P[1].argmax() != 0

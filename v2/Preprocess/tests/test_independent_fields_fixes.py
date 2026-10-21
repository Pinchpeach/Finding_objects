"""Fixes from the independent-truth field validation (2.35.0)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))
sys.path.insert(0, str(V2 / "Preprocess"))
import lamost_spectroscopy  # noqa: E402
import ls_gbm  # noqa: E402


def test_repeat_lamost_spectra_of_one_star_become_one_row(monkeypatch):
    # Three spectra of one star at input-catalogue positions up to 0.8" apart,
    # and a second star 4" away (beyond the minimum fibre spacing).
    d = pd.DataFrame(
        {
            "ObsID": [1, 2, 3, 4],
            "RAJ2000": [150.0, 150.0 + 0.5 / 3600, 150.0, 150.0 + 4 / 3600],
            "DEJ2000": [2.0, 2.0, 2.0 + 0.8 / 3600, 2.0],
            "Class": ["STAR"] * 4,
            "snrg": [5.0, 40.0, 12.0, 30.0],
            "snrr": [6.0, 50.0, 15.0, 35.0],
            "snri": [7.0, 55.0, 16.0, 36.0],
        }
    )
    monkeypatch.setattr(
        lamost_spectroscopy, "vizier_cone", lambda cat, *a, **k: d.copy() if cat == lamost_spectroscopy.VIZIER_CATALOG else None
    )
    out = lamost_spectroscopy.fetch(150.0, 2.0, 1.0)
    assert sorted(out.catalog_object_id) == ["2", "4"]  # best-S/N spectrum of the repeated star


def _ls_row(**kw):
    row = {f"desi_legacy_surveys_dr10__{k}": v for k, v in kw.items()}
    return row


def test_ls_gbm_gives_no_evidence_without_r_band_imaging():
    if ls_gbm.load_model() is None:
        return
    base = dict(type="SER", flux_g=3.0, flux_z=12.0, flux_w1=20.0, flux_w2=12.0, flux_ivar_g=50.0, flux_ivar_z=10.0, flux_ivar_w1=1.0, flux_ivar_w2=0.5)
    with_r = _ls_row(**base, flux_r=6.0, flux_ivar_r=30.0)
    no_r = _ls_row(**base, flux_r=0.0, flux_ivar_r=0.0)  # DR10 area never imaged in r
    p = ls_gbm.predict_proba(pd.DataFrame([with_r, no_r]))
    assert np.isfinite(p[0]).all()
    assert np.isnan(p[1]).all()


def test_latitude_prior_scales_extragalactic_odds_only_near_the_plane():
    import importlib.util

    spec = importlib.util.spec_from_file_location("s5", V2 / "Preprocess" / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    # Galactic anticentre at b ~ +2.3, the Kepler field (b ~ +13), the NGP, no position
    f = s5.latitude_factor(pd.DataFrame({"ra": [89.92, 291.23, 192.86, np.nan], "dec": [28.30, 44.90, 27.13, np.nan]}))
    assert abs(f[0] - np.sin(np.radians(2.3)) / np.sin(np.radians(20))) < 0.01
    assert 0.6 < f[1] < 0.75
    assert f[2] == 1.0 and f[3] == 1.0


def test_gaia_optional_tables_merge_in_chunks(monkeypatch):
    import gaia_dr3

    calls = []

    def fake_tap(query):
        ids = query.split("IN (")[1].rstrip(")").split(",")
        calls.append(len(ids))
        return pd.DataFrame({"source_id": [int(i) for i in ids], "classprob_dsc_combmod_quasar": 0.1})

    monkeypatch.setattr(gaia_dr3, "_tap", fake_tap)
    monkeypatch.setattr(gaia_dr3, "_bounded", lambda fn, left, *a: fn(*a))
    base = pd.DataFrame({"source_id": np.arange(1, 4501)})
    out = gaia_dr3._merge_optional(base, "gaiadr3.astrophysical_parameters", ["classprob_dsc_combmod_quasar"], "dsc_status")
    assert calls == [2000, 2000, 500]
    assert out["classprob_dsc_combmod_quasar"].notna().all() and set(out["dsc_status"]) == {"ok"}

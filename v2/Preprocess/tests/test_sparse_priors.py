"""Priors for evidence-free objects (2.43.0)."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import sparse_priors as sp  # noqa: E402


def _crowd(n, ra=6.02, dec=-72.08, spread=0.003):
    rng = np.random.default_rng(3)
    return pd.DataFrame(
        {
            "object_id": [f"S{i}" for i in range(n)],
            "ra": ra + rng.uniform(-spread, spread, n),
            "dec": dec + rng.uniform(-spread, spread, n),
            "catalogs": "Gaia DR3",
            "gaia_dr3__phot_g_mean_mag": rng.uniform(13, 18, n),
            "gaia_dr3__parallax": np.nan,  # 2-parameter solutions
        }
    )


def test_two_parameter_gaia_sources_are_stars_only_in_crowded_fields():
    dense = _crowd(400)  # ~10^7 deg^-2
    assert sp.gaia_point_star(dense).all()
    sparse = _crowd(40, ra=180.0, dec=30.0, spread=0.05)
    assert not sp.gaia_point_star(sparse).any()
    sparse["gaia_dr3__parallax"] = 0.3  # 5-parameter solutions
    assert sp.gaia_point_star(sparse).all()
    sparse["gaia_dr3__phot_g_mean_mag"] = 19.5
    assert not sp.gaia_point_star(sparse).any()


def test_mid_ir_only_red_sources_are_galaxies_at_high_latitude():
    d = pd.DataFrame(
        {
            "ra": [180.0, 180.0, 180.0, 180.0, 270.0],
            "dec": [30.0, 30.0, 30.0, 30.0, -29.0],  # NGP x4, Galactic centre
            "catalogs": ["AllWISE", "AllWISE", "AllWISE|Gaia DR3", "AllWISE", "AllWISE"],
            "allwise__W2mag": [14.5, 14.5, 14.5, 14.5, 14.5],
            "allwise__W3mag": [11.0, 14.4, 11.0, 11.0, 11.0],
            "allwise__snr3": [8.0, 8.0, 8.0, 1.5, 8.0],
        }
    )
    assert sp.wise_only_galaxy(d).tolist() == [True, False, False, False, False]


def test_stage5_uses_the_priors_only_without_evidence(tmp_path):
    spec = importlib.util.spec_from_file_location("s5_sparse", V2 / "Preprocess" / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    d = _crowd(60)
    d["evidence_json"] = "[]"
    gal = {"rule_id": "PS1-MORPH-001", "class": "GALAXY", "score": 0.95, "raw_score": 0.95, "kind": "binary_evidence"}
    d.loc[0, "evidence_json"] = json.dumps([gal])
    ev, out = tmp_path / "e.csv", tmp_path / "l.csv"
    d.to_csv(ev, index=False)
    s5.run(ev, out)
    r = pd.read_csv(out)
    assert (r.primary_class.iloc[1:] == "STAR").all() and (r.classification_basis.iloc[1:] == sp.GAIA_BASIS).all()
    assert r.classification_basis.iloc[0] != sp.GAIA_BASIS

"""Bright-star halo rows from several shallow surveys; atlas galaxies in a neighbour's ellipse (2.45.0)."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2))
import host_groups as hg  # noqa: E402


def _load(name, file):
    s = importlib.util.spec_from_file_location(name, V2 / "Preprocess" / file)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _field():
    ra, dec, d = 150.0, 2.0, 1.0 / 3600
    rows = [
        # a G = 10 star, a Legacy Surveys neighbour far away (LS coverage)
        dict(object_id="S", ra=ra, dec=dec, catalogs="Gaia DR3|DESI Legacy Surveys DR10|Pan-STARRS1 DR2 MeanObject", primary_class="STAR", gaia_dr3__phot_g_mean_mag=10.0),
        dict(object_id="L", ra=ra + 30 * d, dec=dec, catalogs="DESI Legacy Surveys DR10", primary_class="GALAXY", gaia_dr3__phot_g_mean_mag=None),
        # PS1+SDSS row 4" from the star: a halo/spike piece of it
        dict(object_id="H", ra=ra + 4 * d, dec=dec, catalogs="Pan-STARRS1 DR2 MeanObject|SDSS DR18 PhotoObj", primary_class="UNKNOWN", gaia_dr3__phot_g_mean_mag=None),
        # same place but measured by the Legacy Surveys: a real neighbour, kept apart
        dict(object_id="R", ra=ra, dec=dec + 4 * d, catalogs="DESI Legacy Surveys DR10|Pan-STARRS1 DR2 MeanObject", primary_class="GALAXY", gaia_dr3__phot_g_mean_mag=None),
    ]
    return pd.DataFrame(rows)


def test_multi_survey_halo_rows_join_the_star():
    out = hg.attach_bright_star_artifacts(_field()).set_index("object_id")
    assert out.at["H", "parent_object_id"] == "S" and out.at["H", "component_role"] == "bright_star_halo"
    assert pd.isna(out.at["R", "parent_object_id"])  # Legacy Surveys row: not an artefact
    assert out.at["S", "n_components"] == 1


def test_atlas_galaxy_is_not_inside_a_neighbour():
    s5 = _load("s5ha", "05_likelihood_vectors.py")
    sga = [{"class": "GALAXY", "rule_id": "SGA-001", "score": 0.95, "kind": "catalog_label"}]
    assert s5._atlas_galaxy(sga) and not s5._atlas_galaxy([{"class": "GALAXY", "rule_id": "LS-MORPH-001"}])

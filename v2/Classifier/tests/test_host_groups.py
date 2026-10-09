"""Large-galaxy consolidation (v2/host_groups.py)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"v2_{name}", V2 / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _frame():
    fg = json.dumps([{"rule_id": "AST-GAL-002", "raw_score": 0.9}])
    rows = [
        # host: SGA entry at the centre
        dict(object_id="H", designation="NGC4522", designation_catalog="SGA-2020", catalog_designations="NGC4522",
             catalogs="SGA-2020", ra=188.4153, dec=9.1744, sga_2020__catalog_object_id=365058.0),
        # SIMBAD entry of the same galaxy 1 arcsec away -> identity, lends its name
        dict(object_id="S", designation="NGC 4522", designation_catalog="SIMBAD", catalog_designations="NGC 4522",
             catalogs="SIMBAD", ra=188.4155, dec=9.1745, host_large_galaxy=365058, host_elliptical_radius=0.01,
             simbad__rvz_redshift=0.00777),
        # nucleus fibre spectrum at the host redshift -> nucleus
        dict(object_id="N", designation="SDSS spectrum 1", designation_catalog="SDSS DR18 spectroscopy",
             catalog_designations="SDSS spectrum 1", catalogs="SDSS DR18 spectroscopy", ra=188.41545, dec=9.17500,
             host_large_galaxy=365058, host_elliptical_radius=0.01, sdss_dr18_spectroscopy__z=0.0077),
        # shredded knot in the disc -> component
        dict(object_id="K", designation="PSO J1", designation_catalog="Pan-STARRS1 DR2 MeanObject",
             catalog_designations="PSO J1", catalogs="Pan-STARRS1 DR2 MeanObject", ra=188.4170, dec=9.1770,
             host_large_galaxy=365058, host_elliptical_radius=0.3),
        # foreground star (significant proper motion) -> independent
        dict(object_id="F", designation="Gaia DR3 1", designation_catalog="Gaia DR3", catalog_designations="Gaia DR3 1",
             catalogs="Gaia DR3", ra=188.4160, dec=9.1760, host_large_galaxy=365058, host_elliptical_radius=0.2,
             evidence_json=fg),
        # background QSO with a very different redshift -> independent
        dict(object_id="Q", designation="SDSS spectrum 2", designation_catalog="SDSS DR18 spectroscopy",
             catalog_designations="SDSS spectrum 2", catalogs="SDSS DR18 spectroscopy", ra=188.4140, dec=9.1730,
             host_large_galaxy=365058, host_elliptical_radius=0.4, sdss_dr18_spectroscopy__z=1.8),
        # outside the D26 ellipse -> independent
        dict(object_id="O", designation="PSO J2", designation_catalog="Pan-STARRS1 DR2 MeanObject",
             catalog_designations="PSO J2", catalogs="Pan-STARRS1 DR2 MeanObject", ra=188.30, dec=9.10,
             host_large_galaxy=365058, host_elliptical_radius=1.7),
    ]
    return pd.DataFrame(rows)


def test_large_galaxy_fragments_join_their_host():
    hg, names = _load("host_groups"), _load("designations")
    out = hg.consolidate(_frame(), names.PRIORITY).set_index("object_id")
    assert out.loc["S", "component_role"] == "identity" and out.loc["S", "parent_object_id"] == "H"
    assert out.loc["N", "component_role"] == "nucleus" and out.loc["K", "component_role"] == "component"
    for independent in ("F", "Q", "O", "H"):
        assert pd.isna(out.loc[independent, "parent_object_id"]), independent
    assert out.loc["H", "n_components"] == 3
    assert out.loc["H", "designation"] == "NGC 4522" and out.loc["H", "designation_catalog"] == "SIMBAD"
    assert "SIMBAD" in out.loc["H", "catalogs"] and abs(out.loc["H", "host_redshift"] - 0.00777) < 1e-9
    assert out.loc["S", "designation"] == "NGC 4522 (SIMBAD entry)"


def test_cone_cut_keeps_the_host_of_a_kept_component():
    hg, names = _load("host_groups"), _load("designations")
    out = hg.consolidate(_frame(), names.PRIORITY)
    # 2 arcsec around the disc knot: the host centre is ~10 arcsec away
    cut = names.annotate(out, pd.DataFrame(), center=(188.4170, 9.1770), radius_arcmin=2 / 60)
    assert set(cut.object_id) == {"K", "H"}

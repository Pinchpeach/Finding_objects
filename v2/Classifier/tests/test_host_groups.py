"""Large-galaxy consolidation (v2/host_groups.py)."""

from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"v2_{name}", V2 / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _frame():
    fg = json.dumps([{"rule_id": "AST-GAL-002", "raw_score": 0.9}])
    rows = [
        # host: SGA entry at the centre
        dict(
            object_id="H",
            designation="NGC4522",
            designation_catalog="SGA-2020",
            catalog_designations="NGC4522",
            catalogs="SGA-2020",
            ra=188.4153,
            dec=9.1744,
            sga_2020__catalog_object_id=365058.0,
        ),
        # SIMBAD entry of the same galaxy 1 arcsec away -> identity, lends its name
        dict(
            object_id="S",
            designation="NGC 4522",
            designation_catalog="SIMBAD",
            catalog_designations="NGC 4522",
            catalogs="SIMBAD",
            ra=188.4155,
            dec=9.1745,
            host_large_galaxy=365058,
            host_elliptical_radius=0.01,
            simbad__rvz_redshift=0.00777,
        ),
        # nucleus fibre spectrum at the host redshift -> nucleus
        dict(
            object_id="N",
            designation="SDSS spectrum 1",
            designation_catalog="SDSS DR18 spectroscopy",
            catalog_designations="SDSS spectrum 1",
            catalogs="SDSS DR18 spectroscopy",
            ra=188.41545,
            dec=9.17500,
            host_large_galaxy=365058,
            host_elliptical_radius=0.01,
            sdss_dr18_spectroscopy__z=0.0077,
        ),
        # shredded knot in the disc -> component
        dict(
            object_id="K",
            designation="PSO J1",
            designation_catalog="Pan-STARRS1 DR2 MeanObject",
            catalog_designations="PSO J1",
            catalogs="Pan-STARRS1 DR2 MeanObject",
            ra=188.4170,
            dec=9.1770,
            host_large_galaxy=365058,
            host_elliptical_radius=0.3,
        ),
        # foreground star (significant proper motion) -> independent
        dict(
            object_id="F",
            designation="Gaia DR3 1",
            designation_catalog="Gaia DR3",
            catalog_designations="Gaia DR3 1",
            catalogs="Gaia DR3",
            ra=188.4160,
            dec=9.1760,
            host_large_galaxy=365058,
            host_elliptical_radius=0.2,
            evidence_json=fg,
        ),
        # background QSO with a very different redshift -> independent
        dict(
            object_id="Q",
            designation="SDSS spectrum 2",
            designation_catalog="SDSS DR18 spectroscopy",
            catalog_designations="SDSS spectrum 2",
            catalogs="SDSS DR18 spectroscopy",
            ra=188.4140,
            dec=9.1730,
            host_large_galaxy=365058,
            host_elliptical_radius=0.4,
            sdss_dr18_spectroscopy__z=1.8,
        ),
        # outside the D26 ellipse -> independent
        dict(
            object_id="O",
            designation="PSO J2",
            designation_catalog="Pan-STARRS1 DR2 MeanObject",
            catalog_designations="PSO J2",
            catalogs="Pan-STARRS1 DR2 MeanObject",
            ra=188.30,
            dec=9.10,
            host_large_galaxy=365058,
            host_elliptical_radius=1.7,
        ),
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
    assert out.loc["F", "component_role"] == "foreground_star" and out.loc["Q", "component_role"] == "background_source"
    assert out.loc["H", "designation"] == "NGC 4522" and out.loc["H", "designation_catalog"] == "SIMBAD"
    assert "SIMBAD" in out.loc["H", "catalogs"] and abs(out.loc["H", "host_redshift"] - 0.00777) < 1e-9
    assert out.loc["S", "designation"] == "NGC 4522 (SIMBAD entry)"


def test_cone_cut_keeps_the_host_of_a_kept_component():
    hg, names = _load("host_groups"), _load("designations")
    out = hg.consolidate(_frame(), names.PRIORITY)
    # 2 arcsec around the disc knot: the host centre is ~10 arcsec away
    cut = names.annotate(out, pd.DataFrame(), center=(188.4170, 9.1770), radius_arcmin=2 / 60)
    assert set(cut.object_id) == {"K", "H"}


def test_ps1_rows_on_a_small_galaxy_are_grouped_under_it():
    """2.34.0: PS1 duplicates/fragments of an extended LS galaxy become its
    components; separate sources (other LS/Gaia/SDSS detection, much brighter,
    outside 2 half-light radii, point-source host) stay independent."""
    hg = _load("host_groups")
    LS, PS1 = hg.LS, hg.PS1
    arc = 1 / 3600.0
    objs = [
        # host galaxy (LS EXP, r_e = 1.0") and a point-source LS object
        dict(object_id="G", catalogs=f"{LS}|{PS1}", desi_legacy_surveys_dr10__type="EXP",
             desi_legacy_surveys_dr10__shape_r=1.0, std_mag__ls_r=20.0, designation="G1"),
        dict(object_id="P", catalogs=LS, desi_legacy_surveys_dr10__type="PSF", desi_legacy_surveys_dr10__shape_r=0.0,
             std_mag__ls_r=21.0, designation="P1"),
        dict(object_id="A", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=20.2),  # whole-galaxy duplicate
        dict(object_id="B", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=22.0),  # faint knot
        dict(object_id="C", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=21.0),  # on the other LS source
        dict(object_id="D", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=21.0),  # Gaia star there
        dict(object_id="E", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=18.0),  # 2 mag brighter
        dict(object_id="F", catalogs=PS1, pan_starrs1_dr2_meanobject__rMeanKronMag=21.0),  # 3" away
        dict(object_id="S", catalogs="Gaia DR3"),
        # PS1+SDSS object at the centre; its SDSS source is the only one on the galaxy
        dict(object_id="H", catalogs=f"{PS1}|SDSS DR18 PhotoObj", pan_starrs1_dr2_meanobject__rMeanKronMag=20.1),
    ]
    out = pd.DataFrame(objs)
    out["unknown_reason"] = ""
    rows = [
        (LS, "G", 10.0, 0.0), (PS1, "G", 10.0, 0.0), (LS, "P", 10.0, 1.5 * arc),
        (PS1, "A", 10.0 + 0.6 * arc, 0.0), (PS1, "B", 10.0, -1.2 * arc), (PS1, "C", 10.0, 1.4 * arc),
        (PS1, "D", 10.0 - 0.8 * arc, 0.0), ("Gaia DR3", "S", 10.0 - 0.9 * arc, 0.0),
        (PS1, "E", 10.0, 0.5 * arc), (PS1, "F", 10.0 + 3.0 * arc, 0.0),
        (PS1, "H", 10.0, -0.3 * arc), ("SDSS DR18 PhotoObj", "H", 10.0, -0.3 * arc),
    ]
    assoc = pd.DataFrame(rows, columns=["catalog", "object_id", "ra", "dec"])
    res = hg.attach_ps1_fragments(out, assoc).set_index("object_id")
    assert res.at["A", "parent_object_id"] == "G" and res.at["A", "component_role"] == "ps1_duplicate"
    assert res.at["B", "parent_object_id"] == "G" and res.at["B", "component_role"] == "component"
    assert "G1" in res.at["B", "unknown_reason"]
    for k in "CDEF":
        assert pd.isna(res.at[k, "parent_object_id"]), k
    assert res.at["H", "parent_object_id"] == "G"  # SDSS's own measurement of the galaxy
    assert res.at["G", "n_components"] == 3


def test_single_survey_rows_in_a_bright_star_halo_are_grouped_under_the_star():
    import pandas as pd

    import host_groups

    star = dict(object_id="S", designation="Gaia DR3 1", ra=150.0, dec=2.0, primary_class="STAR",
                gaia_dr3__phot_g_mean_mag=11.0, catalogs="DESI Legacy Surveys DR10|Gaia DR3|Pan-STARRS1 DR2 MeanObject")
    rows = [
        star,
        # PS1-only row 5" away (R/2 = 20" at G = 11): halo artefact
        dict(object_id="P", ra=150.0 + 5 / 3600, dec=2.0, primary_class="GALAXY", catalogs="Pan-STARRS1 DR2 MeanObject"),
        # a real neighbour measured by LS too: stays independent
        dict(object_id="L", ra=150.0, dec=2.0 + 6 / 3600, primary_class="GALAXY",
             catalogs="DESI Legacy Surveys DR10|Pan-STARRS1 DR2 MeanObject"),
        # PS1-only row beyond the halo radius: stays
        dict(object_id="F", ra=150.0, dec=2.0 + 40 / 3600, primary_class="UNKNOWN", catalogs="Pan-STARRS1 DR2 MeanObject"),
    ]
    out = host_groups.attach_bright_star_artifacts(pd.DataFrame(rows).assign(unknown_reason=None, parent_object_id=None))
    got = out.set_index("object_id")
    assert got.at["P", "parent_object_id"] == "S" and got.at["P", "component_role"] == "bright_star_halo"
    assert got.parent_object_id.isna()[["S", "L", "F"]].all()
    assert got.at["S", "n_components"] == 1

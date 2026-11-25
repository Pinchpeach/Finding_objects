"""Fragments and duplicate rows of small galaxies (host_groups, 2.41.0)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2))
import host_groups as hg  # noqa: E402

LS, PS1, WISE, GAIA = "DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject", "AllWISE", "Gaia DR3"


def _field():
    a = 1 / 3600
    rows = [
        # galaxy r = 18, r_e = 3"
        dict(object_id="G", ra=150.0, dec=2.0, catalogs=LS, t="SER", re=3.0, r=18.0, cls="GALAXY"),
        # faint LS source that took the galaxy's PS1 + AllWISE rows -> fragment
        dict(object_id="F", ra=150.0 + 1.5 * a, dec=2.0, catalogs=f"{WISE}|{LS}|{PS1}", t="PSF", re=0, r=22.0, cls="STAR"),
        # faint LS neighbour with nothing extra -> separate
        dict(object_id="N", ra=150.0, dec=2.0 + 2 * a, catalogs=LS, t="PSF", re=0, r=23.0, cls="GALAXY"),
        # AllWISE-only row on the galaxy -> duplicate row
        dict(object_id="W", ra=150.0 - 0.6 * a, dec=2.0, catalogs=WISE, t="", re=np.nan, r=np.nan, cls="UNKNOWN"),
        # bright LS source taking rows but < 2 mag fainter -> separate
        dict(object_id="B", ra=150.0, dec=2.0 - 2 * a, catalogs=f"{LS}|{PS1}", t="PSF", re=0, r=19.0, cls="STAR"),
        # Gaia star with significant proper motion -> separate
        dict(object_id="S", ra=150.0 + 1 * a, dec=2.0 + 1 * a, catalogs=f"{GAIA}|{PS1}", t="", re=np.nan, r=np.nan, cls="STAR",
             pmra=12.0, pmra_error=0.5, pmdec=0.0, pmdec_error=0.5, parallax=1.0, parallax_error=0.5),
        # AllWISE-only row far outside r_e -> separate
        dict(object_id="X", ra=150.0 + 10 * a, dec=2.0, catalogs=WISE, t="", re=np.nan, r=np.nan, cls="UNKNOWN"),
    ]
    d = pd.DataFrame(rows).rename(
        columns={"t": "desi_legacy_surveys_dr10__type", "re": "desi_legacy_surveys_dr10__shape_r", "r": "std_mag__ls_r", "cls": "primary_class"}
    )
    for c in ("pmra", "pmra_error", "pmdec", "pmdec_error", "parallax", "parallax_error"):
        d[f"gaia_dr3__{c}"] = d.pop(c)
    d["parent_object_id"] = np.nan
    return d


def test_fragments_and_unconfirmed_rows_join_the_galaxy():
    out = hg.attach_galaxy_fragments(_field()).set_index("object_id")
    assert out.loc["F", "parent_object_id"] == "G" and out.loc["F", "component_role"] == "fragment"
    assert out.loc["W", "parent_object_id"] == "G"
    for o in ("G", "N", "B", "S", "X"):
        assert pd.isna(out.loc[o, "parent_object_id"]), o
    assert out.loc["G", "n_components"] == 2


def test_no_galaxy_class_no_host():
    d = _field()
    d.loc[d.object_id.eq("G"), "primary_class"] = "STAR"
    assert hg.attach_galaxy_fragments(d).parent_object_id.isna().all()


# ------------------------------------------------------------------------------------------ 2.60.9 tuning switches
def _pair_of_hosts():
    """A bright extended galaxy and, 0.3'' away, a fainter extended galaxy that took the AllWISE and PS1 rows (the
    two Tractor models of one source that the 2.60.9 COSMOS2020 measurement found most often)."""
    a = 1 / 3600
    d = _field().iloc[:1].copy()  # G: galaxy r = 18, r_e = 3''
    d["object_id"] = "H"
    d["std_mag__ls_r"] = 20.0
    d["desi_legacy_surveys_dr10__shape_r"] = 0.5
    e = d.copy()
    e["object_id"] = "K"  # fainter by 3 mag, extended and a GALAXY itself, carries the extra survey rows
    e["ra"] = 150.0 + 0.3 * a
    e["std_mag__ls_r"] = 23.0
    e["desi_legacy_surveys_dr10__shape_r"] = 0.4
    e["catalogs"] = f"{WISE}|{LS}|{PS1}"
    out = pd.concat([d, e], ignore_index=True)
    out["parent_object_id"] = np.nan
    return out


def test_defaults_are_the_2_41_0_values():
    assert hg.FRAG_RADII == 1.0 and hg.FRAG_MIN_ARCSEC == 1.0 and hg.FRAG_FAINTER_MAG == 2.0
    assert hg.FRAG_HOST_AS_CANDIDATE is False and hg.HALO_FRACTION == 0.5
    assert hg.halo_radius_arcsec(14.0, True) == max(0.5 * 1630.0 * 1.396**-14.0, hg.HALO_MIN_ARCSEC)  # unchanged


def test_two_hosts_stay_apart_unless_the_host_candidate_switch_is_on(monkeypatch):
    assert hg.attach_galaxy_fragments(_pair_of_hosts()).parent_object_id.isna().all()
    monkeypatch.setattr(hg, "FRAG_HOST_AS_CANDIDATE", True)
    out = hg.attach_galaxy_fragments(_pair_of_hosts()).set_index("object_id")
    assert out.loc["K", "parent_object_id"] == "H" and out.loc["K", "component_role"] == "fragment"
    assert pd.isna(out.loc["H", "parent_object_id"]) and out.loc["H", "n_components"] == 1


def _chain_rows():
    """I2 (faint, LS|SDSS) sits 0.7'' from H1; H1 (r = 21, extended, LS|PS1) sits 2.5'' from H0 (r = 18, r_e = 3'').
    I2 is 3.2'' from H0, outside its r_e (2.60.9 review: this made I2 -> H1 -> H0 in one row order)."""
    a = 1 / 3600
    sdss = "SDSS DR18 PhotoObj"

    def row(oid, dra, r, re, cats, t="SER", cls="GALAXY"):
        return dict(object_id=oid, ra=150 + dra * a, dec=2.0, catalogs=cats, desi_legacy_surveys_dr10__type=t,
                    desi_legacy_surveys_dr10__shape_r=re, std_mag__ls_r=r, primary_class=cls, parent_object_id=np.nan)  # fmt: skip

    return [
        row("I2", 3.2, 24.0, 0.0, f"{LS}|{sdss}", t="PSF", cls="STAR"),
        row("H1", 2.5, 21.0, 0.8, f"{LS}|{PS1}"),
        row("H0", 0.0, 18.0, 3.0, LS),
    ]


def test_host_candidate_makes_no_chain_and_does_not_depend_on_row_order(monkeypatch):
    monkeypatch.setattr(hg, "FRAG_HOST_AS_CANDIDATE", True)
    seen = []
    for rows in (_chain_rows(), _chain_rows()[::-1]):
        out = hg.attach_galaxy_fragments(pd.DataFrame(rows)).set_index("object_id")
        parents = out.parent_object_id.dropna()
        assert not parents.isin(parents.index).any(), "a fragment is the parent of another fragment"
        assert out.loc["H1", "parent_object_id"] == "H0" and pd.isna(out.loc["I2", "parent_object_id"])
        assert out.loc["H0", "n_components"] == 1 and out.loc["H1", "n_components"] == 0
        seen.append(parents.sort_index().to_dict())
    assert seen[0] == seen[1]  # the same grouping in both row orders


def test_without_the_switch_the_chain_rows_group_as_in_2_41_0():
    for rows in (_chain_rows(), _chain_rows()[::-1]):
        out = hg.attach_galaxy_fragments(pd.DataFrame(rows)).set_index("object_id")
        assert out.parent_object_id.dropna().to_dict() == {"I2": "H1"}  # the default path is unchanged


def test_switch_values_are_checked(monkeypatch):
    for bad in ("nan", "-1", "inf"):
        monkeypatch.setenv("V2_HALO_FRACTION", bad)
        with pytest.raises(ValueError, match="V2_HALO_FRACTION"):
            hg._env_float("V2_HALO_FRACTION", 0.5, 0.0, 2.0)
    monkeypatch.setenv("V2_HALO_FRACTION", "")
    assert hg._env_float("V2_HALO_FRACTION", 0.5, 0.0, 2.0) == 0.5  # empty: the default


def test_halo_radius_follows_the_fraction_switch(monkeypatch):
    base = hg.halo_radius_arcsec(12.0, True)
    monkeypatch.setattr(hg, "HALO_FRACTION", 1.0)
    assert abs(hg.halo_radius_arcsec(12.0, True) - 2 * base) < 1e-9  # legacypipe: MEDIUM mask = R, BRIGHT = R / 2
    assert abs(hg.halo_radius_arcsec(12.0, False) - base) < 1e-9  # outside the Legacy Surveys: half of it

"""Fragments and duplicate rows of small galaxies (host_groups, 2.41.0)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

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

"""The low-latitude QSO switches (2.61.3, ``Preprocess/lowlat_qso.py``): off by default, act only below ``V2_LOWLAT_QSO_ABSB``."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "benchmark" / "lowlat_qso"))
_spec = importlib.util.spec_from_file_location("lowlat_qso_under_test", ROOT / "lowlat_qso.py")
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)

# rotation ICRS -> Galactic, the rows of lowlat_qso.galactic_*: x towards the Centre, y towards l = 90, z the pole
_R = np.array([[-0.0548755604, -0.8734370902, -0.4838350155],
               [0.4941094279, -0.4448296300, 0.7469822445],
               [-0.8676661490, -0.1980763734, 0.4559837762]])  # fmt: skip


def eq(l_deg: float, b_deg: float) -> tuple[float, float]:
    """(ra, dec) of a Galactic position."""
    l, b = math.radians(l_deg), math.radians(b_deg)
    x = _R.T @ np.array([math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b)])
    return math.degrees(math.atan2(x[1], x[0])) % 360.0, math.degrees(math.asin(x[2]))


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("V2_LOWLAT_QSO", raising=False)
    monkeypatch.delenv("V2_LOWLAT_QSO_ABSB", raising=False)


def test_the_helper_rotation_round_trips():
    for l, b in ((0.0, 0.0), (195.0, 13.8), (120.0, -40.0), (300.0, 60.0)):
        ra, dec = eq(l, b)
        assert abs(float(LL.galactic_latitude(ra, dec)) - b) < 1e-4
    ra, dec = eq(0.0, 0.0)
    assert float(LL.galactic_centre_distance(ra, dec)) < 0.01  # arccos near 1 amplifies the 1e-10 rounding of the matrix


def test_everything_is_off_by_default():
    ra, dec = eq(150.0, 5.0)
    df = frame([dict(ra=ra, dec=dec, catalogs="AllWISE")])
    assert LL.options() == frozenset()
    assert not LL.qso_forbidden(df).any()
    assert LL.wise_rule_allowed("WISE-AGN-001", df.iloc[0], ra, dec)
    assert LL.wise_rule_allowed("WISE-AGN-R90-001", df.iloc[0], ra, dec)


def test_unknown_and_exclusive_options(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,nonsense")
    with pytest.raises(ValueError, match="unknown"):
        LL.options()
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,surveys3")
    with pytest.raises(ValueError, match="exclude"):
        LL.options()
    monkeypatch.setenv("V2_LOWLAT_QSO", " surveys2 , pm ,")
    assert LL.options() == frozenset({"surveys2", "pm"})
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "120")
    with pytest.raises(ValueError):
        LL.max_abs_b()
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "nan")
    with pytest.raises(ValueError):
        LL.max_abs_b()


def test_annotation_catalogues_are_not_surveys():
    s = pd.Series(["AllWISE", "AllWISE|NED", "AllWISE|DESI Legacy Surveys DR10", "SIMBAD|NED", "", None,
                   "AllWISE|DESI Legacy Surveys DR10|Gaia DR3"])  # fmt: skip
    assert LL.n_surveys(s).tolist() == [1, 1, 2, 0, 0, 0, 3]


@pytest.mark.parametrize("opt,need", [("surveys2", 2), ("surveys3", 3)])
def test_survey_count_limit_acts_at_low_latitude_only(monkeypatch, opt, need):
    monkeypatch.setenv("V2_LOWLAT_QSO", opt)
    cats = ["AllWISE", "AllWISE|DESI Legacy Surveys DR10", "AllWISE|DESI Legacy Surveys DR10|Gaia DR3"]
    lo, hi = eq(150.0, 8.0), eq(150.0, 45.0)
    df = frame([dict(ra=lo[0], dec=lo[1], catalogs=c) for c in cats] + [dict(ra=hi[0], dec=hi[1], catalogs=c) for c in cats])
    got = LL.qso_forbidden(df).tolist()
    assert got[:3] == [n < need for n in (1, 2, 3)]
    assert got[3:] == [False, False, False], "the switches leave high latitude alone"


def test_latitude_limit_follows_the_environment(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2")
    ra, dec = eq(200.0, 12.0)
    df = frame([dict(ra=ra, dec=dec, catalogs="AllWISE")])
    assert LL.qso_forbidden(df).tolist() == [True]  # 12 < 20 (default)
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "10")
    assert LL.qso_forbidden(df).tolist() == [False]
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "15")
    assert LL.qso_forbidden(df).tolist() == [True]
    # the north and the south of the plane alike
    ra2, dec2 = eq(200.0, -12.0)
    assert LL.qso_forbidden(frame([dict(ra=ra2, dec=dec2, catalogs="AllWISE")])).tolist() == [True]


def test_missing_position_or_catalogue_column_is_left_alone(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,pm")
    df = frame([dict(ra=np.nan, dec=np.nan, catalogs="AllWISE"), dict(ra="x", dec="y", catalogs="AllWISE")])
    assert LL.qso_forbidden(df).tolist() == [False, False]
    assert LL.qso_forbidden(frame([dict(ra=150.0, dec=2.0)])).tolist() == [False]
    assert len(LL.qso_forbidden(frame([]))) == 0
    ra, dec = eq(200.0, 5.0)
    # no catalogue column: the object counts 0 surveys, so it is held back (fail closed at low latitude)
    assert LL.qso_forbidden(frame([dict(ra=ra, dec=dec)])).tolist() == [True]


def _gaia(**kw):
    base = dict(gaia_dr3__pmra=0.0, gaia_dr3__pmdec=0.0, gaia_dr3__pmra_error=0.1, gaia_dr3__pmdec_error=0.1,
                gaia_dr3__pmra_pmdec_corr=0.0, gaia_dr3__phot_g_mean_mag=18.0)  # fmt: skip
    base.update(kw)
    return base


def test_proper_motion_density_matches_fu_2021_eq10():
    f = LL.log10_fpm0(frame([_gaia()]))[0]
    sx = math.sqrt((1.08 * 0.1) ** 2 + 0.066**2)
    assert f == pytest.approx(-math.log10(2 * math.pi * sx * sx), abs=1e-9)
    # a bright star (G < 13) takes the smaller intrinsic scatter, which makes the density at zero larger
    assert LL.log10_fpm0(frame([_gaia(gaia_dr3__phot_g_mean_mag=11.0)]))[0] > f
    # the density falls with the proper motion: 1 mas/yr at 0.1 mas/yr errors is far outside
    assert LL.log10_fpm0(frame([_gaia(gaia_dr3__pmra=1.0)]))[0] < LL.PM_LOG10_CUT
    # no Gaia columns, no value
    assert math.isnan(LL.log10_fpm0(frame([dict(ra=1.0)]))[0])


def test_proper_motion_switch(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "pm")
    ra, dec = eq(200.0, 8.0)
    hra, hdec = eq(200.0, 50.0)
    still = dict(ra=ra, dec=dec, catalogs="Gaia DR3|AllWISE", **_gaia())
    moving = dict(ra=ra, dec=dec, catalogs="Gaia DR3|AllWISE", **_gaia(gaia_dr3__pmra=3.0, gaia_dr3__pmdec=-2.0))
    no_gaia = dict(ra=ra, dec=dec, catalogs="AllWISE")
    high_moving = dict(ra=hra, dec=hdec, catalogs="Gaia DR3|AllWISE", **_gaia(gaia_dr3__pmra=3.0, gaia_dr3__pmdec=-2.0))
    df = frame([still, moving, no_gaia, high_moving])
    assert LL.qso_forbidden(df).tolist() == [False, True, False, False]


def test_second_survey_for_the_wise_rules(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "wise_second")
    lo, hi = eq(200.0, 8.0), eq(200.0, 50.0)
    for rid in ("WISE-AGN-001", "WISE-AGN-R90-001"):
        allwise_only = pd.Series(dict(catalogs="AllWISE"))
        with_ls = pd.Series(dict(catalogs="AllWISE|DESI Legacy Surveys DR10"))
        annotated = pd.Series(dict(catalogs="AllWISE|NED|SIMBAD"))
        assert not LL.wise_rule_allowed(rid, allwise_only, *lo)
        assert LL.wise_rule_allowed(rid, with_ls, *lo)
        assert not LL.wise_rule_allowed(rid, annotated, *lo), "an annotation catalogue is no second survey"
        assert LL.wise_rule_allowed(rid, allwise_only, *hi), "high latitude is left alone"
    assert LL.wise_rule_allowed("WISE-AGN-001", pd.Series(dict(catalogs="AllWISE")), None, None)


def test_footprint_for_the_stern_rule_only(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "wise_footprint")
    row = pd.Series(dict(catalogs="AllWISE|DESI Legacy Surveys DR10"))
    plane = eq(100.0, 4.0)  # |b| < 10
    near_centre = eq(10.0, 15.0)  # |b| > 10 but within 30 deg of the Centre
    open_sky = eq(150.0, 25.0)
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *plane)
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *near_centre)
    assert LL.wise_rule_allowed("WISE-AGN-001", row, *open_sky)
    # R90 has its own footprint check in 04_build_evidence: this switch leaves it alone
    assert LL.wise_rule_allowed("WISE-AGN-R90-001", row, *plane)


def test_region_bootstrap_density():
    import ab_variants as AB  # noqa: E402

    reg = pd.DataFrame(dict(name=list("abcd"), area_deg2=[0.1, 0.1, 0.1, 0.1], all=[0, 0, 0, 8]))
    est, lo, hi = AB.boot_density(reg, "all")
    assert est == pytest.approx(8 / 0.4)
    assert lo < est < hi
    assert lo >= 0.0 and hi <= 80.0  # all in one region of four: the interval is wide, not Poisson-narrow
    assert hi - lo > 40.0
    # deterministic
    assert AB.boot_density(reg, "all") == (est, lo, hi)

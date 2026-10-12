"""Survey position errors and the R90 sky mask follow the literature (2.16.0)."""
import importlib.util
import math
import sys
from pathlib import Path

PRE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRE))
import association_model as am  # noqa: E402


def _stage4():
    s = importlib.util.spec_from_file_location("s4", PRE / "04_build_evidence.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_chandra_r0_is_95_percent_radius():
    # r0 = 2.448 sigma for a 2-D Gaussian, plus the 0.16" systematic.
    assert math.isclose(am.infer_poserr_arcsec("Chandra CSC 2.0", {"r0": 2.448}), math.hypot(1.0, 0.16))


def test_legacy_surveys_ivar_and_profile():
    sigma_deg = 0.05 / 3600.0
    row = {"ra_ivar": 1 / sigma_deg ** 2, "dec_ivar": 1 / sigma_deg ** 2, "dec": 0.0}
    assert math.isclose(am.infer_poserr_arcsec("DESI Legacy Surveys DR10", row), 0.05, rel_tol=1e-9)
    assert am.infer_psf_arcsec("DESI Legacy Surveys DR10", {}) == 1.2
    assert am.infer_psf_arcsec("Pan-STARRS1 DR2 MeanObject", {}) == 1.2


def test_erass_and_ps1_epoch():
    assert am.infer_poserr_arcsec("eROSITA eRASS1", {"POS_ERR": 3.0}) == 3.0
    assert am.infer_poserr_arcsec("eROSITA eRASS1", {}) == 4.5
    # epochMean is an MJD: 55197 = 2010.0
    assert abs(am.infer_epoch("Pan-STARRS1 DR2 MeanObject", {"epochMean": 55197.0}) - 2010.0) < 0.01


def test_r90_sky_mask():
    m = _stage4()
    assert not m._r90_sky(266.405, -28.936)   # Galactic Centre
    assert not m._r90_sky(83.63, 22.01)       # Crab, b = -5.8
    assert m._r90_sky(150.1, 2.2)             # COSMOS
    assert m._r90_sky(None, None)

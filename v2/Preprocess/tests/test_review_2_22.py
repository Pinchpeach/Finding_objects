"""2.22.0 review fixes: extended Gaia sources and the decisive-motion rule."""

import importlib.util
from pathlib import Path

PRE = Path(__file__).resolve().parents[1]


def _load(name, file):
    s = importlib.util.spec_from_file_location(name, PRE / file)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


S4 = _load("s4_review", "04_build_evidence.py")
S5 = _load("s5_review", "05_likelihood_vectors.py")


def test_cstar_sigma_point_vs_extended():
    # isolated point source: C close to f(BP-RP) -> ~0 sigma
    g, x = 15.0, 1.0
    f = 1.162004 + 0.011464 * x + 0.049255 * x * x - 0.005879 * x**3
    assert S4.cstar_sigma({"phot_bp_rp_excess_factor": f, "bp_rp": x, "phot_g_mean_mag": g}) < 0.1
    # galaxy nucleus: flux excess well above a point source
    assert S4.cstar_sigma({"phot_bp_rp_excess_factor": f + 0.5, "bp_rp": x, "phot_g_mean_mag": 19.0}) > 5
    assert S4.cstar_sigma({"bp_rp": x}) is None


def _motion(cs=None):
    e = {"rule_id": "AST-GAL-002", "raw_score": 0.74, "value": 14.0, "reliability": 1.0, "association_reliability": 1.0}
    if cs is not None:
        e["cstar_sigma"] = cs
    return [e]


def test_extended_source_motion_is_not_decisive():
    assert S5._decisive_motion(_motion()) and S5._gaia_foreground_star(_motion())  # unmeasured: as before
    assert S5._decisive_motion(_motion(1.2)) and S5._gaia_foreground_star(_motion(1.2))  # point-like star
    assert not S5._decisive_motion(_motion(15.4)) and not S5._gaia_foreground_star(_motion(15.4))  # NGC 4522 nucleus

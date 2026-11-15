"""Documented survey edges: queries skipped outside them (2.54.0)."""

import sys
from pathlib import Path

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import controller  # noqa: E402
import footprint  # noqa: E402


def test_galactic_matches_reference_points():
    l, b = footprint.galactic(266.40499, -28.93617)  # Galactic centre (l, b) = (0, 0)
    assert abs(((l + 180) % 360) - 180) < 1e-3 and abs(b) < 1e-3
    l, b = footprint.galactic(266.41684, -29.00781)  # Sgr A*: l = 359.944, b = -0.046
    assert abs(((l - 359.944 + 180) % 360) - 180) < 0.01 and abs(b + 0.046) < 0.01
    l, b = footprint.galactic(192.85948, 27.12825)  # north Galactic pole
    assert abs(b - 90) < 1e-4


def test_declination_edge_keeps_a_margin():
    nvss = {"dec_min": -40.0}
    assert footprint.outside(nvss, 10.0, -60.0, 2.0)
    assert not footprint.outside(nvss, 10.0, -40.5, 2.0)  # within the 1 deg margin: queried
    assert not footprint.outside(nvss, 10.0, -38.0, 30.0)
    assert not footprint.outside(None, 10.0, -89.0, 1.0)


def test_erosita_de_half_sky():
    ero = {"gal_l_range": (179.9442, 359.9442)}
    assert footprint.outside(ero, 283.3044, -3.5206, 1.0)  # l = 30, b = -2
    assert not footprint.outside(ero, 150.1191, 2.2058, 2.0)  # COSMOS, l = 237
    # just across the l = 0 edge, inside the margin: queried
    ra, dec = 266.6, -28.5  # l ~ 0.4
    assert not footprint.outside(ero, ra, dec, 2.0)


def test_collectors_declare_their_edges_and_controller_skips(tmp_path):
    assert controller._load_collector("nvss").FOOTPRINT == {"dec_min": -40.0}
    assert controller._load_collector("tgss").FOOTPRINT == {"dec_min": -53.0}
    r = controller._collect_one("vlass", 0.0, -70.0, 2.0, tmp_path, "t")
    assert r["status"] == "outside_footprint" and r["rows"] == 0 and r["error"] == ""
    assert not list(tmp_path.glob("*.csv"))

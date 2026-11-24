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


# ---------------------------------------------------- DESI DR1 tiles (2.59.0)
def test_desi_collectors_declare_the_tile_footprint():
    for name in ("desi_spectroscopy", "desi_fastspec"):
        fp = controller._load_collector(name).FOOTPRINT
        assert fp == {"tiles": "desi_dr1_tiles.csv.gz", "tile_radius_deg": 1.7}


def test_tile_footprint_skips_the_galactic_plane_but_keeps_desi_fields_and_edges():
    fp = {"tiles": "desi_dr1_tiles.csv.gz", "tile_radius_deg": 1.7}
    assert not footprint.outside(fp, 150.10, 2.25, 2.0)  # COSMOS: a DR1 tile is on it
    assert not footprint.outside(fp, 188.4155, 9.1751, 2.0)  # NGC 4522: 1.1 deg from a tile centre
    assert footprint.outside(fp, 283.80, -2.10, 1.0)  # 11 deg from every tile
    assert footprint.outside(fp, 283.3044, -3.5206, 1.0)
    assert footprint.tile_gap_deg("desi_dr1_tiles.csv.gz", 150.12, 2.206) < 0.1
    # a cone whose edge is within tile radius + margin of a tile is asked: a 3 deg cone 5 deg from the tiles is not skipped
    gap = footprint.tile_gap_deg("desi_dr1_tiles.csv.gz", 283.80, -2.10)
    assert footprint.outside(fp, 283.80, -2.10, 60.0 * (gap - 1.7 - footprint.MARGIN_DEG - 1.0))
    assert not footprint.outside(fp, 283.80, -2.10, 60.0 * (gap - 1.7 - footprint.MARGIN_DEG + 1.0))


def test_every_stored_desi_object_lies_inside_the_tile_radius():
    """The 1.7 deg radius: 162,821 DESI objects stored in benchmark/ lie within 1.622 deg of a tile centre (2026-11-23).
    This keeps the assumption checked on the 4,795 external-benchmark objects, so a different tile file cannot
    silently cut the footprint."""
    import numpy as np
    import pandas as pd

    d = pd.read_csv(GET.parent / "benchmark" / "desi_external" / "truth.csv", usecols=["ra", "dec"]).dropna()
    gaps = [footprint.tile_gap_deg("desi_dr1_tiles.csv.gz", r, x) for r, x in zip(d.ra[::10], d.dec[::10])]
    assert max(gaps) < 1.7 and np.isfinite(gaps).all()


def test_controller_asks_no_desi_archive_outside_the_footprint(tmp_path):
    for name in ("desi_spectroscopy", "desi_fastspec"):
        r = controller._collect_one(name, 283.80, -2.10, 1.0, tmp_path, "t")
        assert r["status"] == "outside_footprint" and r["rows"] == 0 and r["error"] == ""
    assert not list(tmp_path.glob("*.csv"))


# --- 2.60.2: LoTSS DR2 (dec_min), FIRST (boxes), MYStIX (regions): a search outside them asks nothing
COSMOS, NGC4522, PLANE_L30 = (150.10, 2.25), (188.4155, 9.1751), (283.80, -2.10)


def test_lotss_is_skipped_south_of_its_coverage_only():
    import lotss

    for ra, dec in (COSMOS, NGC4522, PLANE_L30):
        assert footprint.outside(lotss.FOOTPRINT, ra, dec, 2.0)
    assert footprint.outside(lotss.FOOTPRINT, 200.0, 14.5, 2.0)  # the lowest covered cell centre is at +16.26
    assert not footprint.outside(lotss.FOOTPRINT, 200.0, 16.0, 2.0)
    assert not footprint.outside(lotss.FOOTPRINT, 150.0, 40.0, 2.0)
    assert not footprint.outside(lotss.FOOTPRINT, 1.0, 20.0, 2.0)  # the RA-1 region


def test_first_is_skipped_outside_the_boxes_of_its_coverage_maps():
    import first

    assert not footprint.outside(first.FOOTPRINT, *COSMOS, 2.0) and not footprint.outside(
        first.FOOTPRINT, *NGC4522, 2.0
    )
    assert footprint.outside(first.FOOTPRINT, *PLANE_L30, 1.0)  # RA 283.8 is in neither cap
    assert footprint.outside(first.FOOTPRINT, 270.0, 10.0, 2.0)  # 3.5 deg east of the north cap
    assert not footprint.outside(first.FOOTPRINT, 267.0, 10.0, 2.0)  # inside the margin of its edge
    assert not footprint.outside(first.FOOTPRINT, 10.0, 0.0, 2.0)  # the south cap wraps through RA = 0
    assert footprint.outside(first.FOOTPRINT, 150.0, 80.0, 2.0)  # north of the covered declinations
    assert footprint.outside(first.FOOTPRINT, 150.0, -30.0, 2.0)


def test_mystix_is_skipped_away_from_its_20_regions():
    import mystix_mpcm

    fp = mystix_mpcm.FOOTPRINT
    assert len(fp["regions"]) == 20
    for ra, dec in (COSMOS, NGC4522, PLANE_L30):
        assert footprint.outside(fp, ra, dec, 2.0)
    assert not footprint.outside(fp, 83.82, -5.39, 2.0)  # the Orion Nebula
    assert not footprint.outside(fp, 97.92, 6.4, 6.0)  # 1.4 deg north of the Rosette centre, radius 1.5
    assert footprint.outside(fp, 97.92, 9.0, 2.0)

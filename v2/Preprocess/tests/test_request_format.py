"""Archive requests: pacing and coordinate text (2.33.0)."""

import sys
from pathlib import Path

import pytest

GET_DATA = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET_DATA))
import throttle  # noqa: E402


def test_every_request_pauses_once(monkeypatch):
    requests = pytest.importorskip("requests")
    slept = []
    monkeypatch.setattr(throttle.time, "sleep", slept.append)
    throttle.install()
    throttle.install()  # idempotent: one wrapper, one pause per request

    class Offline(requests.adapters.BaseAdapter):
        def send(self, request, **kw):
            r = requests.Response()
            r.status_code, r.url, r._content = 200, request.url, b"ok"
            return r

        def close(self):
            pass

    s = requests.Session()
    s.mount("https://", Offline())
    assert s.get("https://a.example/x").text == "ok" and s.get("https://b.example/y").text == "ok"
    assert len(slept) == 2 and all(throttle.MIN_PAUSE_S <= x <= throttle.MAX_PAUSE_S for x in slept)


def test_nested_layers_pause_once(monkeypatch):
    slept = []
    monkeypatch.setattr(throttle.time, "sleep", slept.append)
    inner = throttle._paced(lambda: "sent")
    outer = throttle._paced(lambda: inner())
    assert outer() == "sent"
    assert len(slept) == 1


def _load(name):
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"t_{name}", GET_DATA / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize(
    "ra,dec,ra_hours,dec_deg",
    [(20.0, 0.0, 1.3333, 0.0), (0.0, 10.0, 0.0, 10.0), (245.0, 43.0, 16.3333, 43.0)],
)
def test_ned_centre_is_fixed_point(monkeypatch, ra, dec, ra_hours, dec_deg):
    pytest.importorskip("astroquery")
    from astroquery.query import BaseQuery
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    seen = {}

    def fake(self, method, url, params=None, **kw):
        seen.update(params)
        raise RuntimeError("no network")

    monkeypatch.setattr(BaseQuery, "_request", fake)
    with pytest.raises(RuntimeError):
        _load("ned")._ned().query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=2 * u.arcmin)
    # Field RA 20, Dec 0 was sent as lat=4.847e-07, which NED read as Dec +4.85.
    assert "e" not in seen["lon"].lower() and "e" not in seen["lat"].lower()
    assert float(seen["lon"]) == pytest.approx(ra_hours, abs=1e-4)
    assert float(seen["lat"]) == pytest.approx(dec_deg, abs=1e-4)


def test_sdss_rectangle_keeps_full_precision():
    pytest.importorskip("astroquery")
    import _catalog_utils as cu

    sql = cu._sdss()._rectangle_sql(245.0667, 43.0, 0.18, height=0.13)
    assert "244.97670000" in sql and "245.15670000" in sql  # astroquery wrote 244.977 / 245.157
    wrapped = cu._sdss()._rectangle_sql(359.95, -0.0667, 0.2, height=0.1333)
    assert "(p.ra >= 359.85000000) OR (p.ra <= 0.05000000)" in wrapped
    assert "-0.00005000" in wrapped and "e-" not in wrapped


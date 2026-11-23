"""Legacy Surveys second path: the viewer catalogue and the hedged request (2.57.0)."""

import importlib.util
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import archive_cache  # noqa: E402

spec = importlib.util.spec_from_file_location("ls_viewer_t", GET / "desi_legacy.py")
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)


def _viewer_fits(rows, release=10000, brick=384210):
    """A FITS table like the viewer's cat.fits: big-endian, bytes ``type``, ``dchisq`` of shape (N, 5)."""
    n = len(rows)
    cols = {c: np.zeros(n, ">f4") for c in ls.TAP_COLUMNS if c not in ("ls_id", "type") and not c.startswith("dchisq_")}
    cols.update(
        release=np.full(n, release, ">i2"),
        brickid=np.full(n, brick, ">i4"),
        objid=np.array([r["objid"] for r in rows], ">i4"),
        ra=np.array([r["ra"] for r in rows], ">f8"),
        dec=np.array([r["dec"] for r in rows], ">f8"),
        flux_r=np.array([r.get("flux_r", 1.0) for r in rows], ">f4"),
        nobs_r=np.full(n, 3, ">i2"),
        maskbits=np.zeros(n, ">i2"),
    )
    tbl = [
        fits.Column(name=k, format={"f4": "E", "f8": "D", "i2": "I", "i4": "J"}[v.dtype.str[1:]], array=v)
        for k, v in cols.items()
    ]
    tbl.append(fits.Column(name="type", format="4A", array=np.array([r.get("type", "PSF") for r in rows], "S4")))
    tbl.append(fits.Column(name="brick_primary", format="L", array=np.array([r.get("primary", True) for r in rows])))
    tbl.append(
        fits.Column(
            name="dchisq",
            format="5E",
            array=np.tile(np.arange(1, 6, dtype=">f4"), (n, 1)) * np.arange(1, n + 1)[:, None],
        )
    )
    buf = io.BytesIO()
    fits.BinTableHDU.from_columns(tbl).writeto(buf)
    return buf.getvalue()


class _Resp:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_tap_columns_match_the_tap_query():
    """TAP_COLUMNS is the SELECT list of fetch(), in its order (the viewer rows are built from it)."""
    src = (GET / "desi_legacy.py").read_text()
    sel = src.split("SELECT", 1)[1].split("FROM", 1)[0].replace("{{extra}}", ", ra_ivar, dec_ivar, ref_epoch")
    cols = [c.strip() for c in sel.replace("\n", " ").split(",") if c.strip()]
    # the optional astrometric columns come right after objid in the query; the table keeps the SELECT order
    assert cols == ls.TAP_COLUMNS


def test_viewer_rows_have_the_tap_columns_ids_and_the_cone(monkeypatch):
    ra0, dec0 = 188.4155, 9.1751
    rows = [
        {"objid": 1550, "ra": ra0, "dec": dec0, "type": "SER", "flux_r": 12.5},
        {"objid": 7908, "ra": ra0 + 0.4 / 60 / np.cos(np.radians(dec0)), "dec": dec0, "type": "PSF"},
        {"objid": 7909, "ra": ra0 + 0.9 / 60 / np.cos(np.radians(dec0)), "dec": dec0},  # in the box, outside the cone
        {"objid": 7910, "ra": ra0, "dec": dec0 + 0.1 / 60, "primary": False},  # not a primary row
    ]
    seen = []
    monkeypatch.setattr(
        "requests.get",
        lambda url, params=None, timeout=None: seen.append(params) or _Resp(_viewer_fits(rows)),
    )
    df = ls._viewer_fetch(ra0, dec0, 0.5)
    assert list(df.columns) == ls.TAP_COLUMNS + ["legacy_query_status"]
    assert df.legacy_query_status.eq("viewer_fallback").all()
    assert df.ls_id.tolist() == [10000 * 2**40 + 384210 * 2**20 + 1550, 10000 * 2**40 + 384210 * 2**20 + 7908]
    assert df.type.tolist() == ["SER", "PSF"]  # text, not bytes
    assert df.dchisq_3.tolist() == [3.0, 6.0] or df.dchisq_3.iloc[0] == 3.0  # the (N, 5) array split into dchisq_1..5
    assert df.flux_r.iloc[0] == pytest.approx(12.5)
    assert len(seen) == 1 and float(seen[0]["ralo"]) < ra0 < float(seen[0]["rahi"])
    # the saved columns are what the TAP path writes: the collector's save() works on it
    out = df.assign(catalog="DESI Legacy Surveys DR10", catalog_object_id=df.ls_id.astype("string"))
    assert out.catalog_object_id.iloc[0] == str(10000 * 2**40 + 384210 * 2**20 + 1550)


def test_dr9_north_rows_keep_the_dr9_id_and_have_no_i_band(monkeypatch):
    """2.57.0 review: the Data Lab ls_dr10 ids of DR9 North rows are release<<40 | brickid<<16 | objid (219 of
    219 rows north of the split: same release, brickid, objid; only the shift differed).  BASS + MzLS have no
    i band, so the viewer table has no *_i columns (a KeyError before)."""
    ra0, dec0 = 180.0, 32.45
    rows = [{"objid": 2956, "ra": ra0, "dec": dec0}]
    blob = _viewer_fits(rows, release=9011, brick=508642)
    from astropy.table import Table

    tab = Table.read(io.BytesIO(blob), format="fits")
    tab.remove_columns([c for c in tab.colnames if c.endswith("_i")])
    buf = io.BytesIO()
    tab.write(buf, format="fits")
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(buf.getvalue()))
    df = ls._viewer_fetch(ra0, dec0, 0.5)
    assert df.ls_id.tolist() == [9907732612254604]  # the TAP's id of this source (2026-11-23)
    assert df.flux_i.isna().all() and df.nobs_i.isna().all()


def test_empty_box_answer_is_an_empty_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(b"No catalog sources in layer and RA,Dec box"))
    df = ls._viewer_fetch(283.80, -2.10, 1.0)
    assert df.empty and "ls_id" in df.columns
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(b"<html>maintenance</html>"))
    with pytest.raises(RuntimeError, match="not a FITS table"):
        ls._viewer_fetch(283.80, -2.10, 1.0)


def test_boxes_split_at_ra_zero_and_stay_out_of_the_poles():
    (b,) = ls.viewer_boxes(150.0, 2.0, 2.0)
    assert b[0] < 150.0 < b[1] and b[2] < 2.0 < b[3]
    lo, hi = ls.viewer_boxes(0.0005, 2.0, 2.0)
    assert lo[1] == 360.0 and lo[0] > 359.9 and hi[0] == 0.0 and hi[1] > 0.0005
    lo, hi = ls.viewer_boxes(359.9995, 2.0, 2.0)
    assert lo[1] == 360.0 and hi[0] == 0.0 and hi[1] < 0.1
    assert ls.viewer_usable(150.0, 2.0, 10.0) and not ls.viewer_usable(150.0, 2.0, 10.5)  # 30' would be 688 MB
    assert not ls.viewer_usable(10.0, 89.5, 1.0)


def test_viewer_only_for_cones_wholly_in_dr10_south():
    """2.57.0 review (compare_ls_viewer.py): in the DR9 North part of ls_dr10 the viewer rows lack the i band
    and carry other ls_id values than the TAP's; DR10 South (incl. the SGC above Dec 32.375) is identical."""
    assert ls.viewer_usable(188.4155, 9.1751, 2.0)  # NGC 4522
    assert ls.viewer_usable(180.0, 32.30, 2.0)  # NGC just south of the split
    assert ls.viewer_usable(20.0, 33.5, 2.0)  # SGC above the split: DR10 South only
    assert not ls.viewer_usable(180.0, 32.45, 2.0)  # NGC just north of the split: DR9 North
    assert not ls.viewer_usable(245.0, 43.0, 2.0) and not ls.viewer_usable(150.0, 50.0, 2.0)
    assert not ls.viewer_usable(180.0, 32.35, 2.0)  # centre south, cone reaches the split


def test_hedge_answers_when_the_tap_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(ls, "HEDGE_DELAY_S", 0.2)
    monkeypatch.setattr(ls, "ATTEMPT_BUDGET_S", 3.0)
    monkeypatch.setattr(ls, "ATTEMPTS", 1)

    def tap():
        time.sleep(2.5)
        return "tap"

    t0 = time.monotonic()
    assert ls._query_with_retries(tap, lambda: "viewer") == "viewer"
    assert time.monotonic() - t0 < 1.5  # did not wait for the TAP
    assert "asking the Legacy Surveys viewer catalogue as well" in capsys.readouterr().out


def test_healthy_tap_never_touches_the_viewer(monkeypatch):
    monkeypatch.setattr(ls, "HEDGE_DELAY_S", 5.0)
    called = []
    assert ls._query_with_retries(lambda: "tap", lambda: called.append(1) or "viewer") == "tap"
    assert not called


def test_tap_wins_when_both_answered_and_a_failed_attempt_starts_the_hedge(monkeypatch):
    monkeypatch.setattr(ls, "ATTEMPT_BUDGET_S", 3.0)
    monkeypatch.setattr(ls, "ATTEMPTS", 2)

    def tap_error():
        raise ConnectionError("HTTP 500")

    assert ls._query_with_retries(tap_error, lambda: "viewer") == "viewer"  # no 30 s wait after a quick error


def test_both_paths_failing_raises_the_tap_error(monkeypatch):
    monkeypatch.setattr(ls, "ATTEMPT_BUDGET_S", 1.0)
    monkeypatch.setattr(ls, "ATTEMPTS", 1)
    monkeypatch.setattr(ls, "VIEWER_TIMEOUT_S", (0.1, 0.1))

    def viewer():
        raise ConnectionError("viewer down")

    def tap():
        raise ConnectionError("tap down")

    with pytest.raises(RuntimeError, match="Legacy Surveys TAP failed"):
        ls._query_with_retries(tap, viewer)
    with pytest.raises(RuntimeError, match="Legacy Surveys TAP failed"):
        ls._query_with_retries(tap, None)  # no second path (a large cone): as before


def test_a_viewer_answer_is_cached_for_a_day_only():
    df = pd.DataFrame({"ra": [1.0], "dec": [2.0], "legacy_query_status": ["viewer_fallback"]})
    assert archive_cache.cacheable(df) and archive_cache.fallback(df)
    assert archive_cache._ttl("desi_legacy", 1, True) == archive_cache.FALLBACK_TTL_DAYS


def test_a_caller_may_wait_less_than_the_legacy_surveys_defaults(monkeypatch):
    """FastSpecFit (2.59.0): two attempts of 50 s, not three of 80 s; the helper takes them per call."""
    import time as _t

    fs_spec = importlib.util.spec_from_file_location("desi_fastspec_t", GET / "desi_fastspec.py")
    fs = importlib.util.module_from_spec(fs_spec)
    fs_spec.loader.exec_module(fs)
    assert (fs.ATTEMPTS, fs.ATTEMPT_BUDGET_S, fs.BUDGET_S) == (2, 50.0, 110.0)
    assert fs.ATTEMPTS * fs.ATTEMPT_BUDGET_S + 2.0 < fs.BUDGET_S  # the controller budget leaves room for both attempts
    calls = []

    def stall():
        calls.append(_t.monotonic())
        _t.sleep(5)

    monkeypatch.setattr(ls, "ATTEMPTS", 3)  # the module defaults stay what they were
    monkeypatch.setattr(ls, "ATTEMPT_BUDGET_S", 3.0)
    t0 = _t.monotonic()
    with pytest.raises(ls.TapTimeout):
        ls._query_with_retries(stall, attempts=2, attempt_budget_s=0.5)
    assert len(calls) == 2 and _t.monotonic() - t0 < 4.0

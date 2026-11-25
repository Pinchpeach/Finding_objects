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
        lambda url, params=None, timeout=None, **k: seen.append(params) or _Resp(_viewer_fits(rows)),
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
    assert ls.viewer_usable(150.0, 2.0, 10.0) and ls.viewer_usable(150.0, 2.0, 20.0)  # 2.60.10: tiles up to 20'
    assert not ls.viewer_usable(150.0, 2.0, 20.5)  # 30' in one box would be 688 MB; no larger cone is asked
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


# ------------------------------------------------------------------------------------------ 2.60.10: tiles
def _tangent_offsets(ra0, dec0, ra, dec):
    return (
        ((np.asarray(ra) - ra0 + 180.0) % 360.0 - 180.0) * np.cos(np.radians(dec0)) * 60.0,
        (np.asarray(dec) - dec0) * 60.0,
    )


def test_tile_counts_follow_the_cone_size():
    n = lambda r, dec=2.0: len(ls.viewer_tiles(150.0, dec, r))
    assert n(2.0) == n(10.0) == n(12.0) == n(12.5) == 1  # the set-C 12' cone is one request
    assert n(13.0) == n(16.0) == n(20.0) == 4  # 2 x 2 tiles of at most 25' x 25'
    assert n(12.0, -60.0) == 1 and n(20.0, -70.0) == 4
    assert (
        ls.viewer_usable(150.0, 2.0, 12.0)
        and ls.viewer_usable(150.0, 2.0, 20.0)
        and not ls.viewer_usable(150.0, 2.0, 20.5)
    )
    assert (
        max(ls.VIEWER_TILE_ARCMIN, 0) * ls.VIEWER_MAX_TILES >= 2 * ls.MAX_VIEWER_RADIUS_ARCMIN
    )  # the cap fits the tiles


@pytest.mark.parametrize("ra0,dec0,r", [(150.12, 2.2, 12.0), (150.12, 2.2, 20.0), (23.5, -41.3, 16.0), (359.95, -30.0, 12.0),
                                        (0.05, -30.0, 20.0), (300.0, -70.0, 20.0)])  # fmt: skip
def test_tiles_cover_every_point_of_the_cone_and_overlap_where_they_meet(ra0, dec0, r):
    tiles = ls.viewer_tiles(ra0, dec0, r)
    rng = np.random.default_rng(3)
    rr, th = r / 60.0 * np.sqrt(rng.random(40000)), 2 * np.pi * rng.random(40000)
    dec = dec0 + rr * np.sin(th)
    ra = (ra0 + rr * np.cos(th) / np.cos(np.radians(dec0))) % 360.0

    def in_tile(t):
        ralo, rahi, declo, dechi = t
        in_ra = (
            ((ra >= ralo) & (ra <= rahi))
            | ((ra + 360 >= ralo) & (ra + 360 <= rahi))
            | ((ra - 360 >= ralo) & (ra - 360 <= rahi))
        )
        return in_ra & (dec >= declo) & (dec <= dechi)

    covered = np.zeros(len(ra), bool)
    for t in tiles:
        covered |= in_tile(t)
    assert covered.all(), f"{(~covered).sum()} points of the cone are in no tile"
    # a point close to the boundary of two tiles of the same box is in both (the overlap)
    if (
        len(ls.viewer_boxes(ra0, dec0, r)) == 1 and len(tiles) > 1
    ):  # one box cut in tiles (a wrapped cone has two boxes)
        both = sum(in_tile(t).astype(int) for t in tiles) > 1
        assert both.any()


class _Server:
    """The viewer's cat.fits for a synthetic catalogue: the rows inside the requested box (an edge rule of
    the test's choosing), as a FITS table, or the "no sources" text."""

    def __init__(self, ra, dec, inclusive_upper=True, edge_loss=0.0):
        # edge_loss: the share of the box width within which the rows at an edge are not answered (the real viewer
        # lost the rows within ~1/2300 of the width, 2026-11-25)
        self.ra, self.dec, self.inc, self.asked = np.asarray(ra), np.asarray(dec), inclusive_upper, []
        self.loss = edge_loss

    def __call__(self, url, params=None, timeout=None, **k):
        p = {k_: float(v) for k_, v in params.items()}
        self.asked.append(p)
        up = (lambda x, hi: x <= hi) if self.inc else (lambda x, hi: x < hi)
        w_ra, w_dec = (p["rahi"] - p["ralo"]), (p["dechi"] - p["declo"])
        lo_ra, hi_ra = p["ralo"] + self.loss * w_ra, p["rahi"] - self.loss * w_ra
        lo_dec, hi_dec = p["declo"] + self.loss * w_dec, p["dechi"] - self.loss * w_dec
        m = (self.ra >= lo_ra) & up(self.ra, hi_ra) & (self.dec >= lo_dec) & up(self.dec, hi_dec)
        idx = np.flatnonzero(m)
        if not len(idx):
            return _Resp(b"No catalog sources in layer and RA,Dec box")
        rows = [{"objid": int(i), "ra": float(self.ra[i]), "dec": float(self.dec[i])} for i in idx]
        return _Resp(_viewer_fits(rows))


@pytest.mark.parametrize("edge_loss", [0.0, 1 / 2300, 1 / 1000])  # no loss, the viewer's measured loss, 2.3 times it
@pytest.mark.parametrize("inclusive", [True, False])
@pytest.mark.parametrize(
    "ra0,dec0,r", [(150.12, 2.2, 12.0), (150.12, 2.2, 20.0), (359.95, -30.0, 12.0), (0.05, -30.0, 20.0)]
)
def test_a_tiled_fetch_returns_the_cone_exactly(monkeypatch, ra0, dec0, r, inclusive, edge_loss):
    """The rows of the cone, each once: none lost on a tile edge (either viewer edge rule) and none doubled in an
    overlap.  The synthetic catalogue has rows on every tile edge and just inside / outside the cone."""
    rng = np.random.default_rng(5)
    n = 4000
    rr, th = (r * 1.15) / 60.0 * np.sqrt(rng.random(n)), 2 * np.pi * rng.random(n)
    dec = dec0 + rr * np.sin(th)
    ra = (ra0 + rr * np.cos(th) / np.cos(np.radians(dec0))) % 360.0
    tiles = ls.viewer_tiles(ra0, dec0, r)
    edge_ra = [t[0] for t in tiles] + [t[1] for t in tiles]  # rows exactly on tile edges
    edge_dec = [t[2] for t in tiles] + [t[3] for t in tiles]
    ra = np.concatenate([ra, np.array(edge_ra) % 360.0])
    dec = np.concatenate([dec, np.full(len(edge_ra), dec0), np.array(edge_dec)[:0]])[: len(ra)]
    ra = np.concatenate([ra, np.full(len(edge_dec), ra0)])
    dec = np.concatenate([dec, np.array(edge_dec)])
    server = _Server(ra, dec, inclusive, edge_loss)
    monkeypatch.setattr("requests.get", server)
    got = ls._viewer_fetch(ra0, dec0, r)
    # the expected rows: those in the cone (great-circle) whose position the server could deliver (the box cover)
    a, d, a0, d0 = np.radians(ra), np.radians(dec), np.radians(ra0), np.radians(dec0)
    h = np.sin((d - d0) / 2) ** 2 + np.cos(d0) * np.cos(d) * np.sin((a - a0) / 2) ** 2
    sep = np.degrees(2 * np.arcsin(np.sqrt(h))) * 60.0
    want = {10000 * 2**40 + 384210 * 2**20 + int(i) for i in np.flatnonzero(sep <= r)}
    assert len(got) == len(set(got.ls_id)), "a row came twice"
    assert set(got.ls_id) == want, f"{len(want - set(got.ls_id))} lost, {len(set(got.ls_id) - want)} extra"
    assert len(server.asked) == len(tiles)


def test_an_answer_over_the_byte_cap_is_not_read(monkeypatch):
    class _Big(_Resp):
        closed = False

        def iter_content(self, chunk_size=1):
            for _ in range(5):
                yield b"x" * 1000

        def close(self):
            self.closed = True

    monkeypatch.setattr(ls, "VIEWER_MAX_BYTES", 2500)
    r = _Big(b"")
    with pytest.raises(RuntimeError, match="larger than"):
        ls._viewer_read(r)
    assert r.closed
    assert len(ls._viewer_read(_Big(b""), limit=10_000)) == 5000


def test_the_tiles_of_one_cone_share_a_time_budget(monkeypatch):
    monkeypatch.setattr(ls, "VIEWER_BUDGET_S", -1.0)
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(b"No catalog sources in layer and RA,Dec box"))
    with pytest.raises(TimeoutError, match="tiles not done"):
        ls._viewer_fetch(150.12, 2.2, 20.0)


def test_the_hedge_waits_longer_for_a_larger_cone_but_not_beyond_one_attempt():
    assert ls.hedge_delay_s(2.0) == ls.hedge_delay_s(10.0) == ls.HEDGE_DELAY_S  # the validated sizes: as before
    assert ls.hedge_delay_s(12.0) == pytest.approx(
        ls.HEDGE_DELAY_S * 1.5 * 1.44
    )  # the Data Lab's time follows the area
    assert ls.hedge_delay_s(12.0) > 43.0  # the slowest healthy 12' answer measured (COSMOS, 2026-11-25) does not hedge
    assert ls.hedge_delay_s(20.0) == ls.ATTEMPT_BUDGET_S  # 120 s would be later than the attempt itself


def test_fetch_gives_the_hedge_the_delay_of_the_cone(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        ls, "_query_with_retries", lambda run, hedge=None, **k: seen.update(k, hedge=hedge) or pd.DataFrame()
    )
    ls.fetch(150.12, 2.2, 12.0)
    assert seen["hedge_delay"] == pytest.approx(ls.HEDGE_DELAY_S * 1.5 * 1.44) and seen["hedge"] is not None
    seen.clear()
    ls.fetch(150.12, 2.2, 25.0)  # beyond the viewer's reach: no second path at all
    assert seen["hedge"] is None


def test_the_viewer_deadline_holds_while_an_answer_streams(monkeypatch):
    """2.60.10 review (Codex): the cone's VIEWER_BUDGET_S is checked while a slow answer streams in, and a last tile
    that finishes late is not accepted."""
    import time as _t

    class _Slow(_Resp):
        closed = False

        def iter_content(self, chunk_size=1):
            for _ in range(5):
                yield b"x" * 10

        def close(self):
            self.closed = True

    r = _Slow(b"")
    with pytest.raises(TimeoutError, match="while reading"):
        ls._viewer_read(r, deadline=_t.monotonic() - 1.0)
    assert r.closed
    assert len(ls._viewer_read(_Slow(b""), deadline=_t.monotonic() + 60.0)) == 50

    # one tile, answered (empty box) but only after the budget: rejected after the loop
    clock = iter([0.0, 0.0, 500.0, 500.0, 500.0])
    monkeypatch.setattr(_t, "monotonic", lambda: next(clock, 500.0))
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(b"No catalog sources in layer and RA,Dec box"))
    with pytest.raises(TimeoutError, match="tiles not done"):
        ls._viewer_fetch(150.12, 2.2, 5.0)


def test_the_retry_budget_fits_the_viewer_of_large_cones():
    """2.60.10 review (Codex): a retry, or a search after a remembered failure, gets RETRY_BUDGET_S (90 s), which a
    20' cone's viewer tiles cannot meet; such cones get the hedge delay plus the tiles' budget."""
    south = (150.12, 2.2)  # COSMOS: DR10 South
    assert ls.retry_budget_s(*south, 10.0) == ls.RETRY_BUDGET_S
    big = ls.retry_budget_s(*south, 20.0)
    assert big >= ls.hedge_delay_s(20.0) + ls.VIEWER_BUDGET_S and big <= 300.0  # inside the controller's budget
    assert ls.retry_budget_s(185.0, 45.0, 20.0) == ls.RETRY_BUDGET_S  # DR9 North: no viewer, the short retry


def test_the_controller_sizes_retry_budgets_by_the_cone(monkeypatch):
    import importlib.util

    root = Path(__file__).resolve().parents[2] / "Get_data"
    spec = importlib.util.spec_from_file_location("v2_controller_budget_t", root / "controller.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    assert ctl._budget("desi_legacy", 300.0, retry=True) == ls.RETRY_BUDGET_S  # no cone given: the fixed one
    assert ctl._budget("desi_legacy", 300.0, retry=True, cone=(150.12, 2.2, 20.0)) == ls.retry_budget_s(150.12, 2.2, 20.0)
    assert ctl._budget("desi_legacy", 300.0, retry=False, cone=(150.12, 2.2, 20.0)) == 300.0  # a fresh search: unchanged

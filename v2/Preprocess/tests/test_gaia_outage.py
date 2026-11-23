"""Gaia archive downtime: maintenance page, V2_GAIA_SOURCE, parallel VizieR copy (2.57.0)."""

import sys
import threading
import time
import types
from pathlib import Path

import pandas as pd
import pytest

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import gaia_dr3 as g  # noqa: E402

MAINTENANCE = '<html class="ltr" dir="ltr" lang="en-GB"><head><title>ESDC Archives downtime</title></head></html>'
VOSI = '<?xml version="1.0"?><vosi:availability xmlns:vosi="http://www.ivoa.net/xml/VOSIAvailability/v1.0"><vosi:available>true</vosi:available></vosi:availability>'


class _Resp:
    def __init__(self, text):
        self.text = text


def test_maintenance_page_is_recognised_by_content(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(MAINTENANCE))  # HTTP 200, as ESA answers
    assert "maintenance" in g.archive_down_reason()
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(VOSI))
    assert g.archive_down_reason() is None
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(VOSI.replace("true", "false")))
    assert "unavailable" in g.archive_down_reason()

    def boom(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "get", boom)
    assert g.archive_down_reason() is None  # unknown is not down: the ordinary retries decide


def _fake_gaia(monkeypatch, sync_error, async_calls):
    astroquery_gaia = types.ModuleType("astroquery.gaia")

    class Job:
        def get_results(self):
            raise AssertionError("not reached")

    class Gaia:
        @staticmethod
        def launch_job(q):
            raise sync_error

        @staticmethod
        def launch_job_async(q):
            async_calls.append(q)
            raise RuntimeError("HTTPError: OK")

    astroquery_gaia.Gaia = Gaia
    monkeypatch.setitem(sys.modules, "astroquery.gaia", astroquery_gaia)


def test_tap_fails_fast_during_maintenance_without_async_retries(monkeypatch):
    calls = []
    _fake_gaia(monkeypatch, ValueError("E19: File does not appear to be a VOTABLE"), calls)
    monkeypatch.setattr(g, "archive_down_reason", lambda *a, **k: "the archive answers with a maintenance page")
    t0 = time.monotonic()
    with pytest.raises(g.ArchiveDown, match="maintenance"):
        g._tap("SELECT 1", retries=4)
    assert not calls and time.monotonic() - t0 < 2  # was: 4 async attempts, 33 s
    # an archive that is up keeps its asynchronous retries (a failed sync request is not an outage)
    monkeypatch.setattr(g, "archive_down_reason", lambda *a, **k: None)
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        g._tap("SELECT 1", retries=2)
    assert len(calls) == 2


def test_source_switch(monkeypatch):
    monkeypatch.delenv("V2_GAIA_SOURCE", raising=False)
    assert g.source_mode() == "auto"
    monkeypatch.setenv("V2_GAIA_SOURCE", "VizieR")
    assert g.source_mode() == "vizier"
    monkeypatch.setenv("V2_GAIA_SOURCE", "esa")
    with pytest.raises(ValueError):
        g.source_mode()  # not swallowed as an "outage"


def _tables():
    src = pd.DataFrame(
        {
            "Source": [1, 2],
            "RA_ICRS": [10.0, 10.001],
            "DE_ICRS": [20.0, 20.001],
            "Plx": [1.0, 2.0],
            "Gmag": [15.0, 19.0],
        }
    )
    ap = pd.DataFrame({"Source": [1], "PQSO": [0.1], "PGal": [0.2], "Pstar": [0.7], "PWD": [0.0], "Pbin": [0.0]})
    var = pd.DataFrame({"Source": [2], "Class": ["RR"], "ClassSc": [0.9]})
    return src, ap, var


def test_vizier_copy_asks_the_three_tables_side_by_side_and_merges_as_before(monkeypatch):
    src, ap, var = _tables()
    started = []

    def cone(cat, ra, dec, r, columns=("**",)):
        started.append((cat, time.monotonic()))
        time.sleep(0.4)
        return {"I/355/gaiadr3": src, "I/355/paramp": ap, "I/358/vclassre": var}[cat]

    monkeypatch.setattr(g, "vizier_cone", cone)
    t0 = time.monotonic()
    out = g._vizier_fallback(10.0, 20.0, 1.0)
    assert time.monotonic() - t0 < 0.9  # 3 x 0.4 s one after the other would be 1.2 s
    assert len({round(t - t0, 1) for _, t in started}) == 1  # all three began together
    assert out.source_id.tolist() == [1, 2] and out.parallax.tolist() == [1.0, 2.0]
    r1 = out.set_index("source_id")
    assert r1.loc[1, "classprob_dsc_combmod_star"] == 0.7 and pd.isna(r1.loc[2, "classprob_dsc_combmod_star"])
    assert r1.loc[2, "best_class_name"] == "RR" and r1.loc[2, "best_class_score"] == 0.9
    assert set(out.gaia_base_query_status) == {"vizier_fallback"} and set(out.gaia_vari_summary_query_status) == {
        "fallback_unavailable"
    }
    assert set(g.AP + g.SPEC_AP + g.VAR_SUMMARY) <= set(
        out.columns
    )  # absent products are NA columns, not missing columns


def test_empty_cone_does_not_wait_for_the_other_two(monkeypatch):
    def cone(cat, *a, **k):
        if cat == "I/355/gaiadr3":
            return pd.DataFrame()
        time.sleep(2.0)
        return None

    monkeypatch.setattr(g, "vizier_cone", cone)
    t0 = time.monotonic()
    assert g._vizier_fallback(10.0, 20.0, 1.0).empty
    assert time.monotonic() - t0 < 1.0


def test_failing_optional_tables_do_not_fail_the_copy(monkeypatch):
    src, _, _ = _tables()

    def cone(cat, *a, **k):
        if cat == "I/355/gaiadr3":
            return src
        raise ConnectionError("mirror down")

    monkeypatch.setattr(g, "vizier_cone", cone)
    out = g._vizier_fallback(10.0, 20.0, 1.0)
    assert len(out) == 2 and out.classprob_dsc_combmod_star.isna().all()
    monkeypatch.setattr(g, "vizier_cone", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("all mirrors down")))
    with pytest.raises(ConnectionError):  # the base table is required: fetch() then raises as before
        g._vizier_fallback(10.0, 20.0, 1.0)


def test_vizier_mode_never_asks_esa(monkeypatch):
    monkeypatch.setenv("V2_GAIA_SOURCE", "vizier")
    monkeypatch.setattr(g, "_bounded", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ESA asked")))
    src, ap, var = _tables()
    monkeypatch.setattr(
        g, "vizier_cone", lambda cat, *a, **k: {"I/355/gaiadr3": src, "I/355/paramp": ap, "I/358/vclassre": var}[cat]
    )
    monkeypatch.setattr(
        g, "_merge_fidelity", lambda df, deadline=None: df.assign(gaia_fidelity_query_status="ok", fidelity_v2=0.9)
    )
    df = g.fetch(10.0, 20.0, 1.0)
    assert set(df.gaia_base_query_status) == {"vizier_fallback"} and df.gaia_release.iloc[0] == "DR3"

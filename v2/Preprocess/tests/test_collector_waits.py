"""Recent-failure memory and per-collector budgets (2.55.0)."""

import sys
import time
import types
from pathlib import Path

import pandas as pd

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import archive_cache  # noqa: E402
import controller  # noqa: E402


def _fake(calls, fail=True, budget=None):
    m = types.SimpleNamespace()

    def fetch(ra, dec, r):
        calls.append(time.monotonic())
        if fail:
            raise ConnectionError("service unavailable")
        return pd.DataFrame(
            {"catalog": ["X"], "catalog_object_id": ["1"], "object_name": ["x"], "ra": [ra], "dec": [dec]}
        )

    m.fetch = fetch
    m.save = lambda df, path: df.to_csv(path, index=False)
    if budget is not None:
        m.BUDGET_S = budget
    return m


def _setup(tmp_path, monkeypatch, calls, **kw):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    mod = _fake(calls, **kw)
    monkeypatch.setattr(controller, "_load_collector", lambda name: mod)
    monkeypatch.setattr(controller, "COLLECTORS", ["atnf_pulsar"])
    monkeypatch.setattr(controller.archive_cache, "prune", lambda *a, **k: {})


def test_failed_auxiliary_collector_is_skipped_until_the_memory_expires(tmp_path, monkeypatch):
    calls = []
    _setup(tmp_path, monkeypatch, calls)
    s1 = controller.collect_all(10.0, 20.0, 1.0, tmp_path / "raw1", workers=1)
    assert s1.status.tolist() == ["error"] and len(calls) == 1
    s2 = controller.collect_all(10.0, 20.0, 1.0, tmp_path / "raw2", workers=1)  # the same search, at once
    assert s2.status.tolist() == ["error"] and s2.cache.tolist() == ["recent_failure"] and len(calls) == 1
    assert "skipped" in s2.error.iloc[0]
    rec = archive_cache._read_failures()["atnf_pulsar"]
    rec[0]["t"] -= archive_cache.failure_memory_s() + 1  # the memory has expired
    archive_cache._write_failures({"atnf_pulsar": rec})
    mod_ok = _fake(calls, fail=False)
    monkeypatch.setattr(controller, "_load_collector", lambda name: mod_ok)
    s3 = controller.collect_all(10.0, 20.0, 1.0, tmp_path / "raw3", workers=1)
    assert s3.status.tolist() == ["ok"] and len(calls) == 2
    assert "atnf_pulsar" not in archive_cache._read_failures()  # forgotten after the success


def test_an_error_at_one_cone_does_not_switch_the_collector_off_elsewhere(tmp_path, monkeypatch):
    """2.56.0: an unparsable SDSS answer at NGC 4522 switched SDSS spectroscopy
    off for the COSMOS and Galactic-plane searches that followed (2.55.0)."""
    calls = []
    _setup(tmp_path, monkeypatch, calls)
    controller.collect_all(188.4155, 9.1751, 2.0, tmp_path / "a", workers=1)
    s = controller.collect_all(150.10, 2.25, 2.0, tmp_path / "b", workers=1)  # another cone: asked
    assert s.cache.tolist() != ["recent_failure"] and len(calls) == 2
    # a second cone failing as well is an outage: the third cone is not asked
    s = controller.collect_all(283.80, -2.10, 1.0, tmp_path / "c", workers=1)
    assert s.cache.tolist() == ["recent_failure"] and len(calls) == 2


def test_a_timeout_is_remembered_for_every_cone(tmp_path, monkeypatch):
    calls = []
    _setup(tmp_path, monkeypatch, calls)
    archive_cache.note_outcome("atnf_pulsar", "timeout", "abandoned after 60 s", 188.4155, 9.1751, 2.0)
    s = controller.collect_all(150.10, 2.25, 2.0, tmp_path / "b", workers=1)
    assert s.cache.tolist() == ["recent_failure"] and not calls


def test_a_slow_error_is_remembered_for_every_cone(tmp_path, monkeypatch):
    """2.56.0 review: an error that took SLOW_FAILURE_S or more (HEASARC "System
    overloaded" after 66 s) is a wait like a timeout; a quick one is not."""
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    archive_cache.note_outcome("ned", "error", "quick parse error", 188.4155, 9.1751, 2.0, seconds=2.0)
    assert archive_cache.recent_failure("ned", 150.10, 2.25, 2.0) is None
    archive_cache.note_outcome("ned", "ok")
    archive_cache.note_outcome("ned", "error", "System overloaded", 188.4155, 9.1751, 2.0, seconds=66.0)
    assert archive_cache.recent_failure("ned", 150.10, 2.25, 2.0)["error"] == "System overloaded"


def test_a_2_55_failure_file_is_read_as_service_wide(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    archive_cache._write_failures({"ned": {"t": time.time(), "status": "error", "error": "x"}})
    assert archive_cache.recent_failure("ned", 1.0, 2.0, 1.0)["error"] == "x"


def test_core_collectors_are_always_asked_again(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    calls = []
    monkeypatch.setattr(controller, "_load_collector", lambda name: _fake(calls))
    archive_cache.note_outcome("gaia_dr3", "timeout", "TAP")
    r = controller._collect_one("gaia_dr3", 10.0, 20.0, 1.0, tmp_path, "t")
    assert r["cache"] != "recent_failure" and len(calls) == 1


def test_memory_off_and_cache_off(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("V2_FAILURE_MEMORY_S", "0")
    archive_cache.note_outcome("ned", "timeout", "x")
    assert archive_cache.recent_failure("ned") is None
    monkeypatch.setenv("V2_FAILURE_MEMORY_S", "600")
    monkeypatch.setenv("V2_CACHE", "0")
    archive_cache.note_outcome("ned", "timeout", "x")
    assert archive_cache.recent_failure("ned") is None


def test_collector_budget_is_per_collector(monkeypatch):
    monkeypatch.setattr(controller, "_load_collector", lambda name: _fake([], budget=45.0))
    assert controller._budget("atnf_pulsar", 300.0) == 45.0
    assert controller._budget("atnf_pulsar", 30.0) == 30.0  # never above the caller's budget
    seen = []

    def job(name, event):
        while not event.is_set():
            time.sleep(0.01)
        seen.append(name)
        return {"collector": name, "status": "ok"}

    t0 = time.monotonic()
    out = controller._run_bounded(job, ["slow"], 1, {"slow": 0.3})
    assert out[0]["status"] == "timeout" and time.monotonic() - t0 < 5


def test_core_collector_after_a_failure_gets_its_retry_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    ls = _fake([])
    ls.RETRY_BUDGET_S = 90.0
    mods = {"desi_legacy": ls, "panstarrs1": _fake([])}
    monkeypatch.setattr(controller, "_load_collector", lambda name: mods[name])
    assert controller._budget("desi_legacy", 300.0) == 300.0
    for n in mods:
        archive_cache.note_outcome(n, "timeout", "x")
    assert controller._budget("desi_legacy", 300.0) == 90.0
    # no RETRY_BUDGET_S (an internal fallback needs the full budget): unchanged
    assert controller._budget("panstarrs1", 300.0) == 300.0
    archive_cache.note_outcome("desi_legacy", "ok")
    assert controller._budget("desi_legacy", 300.0) == 300.0


def test_only_ls_declares_a_retry_budget():
    assert controller._load_collector("desi_legacy").RETRY_BUDGET_S == 90.0
    for n in ("gaia_dr3", "panstarrs1"):
        assert not hasattr(controller._load_collector(n), "RETRY_BUDGET_S")


def test_gaia_tap_asks_the_synchronous_endpoint_first(monkeypatch):
    """2.56.0: four asynchronous jobs (3-4 paced requests each) made every
    Gaia collection 55-64 s; a sync answer below the row cap is complete."""
    import pytest

    pytest.importorskip("astroquery.gaia")
    import astroquery.gaia as ag
    import gaia_dr3

    calls = []

    class Job:
        def __init__(self, n):
            self.n = n

        def get_results(self):
            from astropy.table import Table

            return Table({"source_id": list(range(self.n))})

    class FakeGaia:
        def __init__(self, sync_rows):
            self.sync_rows = sync_rows

        def launch_job(self, q):
            calls.append("sync")
            return Job(self.sync_rows)

        def launch_job_async(self, q):
            calls.append("async")
            return Job(5000)

    monkeypatch.setattr(ag, "Gaia", FakeGaia(13))
    assert len(gaia_dr3._tap("q")) == 13 and calls == ["sync"]
    calls.clear()
    monkeypatch.setattr(ag, "Gaia", FakeGaia(gaia_dr3.SYNC_MAX_ROWS))  # a full page is a cut cone
    assert len(gaia_dr3._tap("q")) == 5000 and calls == ["sync", "async"]

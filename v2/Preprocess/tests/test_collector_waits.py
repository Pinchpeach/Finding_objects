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


def test_failed_auxiliary_collector_is_skipped_until_the_memory_expires(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    calls = []
    mod = _fake(calls)
    monkeypatch.setattr(controller, "_load_collector", lambda name: mod)
    monkeypatch.setattr(controller, "COLLECTORS", ["atnf_pulsar"])
    monkeypatch.setattr(controller.archive_cache, "prune", lambda *a, **k: {})
    s1 = controller.collect_all(10.0, 20.0, 1.0, tmp_path / "raw1", workers=1)
    assert s1.status.tolist() == ["error"] and len(calls) == 1
    s2 = controller.collect_all(30.0, 20.0, 1.0, tmp_path / "raw2", workers=1)  # another search, at once
    assert s2.status.tolist() == ["error"] and s2.cache.tolist() == ["recent_failure"] and len(calls) == 1
    assert "skipped" in s2.error.iloc[0]
    rec = archive_cache._read_failures()["atnf_pulsar"]
    rec["t"] -= archive_cache.failure_memory_s() + 1  # the memory has expired
    archive_cache._write_failures({"atnf_pulsar": rec})
    mod_ok = _fake(calls, fail=False)
    monkeypatch.setattr(controller, "_load_collector", lambda name: mod_ok)
    s3 = controller.collect_all(50.0, 20.0, 1.0, tmp_path / "raw3", workers=1)
    assert s3.status.tolist() == ["ok"] and len(calls) == 2
    assert "atnf_pulsar" not in archive_cache._read_failures()  # forgotten after the success


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

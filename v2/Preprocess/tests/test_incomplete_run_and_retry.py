"""Incomplete-run columns in the result tables and the failed-archives-only retry (2.57.0)."""

import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
GET = V2 / "Get_data"
sys.path.insert(0, str(GET))
import archive_cache  # noqa: E402
import controller  # noqa: E402


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cov = _mod("v2_cov_incomplete", V2 / "catalog_coverage.py")
summary = _mod("v2_summary_incomplete", V2 / "summary.py")


def _summary(raw, rows):
    raw.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(raw / "collection_summary_t.csv", index=False)


# ------------------------------------------------------------------ 1-1: columns
def test_status_values_and_missing_list(tmp_path):
    raw = tmp_path / "raw"
    _summary(
        raw,
        [
            {"collector": "nvss", "status": "error", "rows": 0, "error": "HTTP 502"},
            {"collector": "desi_legacy", "status": "timeout", "rows": 0, "error": "300 s"},
            {"collector": "allwise", "status": "ok", "rows": 3, "error": ""},
            {"collector": "first", "status": "outside_footprint", "rows": 0, "error": ""},
        ],
    )
    c = cov.summarize(raw)
    assert cov.status(c) == "key_archives_missing"
    assert cov.missing(c) == "desi_legacy:timeout|nvss:error"  # key archives first
    assert cov.status({"known": True, "failed": [{"collector": "nvss", "status": "error", "key": False}]}) == (
        "archives_missing"
    )
    _summary(raw, [{"collector": "allwise", "status": "ok", "rows": 3, "error": ""}])
    c = cov.summarize(raw)
    assert (cov.status(c), cov.missing(c)) == ("complete", "")
    # No collection summary (files collected elsewhere): unknown, never a false all-clear.
    assert cov.status(cov.summarize(tmp_path / "none")) == "unknown" and cov.status(None) == "unknown"


def test_both_result_tables_carry_the_columns(tmp_path):
    raw = tmp_path / "raw"
    _summary(raw, [{"collector": "gaia_dr3", "status": "error", "rows": 0, "error": "x"}])
    df = pd.DataFrame(
        {
            "designation": ["A", "B"],
            "ra": [1.0, 2.0],
            "dec": [0.0, 0.0],
            "primary_class": ["STAR", "GALAXY"],
            "catalogs": ["Gaia DR3", "NED"],
            "object_id": ["OBJ1", "OBJ2"],
        }
    )
    full = cov.annotate(df, cov.summarize(raw))
    assert (full[cov.COL_STATUS] == "key_archives_missing").all() and (full[cov.COL_MISSING] == "gaia_dr3:error").all()
    summary.write(full, tmp_path)
    for name in (summary.SUMMARY, summary.LITERATURE_ONLY):
        t = pd.read_csv(tmp_path / name, keep_default_na=False)
        assert {cov.COL_STATUS, cov.COL_MISSING} <= set(t.columns)
    s = pd.read_csv(tmp_path / summary.SUMMARY)
    assert list(s.run_archives_status) == ["key_archives_missing"]  # the NED-only row goes to the other table
    assert "df" not in cov.annotate.__code__.co_varnames or df.columns.tolist() == list(df.columns)  # input untouched
    assert cov.COL_STATUS not in df.columns


def test_pipeline_writes_the_columns_for_an_empty_search(tmp_path):
    pipe = _mod("v2_pipeline_incomplete", V2 / "pipeline.py")
    raw = tmp_path / "raw"
    _summary(raw, [{"collector": "desi_legacy", "status": "timeout", "rows": 0, "error": "300 s"}])
    out = pipe.run(tmp_path / "work", raw_dir=raw)
    assert out.empty
    for f in ("classified_objects.csv", "objects_summary.csv"):
        t = pd.read_csv(tmp_path / "work" / f)
        assert {"run_archives_status", "run_archives_missing"} <= set(t.columns)


# ------------------------------------------------------------------ 1-2: retry
def _fake(calls, fails, name):
    m = types.SimpleNamespace()

    def fetch(ra, dec, r):
        calls.append(name)
        if fails.get(name):
            raise ConnectionError("service unavailable")
        return pd.DataFrame(
            {"catalog": ["X"], "catalog_object_id": [name], "object_name": ["x"], "ra": [ra], "dec": [dec]}
        )

    m.fetch = fetch
    m.save = lambda df, path: df.to_csv(path, index=False)
    return m


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Four fake collectors: desi_legacy (key) / gaia_dr3 (key, core) / nvss / ned fail on demand."""
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    calls, fails = [], {}
    mods = {n: _fake(calls, fails, n) for n in ("gaia_dr3", "desi_legacy", "nvss", "ned")}
    monkeypatch.setattr(controller, "_load_collector", lambda name: mods[name])
    monkeypatch.setattr(controller, "COLLECTORS", list(mods))
    monkeypatch.setattr(controller.archive_cache, "prune", lambda *a, **k: {})
    return types.SimpleNamespace(calls=calls, fails=fails, raw=tmp_path / "raw", mods=mods)


def test_retry_asks_only_failed_key_archives_and_replaces_their_rows(world):
    world.fails.update(desi_legacy=True, nvss=True)
    controller.collect_all(150.1, 2.25, 2.0, world.raw, workers=1)
    assert sorted(world.calls) == ["desi_legacy", "gaia_dr3", "ned", "nvss"]
    assert controller.failed_collectors(world.raw) == ["desi_legacy"]  # nvss is not a key archive
    assert controller.failed_collectors(world.raw, "all") == ["desi_legacy", "nvss"]
    world.calls.clear()
    world.fails.clear()  # the services recovered
    new = controller.retry_failed(world.raw, 150.1, 2.25, 2.0)
    assert world.calls == ["desi_legacy"] and new.status.tolist() == ["ok"]  # nothing that worked is asked again
    s = pd.read_csv(world.raw / next(f.name for f in world.raw.glob("collection_summary_*.csv")))
    assert s.collector.tolist() == ["gaia_dr3", "desi_legacy", "nvss", "ned"]  # COLLECTORS order kept
    assert dict(zip(s.collector, s.status)) == {"gaia_dr3": "ok", "desi_legacy": "ok", "nvss": "error", "ned": "ok"}
    assert list(world.raw.glob("desi_legacy_*.csv"))  # the recovered archive's rows are in the folder
    assert cov.summarize(world.raw)["key_failed"] is False  # the next classification is complete for key archives
    # "all" then takes the remaining failed one
    world.calls.clear()
    controller.retry_failed(world.raw, 150.1, 2.25, 2.0, which="all")
    assert world.calls == ["nvss"]
    assert cov.status(cov.summarize(world.raw)) == "complete"
    assert controller.retry_failed(world.raw, 150.1, 2.25, 2.0).empty and world.calls == [
        "nvss"
    ]  # nothing failed: no request


def test_retry_is_not_blocked_by_the_failure_memory(world):
    """The 10-minute memory skips a non-core collector asked for again by a new
    search; an explicit retry is exactly that request."""
    world.fails.update(nvss=True)
    controller.collect_all(150.1, 2.25, 2.0, world.raw, workers=1)
    # a plain new search of the same cone is skipped by the memory ...
    s = controller.collect_all(150.1, 2.25, 2.0, world.raw / "again", workers=1)
    assert s.set_index("collector").loc["nvss", "cache"] == "recent_failure"
    world.calls.clear()
    world.fails.clear()
    # ... the retry is not
    controller.retry_failed(world.raw, 150.1, 2.25, 2.0, which="all")
    assert world.calls == ["nvss"]
    assert archive_cache.recent_failure("nvss") is None  # forgotten after the success


def test_still_failing_collector_stays_failed_and_is_reported(world, capsys):
    world.fails.update(desi_legacy=True)
    controller.collect_all(150.1, 2.25, 2.0, world.raw, workers=1)
    new = controller.retry_failed(world.raw, 150.1, 2.25, 2.0)
    assert new.status.tolist() == ["error"]
    assert "still failing: desi_legacy" in capsys.readouterr().out
    assert cov.summarize(world.raw)["key_failed"] is True


def test_retry_budget_applies_to_an_explicit_retry(monkeypatch):
    mod = types.SimpleNamespace(RETRY_BUDGET_S=90.0)
    monkeypatch.setattr(controller, "_load_collector", lambda name: mod)
    monkeypatch.setattr(controller.archive_cache, "recent_failure", lambda *a, **k: None)
    assert controller._budget("nvss", 300.0) == 300.0  # no recent failure: the full budget
    assert (
        controller._budget("nvss", 300.0, retry=True) == 90.0
    )  # asked again by the user: a recovery needs one attempt


def test_search_json_round_trips_the_exact_cone(world):
    ra, dec, r = 150.1234567891, 2.2500000123, 2.0000004
    controller.collect_all(ra, dec, r, world.raw, workers=1)
    assert controller.read_search(world.raw) == (ra, dec, r)  # the tag would have rounded them
    assert controller.read_search(world.raw / "missing") is None
    assert (
        controller.last_collection(world.raw.parent) == world.raw
        or controller.last_collection(world.raw.parent) is None
    )


def test_pipeline_retry_needs_an_earlier_search(tmp_path):
    pipe = _mod("v2_pipeline_retry_err", V2 / "pipeline.py")
    with pytest.raises(ValueError, match="no earlier search"):
        pipe.run(tmp_path / "work", retry_failed="key")
    with pytest.raises(ValueError, match="no --raw-dir"):
        pipe.run(tmp_path / "work", raw_dir=tmp_path, retry_failed="key")


def test_pipeline_retry_with_nothing_failed_returns_the_existing_results(tmp_path):
    pipe = _mod("v2_pipeline_retry_none", V2 / "pipeline.py")
    work = tmp_path / "work"
    raw = work / "raw" / "ra1_dec2_r1arcmin"
    _summary(raw, [{"collector": "allwise", "status": "ok", "rows": 3, "error": ""}])
    (raw / "search.json").write_text(json.dumps({"ra": 1.0, "dec": 2.0, "radius_arcmin": 1.0}))
    pd.DataFrame({"object_id": ["OBJ1"], "primary_class": ["STAR"]}).to_csv(
        work / "classified_objects.csv", index=False
    )
    (work / "catalog_coverage.json").write_text(json.dumps({"known": True, "failed": [], "raw_dir": str(raw)}))
    t0 = time.time()
    out = pipe.run(work, retry_failed="key")
    assert out.primary_class.tolist() == ["STAR"] and time.time() - t0 < 5  # no collection, no classification


def test_pipeline_retry_of_another_search_does_not_return_these_results(tmp_path, capsys):
    """PR #73 review: classified_objects.csv belongs to the search it was classified from
    (catalog_coverage.json raw_dir); retrying an older search with nothing failed classifies that search again."""
    pipe = _mod("v2_pipeline_retry_other", V2 / "pipeline.py")
    work = tmp_path / "work"
    old = work / "raw" / "ra1_dec2_r1arcmin"
    new = work / "raw" / "ra50_dec20_r1arcmin"
    for raw, (ra, dec) in ((old, (1.0, 2.0)), (new, (50.0, 20.0))):
        _summary(raw, [{"collector": "allwise", "status": "ok", "rows": 0, "error": ""}])
        (raw / "search.json").write_text(json.dumps({"ra": ra, "dec": dec, "radius_arcmin": 1.0}))
    pd.DataFrame({"object_id": ["NEW1"], "primary_class": ["STAR"]}).to_csv(
        work / "classified_objects.csv", index=False
    )
    (work / "catalog_coverage.json").write_text(json.dumps({"known": True, "failed": [], "raw_dir": str(new)}))
    out = pipe.run(work, ra=1.0, dec=2.0, radius=1.0, retry_failed="key")
    assert "NEW1" not in out.get("object_id", pd.Series(dtype=str)).tolist()  # not the other search's objects
    assert "classifying ra1_dec2_r1arcmin again" in capsys.readouterr().out


# ------------------------------------------------ collectors served by a reduced alternative source
def _gaia_raw(raw, status):
    raw.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"catalog_object_id": ["1"], "ra": [1.0], "dec": [2.0], "gaia_base_query_status": [status]}).to_csv(
        raw / "gaia_dr3_ra1_dec2_r1arcmin.csv", index=False
    )
    pd.DataFrame({"catalog_object_id": ["1"], "ra": [1.0], "dec": [2.0]}).to_csv(  # another collector's file
        raw / "gaia_dr3_variability_sos_vizier_ra1_dec2_r1arcmin.csv", index=False
    )


def test_gaia_from_the_vizier_copy_is_reported_with_what_it_lacks(tmp_path):
    raw = tmp_path / "raw"
    _summary(raw, [{"collector": "gaia_dr3", "status": "ok", "rows": 1, "error": ""}])
    _gaia_raw(raw, "vizier_fallback")
    c = cov.summarize(raw)
    assert not c["failed"] and [a["collector"] for a in c["alternative"]] == ["gaia_dr3"]
    assert cov.status(c) == "degraded" and cov.missing(c) == "gaia_dr3:alternative_source"
    msg = cov.message(c)
    assert (
        "VizieR I/355 copy" in msg and "variability summary" in msg and "in_vari_" in msg
    )  # the lost columns, by name
    assert "FLAME" not in msg and "ESP-UCD" not in msg  # 2.57.0 review: the copy has them (I/355/paramp)
    _gaia_raw(raw, "tap")  # the archive's own answer: complete, no warning
    c = cov.summarize(raw)
    assert cov.status(c) == "complete" and cov.message(c) == ""
    # a failure outranks it
    _summary(raw, [{"collector": "gaia_dr3", "status": "timeout", "rows": 0, "error": "x"}])
    _gaia_raw(raw, "vizier_fallback")
    assert cov.summarize(raw)["alternative"] == [] and cov.status(cov.summarize(raw)) == "key_archives_missing"


def test_an_empty_ps1_answer_from_the_vizier_copy_is_still_an_alternative_source(tmp_path):
    """PR #73 review: the MAST path never writes ps1_query_status, so an empty file that has it in its header is
    the VizieR copy's answer -- reported (degraded, retryable) and not served from the cache to a retry."""
    raw = tmp_path / "raw"
    _summary(raw, [{"collector": "panstarrs1", "status": "empty", "rows": 0, "error": ""}])
    cols = ["catalog", "catalog_object_id", "object_name", "ra", "dec", "ps1_query_status"]
    pd.DataFrame(columns=cols).to_csv(raw / "panstarrs1_ra1_dec2_r1arcmin.csv", index=False)
    c = cov.summarize(raw)
    assert [a["collector"] for a in c["alternative"]] == ["panstarrs1"] and cov.status(c) == "degraded"
    assert controller.failed_collectors(raw, "key") == ["panstarrs1"]
    assert archive_cache.fallback(pd.DataFrame(columns=cols))
    # the MAST path's empty answer (no status column) is a complete empty cone
    pd.DataFrame(columns=cols[:-1]).to_csv(raw / "panstarrs1_ra1_dec2_r1arcmin.csv", index=False)
    assert cov.status(cov.summarize(raw)) == "complete" and not archive_cache.fallback(pd.DataFrame(columns=cols[:-1]))


def test_retry_gets_the_primary_source_instead_of_the_cached_copy(world):
    calls = []
    answers = iter(["vizier_fallback", "tap"])

    def gaia_fetch(ra, dec, r):
        calls.append("gaia")
        return pd.DataFrame(
            {
                "catalog": ["G"],
                "catalog_object_id": ["1"],
                "object_name": ["g"],
                "ra": [ra],
                "dec": [dec],
                "gaia_base_query_status": [next(answers)],
            }
        )

    world.mods["gaia_dr3"].fetch = gaia_fetch
    controller.collect_all(150.1, 2.25, 2.0, world.raw, workers=1)
    assert cov.status(cov.summarize(world.raw)) == "degraded" and calls == ["gaia"]
    # the same cone asked again is served by the (one-day) cache of the copy ...
    s = controller.collect_all(150.1, 2.25, 2.0, world.raw / "again", workers=1)
    assert s.set_index("collector").loc["gaia_dr3", "cache"] == "hit" and calls == ["gaia"]
    # ... a retry is not
    assert controller.failed_collectors(world.raw) == ["gaia_dr3"]
    controller.retry_failed(world.raw, 150.1, 2.25, 2.0)
    assert calls == ["gaia", "gaia"] and cov.status(cov.summarize(world.raw)) == "complete"


def test_retry_only_asks_the_named_collectors_among_the_failed_ones(world):
    """2.60.10: the validation workflows wait out a Data Lab outage and ask only desi_legacy again."""
    world.fails.update(desi_legacy=True, gaia_dr3=True)
    controller.collect_all(150.1, 2.25, 2.0, world.raw, workers=1)
    assert sorted(controller.failed_collectors(world.raw)) == ["desi_legacy", "gaia_dr3"]
    world.calls.clear()
    world.fails.clear()
    new = controller.retry_failed(world.raw, 150.1, 2.25, 2.0, only=("desi_legacy",))
    assert world.calls == ["desi_legacy"] and new.collector.tolist() == ["desi_legacy"]
    assert controller.failed_collectors(world.raw) == ["gaia_dr3"]  # the other one was not asked
    assert controller.retry_failed(world.raw, 150.1, 2.25, 2.0, only=("nvss",)).empty  # nothing of it failed

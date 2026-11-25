"""Validation workflows and the services' guidelines (2.60.8): NED asks for no concurrent automated queries, SDSS
SkyServer for at most 60 queries a minute; astroquery's own SDSS disk cache is not used."""

import re
import sys
from pathlib import Path

import pytest
import yaml

V2 = Path(__file__).resolve().parents[2]
ROOT = V2.parent
sys.path.insert(0, str(V2 / "Get_data"))
import _catalog_utils  # noqa: E402
import controller  # noqa: E402

WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


# ------------------------------------------------------------------------------------------ V2_SKIP_COLLECTORS
def test_skip_list_names_collectors_or_blind(monkeypatch):
    assert controller.skipped_collectors("") == set() and controller.skipped_collectors(" ") == set()
    assert controller.skipped_collectors("ned") == {"ned"}
    assert controller.skipped_collectors(" ned , simbad ,") == {"ned", "simbad"}
    assert controller.skipped_collectors("blind") == set(controller.BLIND_DROPPED)
    assert "ned" in controller.BLIND_DROPPED and "gaia_dr3" not in controller.BLIND_DROPPED
    monkeypatch.setenv("V2_SKIP_COLLECTORS", "blind,sdss_dr18")
    assert controller.skipped_collectors() == set(controller.BLIND_DROPPED) | {"sdss_dr18"}


def test_a_typo_is_an_error_not_a_silent_ned(monkeypatch):
    with pytest.raises(ValueError, match="not a collector"):
        controller.skipped_collectors("nedd")
    monkeypatch.setenv("V2_SKIP_COLLECTORS", "NED")  # case matters: the workflow must say what it means
    with pytest.raises(ValueError):
        controller.collectors_to_run()


def test_every_blind_dropped_name_is_a_collector_and_the_other_lists_agree():
    assert set(controller.BLIND_DROPPED) - set(controller.COLLECTORS) <= {  # sources that are no collector any more
        "pn_spectroscopy",
        "hash_pn",
        "asas_sn_supernova",
        "asiago_supernova",
    }
    spec_path = V2 / "benchmark" / "collect_deep_cosmos.py"
    src = spec_path.read_text()
    deep = set(
        re.findall(r'"([a-z_0-9]+)",', src[src.index("NOT_BLIND = (") : src.index(")", src.index("NOT_BLIND = ("))])
    )
    assert deep == set(controller.BLIND_DROPPED)
    for wf in ("v2_locked_set_c", "experiment-ab-fields", "v2_independent_truth", "v2_independent_truth_b"):
        text = (ROOT / ".github" / "workflows" / f"{wf}.yml").read_text()
        line = next(ln for ln in text.splitlines() if "lamost_spectroscopy_*" in ln)
        names = {
            p.strip().removesuffix("_*").removesuffix(")").removesuffix("_*") for p in line.split(")")[0].split("|")
        }
        assert names == set(controller.BLIND_DROPPED), wf


def test_collect_all_does_not_ask_a_skipped_collector(tmp_path, monkeypatch):
    asked = []

    def fake_one(name, ra, dec, radius, out_dir, tag, cancel=None):
        asked.append(name)
        return {"collector": name, "status": "ok", "rows": 0, "elapsed_seconds": 0.0}

    monkeypatch.setattr(controller, "_collect_one", fake_one)
    monkeypatch.setattr(controller, "_disable_astroquery_cache", lambda: None)
    monkeypatch.setattr(controller.archive_cache, "prune", lambda *a, **k: {})
    monkeypatch.setattr(controller.archive_cache, "note_outcome", lambda *a, **k: None)
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("V2_SKIP_COLLECTORS", "ned")
    summary = controller.collect_all(10.0, 20.0, 2.0, tmp_path / "raw", workers=1)
    assert "ned" not in asked and "simbad" in asked and len(asked) == len(controller.COLLECTORS) - 1
    assert "ned" not in set(summary["collector"])  # absent from the summary: neither failed nor "missing"
    asked.clear()
    monkeypatch.delenv("V2_SKIP_COLLECTORS")
    controller.collect_all(10.0, 20.0, 2.0, tmp_path / "raw2", workers=1)
    assert "ned" in asked and len(asked) == len(controller.COLLECTORS)  # nothing set: everything, as before


# ------------------------------------------------------------------------------------------ the workflows
def _jobs():
    for path in WORKFLOWS:
        y = yaml.safe_load(path.read_text())
        for name, job in (y.get("jobs") or {}).items():
            yield path.name, name, job


def _runs_collectors(job) -> bool:
    body = "\n".join(str(s.get("run", "")) for s in job.get("steps") or [] if isinstance(s, dict))
    return bool(re.search(r"pipeline\.py --ra|controller\.py --ra|validate_reference_objects\.py run", body))


def _matrix_size(job) -> int:
    m = (job.get("strategy") or {}).get("matrix")
    if isinstance(m, dict):
        sizes = [len(v) for v in m.values() if isinstance(v, list)]
        return max(sizes) if sizes else 1
    return 1 if m is None else 2  # a dynamic matrix: assume several


def _mentions_skip(job) -> bool:
    env_text = yaml.safe_dump(job)  # job env and step env alike
    return "V2_SKIP_COLLECTORS" in env_text


def test_no_matrix_job_asks_ned_in_parallel():
    """Every matrix job that runs the collectors either skips NED (V2_SKIP_COLLECTORS) or runs one job at a time."""
    bad = []
    for wf, name, job in _jobs():
        if not (_runs_collectors(job) and _matrix_size(job) > 1):
            continue
        mp = str((job.get("strategy") or {}).get("max-parallel", ""))
        one_at_a_time = mp.strip() == "1"
        if not (_mentions_skip(job) or one_at_a_time):
            bad.append(f"{wf}:{name}")
    assert not bad, "matrix jobs that ask NED concurrently: " + ", ".join(bad)


def test_the_jobs_that_may_ask_ned_serialise_when_they_do():
    for wf in ("v2_independent_truth.yml", "v2_independent_truth_b.yml", "validate-reference-objects.yml"):
        y = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text())
        job = next(j for j in y["jobs"].values() if (j.get("strategy") or {}).get("matrix"))
        mp = str(job["strategy"]["max-parallel"])
        assert "with_ned == 'true' && 1 ||" in mp, wf  # NED asked: one job at a time
        assert "with_ned" in str((y.get("on") or y.get(True))["workflow_dispatch"]["inputs"]), wf
        assert "' ' || 'ned'" in yaml.safe_dump(job)  # the default skips NED
    probe = yaml.safe_load((ROOT / ".github" / "workflows" / "v2_practical_probe.yml").read_text())
    assert probe["jobs"]["field"]["strategy"]["max-parallel"] == 1


# ------------------------------------------------------------------------------------------ SDSS cache
def test_the_sdss_client_never_uses_astroquery_disk_cache(monkeypatch):
    from astroquery.query import BaseQuery

    seen = []

    class _Response:
        text = "run,ra\n1,2\n"

    monkeypatch.setattr(BaseQuery, "_request", lambda self, *a, **k: (seen.append(k.get("cache")), _Response())[1])
    client = _catalog_utils._sdss()
    client._request("GET", "http://example.invalid/", cache=True)  # the SDSS methods pass cache=True themselves
    client._request("GET", "http://example.invalid/")
    assert seen == [False, False]

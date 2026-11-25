"""Workflows that collect many regions at once and the Data Lab 502 of 2026-11-25 (2.60.10)."""

import importlib.util
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
import yaml

V2 = Path(__file__).resolve().parents[2]
ROOT = V2.parent
SET_C = ROOT / ".github" / "workflows" / "v2_locked_set_c.yml"
AB = ROOT / ".github" / "workflows" / "experiment-ab-fields.yml"


def _steps(path, job="field"):
    return yaml.safe_load(path.read_text())["jobs"][job]["steps"]


def _index(steps, fragment):
    return next(i for i, s in enumerate(steps) if fragment in str(s.get("name", "")))


@pytest.mark.parametrize("path", [SET_C, AB])
def test_collect_is_staggered_and_a_failed_legacy_archive_is_asked_again_before_the_blind_copy(path):
    steps = _steps(path)
    collect = next(s for s in steps if str(s.get("name", "")).startswith("Collect"))
    assert "RANDOM % 90" in collect["run"] and "sleep $d" in collect["run"]  # a random start delay
    retry = _index(steps, "failed Legacy Surveys archive again")
    assert retry > steps.index(collect)
    assert retry < _index(steps, "Blind")  # the blind raw copy and the summary it keeps come after the retry
    r = steps[retry]
    assert r.get("continue-on-error") is True  # a retry never fails the job
    assert "retry_failed_archive.py" in r["run"] and "--only desi_legacy" in r["run"]


def test_the_set_c_rules_and_the_gate_are_untouched():
    text = SET_C.read_text()
    assert "LOCK_SHA256: 21c42406ce3700ce7c271f2773a81297484e4f7543a821aaa05cf521f378b7e4" in text
    assert "if len(rows) < 54 or (bad > 0.10).any():" in text
    assert 'core = ["gaia_dr3", "desi_legacy", "panstarrs1", "allwise", "twomass"]' in text
    assert "--aggregate-only" in text and "already scored on set C" in text  # aggregates only, once per version
    steps = _steps(SET_C)
    assert _index(steps, "Ask a failed Legacy Surveys archive again") < _index(steps, "Blind run and compact record")


def _helper():
    spec = importlib.util.spec_from_file_location(
        "retry_helper", ROOT / ".github" / "scripts" / "retry_failed_archive.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_helper_waits_and_asks_again_only_when_desi_legacy_failed(tmp_path, monkeypatch):
    mod = _helper()
    (tmp_path / "raw" / "tag").mkdir(parents=True)
    failed, calls = [], {"sleep": [], "retry": []}
    fake = types.SimpleNamespace(
        failed_collectors=lambda raw_dir, which="key": list(failed),
        retry_failed=lambda raw_dir, ra, dec, r, workers, which, only=None: calls["retry"].append((tuple(only), r)),
    )
    monkeypatch.setattr(mod, "load_controller", lambda: fake)
    monkeypatch.setattr(mod.time, "sleep", lambda s: calls["sleep"].append(s))
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path), "150.1", "2.2", "12", "--wait", "7"])
    assert mod.main() == 0 and calls == {"sleep": [], "retry": []}  # nothing failed: nothing asked, no waiting
    failed[:] = ["gaia_dr3"]
    assert mod.main() == 0 and calls == {"sleep": [], "retry": []}  # another archive failed: not this step's business
    failed[:] = ["gaia_dr3", "desi_legacy"]
    assert mod.main() == 0
    assert calls["sleep"] == [7.0] and calls["retry"] == [(("desi_legacy",), 12.0)]
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path / "nowhere"), "150.1", "2.2", "12"])
    assert mod.main() == 0  # no collected field: nothing to do, no failure

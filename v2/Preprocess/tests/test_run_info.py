"""``benchmark/run_info.py``: every result directory says what it was made with (2.62.6).

The decision table of 2.62.2 could not be shown to have run with ``V2_POSERR_UNITS=legacy`` from its result files.  ``run_info.json`` records the commit, the
V2_* environment, what the code READS in that environment (defaults included), the UTC times, the status and the SHA-256 of the inputs.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark"))
import run_info as RI  # noqa: E402


def read(out):
    return json.loads(RI.target(out).read_text())


def test_a_record_has_commit_environment_effective_values_times_and_input_hashes(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_POSERR_UNITS", "fixed")
    monkeypatch.setenv("V2_ASSOC_AMBIG", "same,nearest")
    f = tmp_path / "list.csv"
    f.write_text("a,b\n1,2\n")
    d = tmp_path / "raw"
    d.mkdir()
    (d / "x.csv").write_text("12345")
    t0 = RI.start()
    RI.write(tmp_path / "out", inputs=[f, d], t0=t0, note="demo")
    r = read(tmp_path / "out")
    assert r["env"]["V2_POSERR_UNITS"] == "fixed" and r["env"]["V2_ASSOC_AMBIG"] == "same,nearest"
    assert r["effective"]["POSERR_UNITS"] == "fixed" and r["effective"]["AMBIG_FIX"] == ["nearest", "same"]
    assert r["status"] == "ok" and r["started_utc"] <= r["finished_utc"] and r["note"] == "demo"
    assert r["inputs"][0]["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert r["inputs"][1]["kind"] == "directory" and r["inputs"][1]["n_files"] == 1
    if r["commit"]:  # a checkout with git
        assert re.fullmatch(r"[0-9a-f]{40}", r["commit"]) and isinstance(r["dirty"], bool)


def test_the_effective_value_is_read_from_the_code_not_assumed(tmp_path, monkeypatch):
    """The default of V2_POSERR_UNITS is what association_model says it is; the record must say the same whichever way the default goes."""
    monkeypatch.delenv("V2_POSERR_UNITS", raising=False)
    got = subprocess.run([sys.executable, "-c", "import association_model as am; print(am.POSERR_UNITS)"], cwd=V2 / "Preprocess", capture_output=True, text=True).stdout.strip()
    RI.write(tmp_path, [])
    assert read(tmp_path)["effective"]["POSERR_UNITS"] == got and "V2_POSERR_UNITS" not in read(tmp_path)["env"]
    monkeypatch.setenv("V2_POSERR_UNITS", "legacy" if got == "fixed" else "fixed")
    RI.write(tmp_path / "other", [])
    assert read(tmp_path / "other")["effective"]["POSERR_UNITS"] != got


def test_the_environment_of_a_pipeline_a_tool_starts_can_replace_its_own(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys3")  # the shell of the tool
    RI.write(tmp_path / "a", [], env={"V2_POSERR_UNITS": "legacy", "PYTHONHASHSEED": "0"}, replace_env=True)
    r = read(tmp_path / "a")
    assert r["env"] == {"PYTHONHASHSEED": "0", "V2_POSERR_UNITS": "legacy"} and r["effective"]["LOWLAT_QSO"] == []  # the pipelines never saw surveys3
    RI.write(tmp_path / "b", [], env={"V2_POSERR_UNITS": "legacy"})
    assert read(tmp_path / "b")["env"]["V2_LOWLAT_QSO"] == "surveys3"  # added to the shell's


def test_a_directory_input_changes_its_hash_when_a_file_changes(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    (d / "a.csv").write_text("x")
    h1 = RI.describe_input(d)["sha256"]
    (d / "a.csv").write_text("xy")
    assert RI.describe_input(d)["sha256"] != h1
    (d / "a.csv").write_text("zz")  # same size, other content: only the content hash sees it
    assert RI.describe_input(d)["sha256"] == RI.describe_input(d)["sha256"]
    assert RI.describe_input(d, content=True)["sha256"] != RI.describe_input(d)["sha256"]
    assert RI.describe_input(tmp_path / "nothing")["kind"] == "missing"


def test_a_directory_of_links_to_the_runs_it_reuses_is_hashed_through_the_links(tmp_path):
    """Review of 2.62.6: ``regroup_new_order`` reused earlier runs through a folder of symlinks and was recorded with n_files 0 (the hash of nothing)."""
    real = tmp_path / "runs" / "field_1"
    real.mkdir(parents=True)
    (real / "classified_objects.csv").write_text("object_id\nOBJ1\n")
    links = tmp_path / "links"
    links.mkdir()
    (links / "field_1").symlink_to(real, target_is_directory=True)
    direct, linked = RI.describe_input(tmp_path / "runs"), RI.describe_input(links)
    assert linked["n_files"] == direct["n_files"] == 1
    assert linked["sha256"] == direct["sha256"] != hashlib.sha256(b"").hexdigest()
    (real / "classified_objects.csv").write_text("object_id\nOBJ2 changed\n")
    assert RI.describe_input(links)["sha256"] != linked["sha256"]
    (real / "loop").symlink_to(real, target_is_directory=True)  # a link loop ends
    assert RI.describe_input(links)["n_files"] == 1


def test_a_file_result_gets_a_sibling_record_and_a_directory_its_own(tmp_path):
    assert RI.target(tmp_path / "table.csv") == tmp_path / "table.run_info.json"
    assert RI.target(tmp_path / "table.csv.gz") == tmp_path / "table.run_info.json"
    assert RI.target(tmp_path / "results_2026-11-27h") == tmp_path / "results_2026-11-27h" / "run_info.json"


def test_the_context_manager_records_running_then_ok_or_failed(tmp_path):
    with RI.RunInfo(tmp_path / "ok", note="n"):
        assert read(tmp_path / "ok")["status"] == "running" and read(tmp_path / "ok")["finished_utc"] is None
    assert read(tmp_path / "ok")["status"] == "ok"
    with pytest.raises(RuntimeError):
        with RI.RunInfo(tmp_path / "bad"):
            raise RuntimeError("x")
    assert read(tmp_path / "bad")["status"] == "failed"


def test_a_directory_written_again_with_another_setting_keeps_the_earlier_record(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_POSERR_UNITS", "legacy")
    RI.write(tmp_path, [])
    monkeypatch.setenv("V2_POSERR_UNITS", "fixed")
    RI.write(tmp_path, [])
    r = read(tmp_path)
    assert r["mixed"] is True and r["previous"][0]["env"]["V2_POSERR_UNITS"] == "legacy" and r["env"]["V2_POSERR_UNITS"] == "fixed"
    RI.write(tmp_path, [])  # the same setting again: nothing more to record
    assert len(read(tmp_path)["previous"]) == 1


def test_the_command_line_keeps_what_begin_recorded_when_end_runs_elsewhere(tmp_path):
    base = [sys.executable, str(V2 / "benchmark" / "run_info.py")]
    subprocess.run([*base, "begin", "--out", str(tmp_path), "--input", str(V2 / "VERSION"), "--note", "shell"], env={**os.environ, "V2_POSERR_UNITS": "fixed"}, check=True)
    assert read(tmp_path)["status"] == "running"
    env = {k: v for k, v in os.environ.items() if k != "V2_POSERR_UNITS"}
    subprocess.run([*base, "end", "--out", str(tmp_path), "--status", "failed"], env=env, check=True)
    r = read(tmp_path)
    assert r["status"] == "failed" and r["env"]["V2_POSERR_UNITS"] == "fixed" and r["note"] == "shell" and r["finished_utc"]


def _tools_with_out():
    out = []
    for d in ("benchmark", "Classifier", "Preprocess", "Get_data"):
        for f in sorted((V2 / d).rglob("*.py")):
            if "tests" in f.parts or "__pycache__" in f.parts:
                continue
            s = f.read_text()
            if re.search(r'add_argument\(\s*["\']--out(-dir|dir|put)?["\']', s):
                out.append((f.relative_to(V2).as_posix(), "run_info" in s))
    return out


def test_a_tool_with_an_output_argument_writes_run_info_or_is_on_the_pending_list():
    """The rule from now on: a new measurement tool writes ``run_info.json``.  The tools that existed before are listed in benchmark/run_info_pending.txt."""
    pending = {x.strip() for x in (V2 / "benchmark" / "run_info_pending.txt").read_text().splitlines() if x.strip() and not x.startswith("#")}
    tools = dict(_tools_with_out())
    new = sorted(f for f, connected in tools.items() if not connected and f not in pending)
    assert not new, f"tools with --out that write no run_info.json (benchmark/run_info.py): {new}"
    stale = sorted(f for f in pending if f not in tools or tools[f])
    assert not stale, f"on the pending list although connected or gone, remove: {stale}"


@pytest.mark.parametrize("script", ["association_truth/run_full.sh", "association_truth/run_native_error_variants.sh"])
def test_the_shell_runners_record_their_runs(script):
    assert "run_info.py" in (V2 / "benchmark" / script).read_text()

"""The committed truth tables stay what they are (2.62.7, task 거).

The truth tables of the benchmarks are drawn from services with ``TOP`` / ``row_limit`` and no ``ORDER BY`` (WORK_REPORT_2026-11-28a.md section 2), so a rebuild gives other
objects.  ``benchmark/truth_tables_manifest.json`` records the SHA-256 of each table; these tests fail when a table changes without the manifest (a change must be a decision:
``python v2/benchmark/truth_manifest.py build`` in the same commit), and when a workflow could replace a table without anyone deciding to.
"""

import importlib.util
import json
import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

V2 = Path(__file__).resolve().parents[2]
ROOT = V2.parent
WORKFLOWS = ROOT / ".github" / "workflows"

_spec = importlib.util.spec_from_file_location("truth_manifest_tool", V2 / "benchmark" / "truth_manifest.py")
TM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TM)


def _manifest() -> dict:
    return json.loads(TM.MANIFEST.read_text())


def test_committed_truth_tables_match_the_manifest():
    problems = TM.verify(_manifest(), V2)
    assert not problems, "a truth table changed without the manifest (run `python v2/benchmark/truth_manifest.py build` if it was meant):\n" + "\n".join(problems)


def test_manifest_and_registry_list_the_same_tables_and_files():
    m = _manifest()["tables"]
    assert set(m) == set(TM.TABLES)
    for name, t in TM.TABLES.items():
        assert [f["path"] for f in m[name]["files"]] == t["files"], name
        assert (V2 / t["builder"]).exists(), f"{name}: builder {t['builder']} is gone"
        if t["workflow"]:
            assert (WORKFLOWS / t["workflow"]).exists(), f"{name}: workflow {t['workflow']} is gone"
    rows = sorted(t["survey"] for t in TM.TABLES.values() if t["survey"])
    assert sorted(set(rows)) == list(range(1, 12)), "the 11 rows of the survey table of 2026-11-28 must all be covered"


def _paired_by_names(m: dict) -> dict:
    """The manifest as the default ``verify(paired="names")`` reads it: the paired feature directories by their file names only.  The features are refreshed on
    purpose by other workflows (``recollect-ps1-features``, ``augment-ls-columns``), so their SHA-256 must not fail the repository's tests (Codex review of 2.62.7)."""
    m = json.loads(json.dumps(m))
    for t in m["tables"].values():
        t["paired"] = [dict(path=d["path"], names=sorted(f["path"] for f in d["files"])) for d in t["paired"]]
    return m


def test_build_is_deterministic_and_has_no_clock():
    a, b = TM.dumps(TM.build()), TM.dumps(TM.build())
    assert a == b
    # the committed file is what `build` writes, up to the content of the paired feature files (their names are compared)
    assert _paired_by_names(json.loads(a)) == _paired_by_names(json.loads(TM.MANIFEST.read_text()))


def test_verify_names_a_changed_value_and_a_renumbering(tmp_path):
    (tmp_path / "t.csv").write_text("benchmark_id,x\nA1,1\nA2,2\nA3,3\n")
    tables = {"t": dict(files=["t.csv"], id="benchmark_id", builder="b.py", workflow=None, paired=[], group="order_dependent", survey=1)}
    m = TM.build(tmp_path, tables)
    assert TM.verify(m, tmp_path) == []
    (tmp_path / "t.csv").write_text("benchmark_id,x\nA1,1\nA2,2\nA3,4\n")  # one value
    p = TM.verify(m, tmp_path)
    assert len(p) == 1 and "differs" in p[0] and "the same (other columns changed)" in p[0]
    (tmp_path / "t.csv").write_text("benchmark_id,x\nA2,1\nA3,2\nA4,3\n")  # renumbered
    p = TM.verify(m, tmp_path)
    assert len(p) == 1 and "different (rows added, removed or renumbered)" in p[0]
    (tmp_path / "t.csv").unlink()
    assert "missing" in TM.verify(m, tmp_path)[0]


def test_paired_directories_are_compared_by_name_unless_strict(tmp_path):
    (tmp_path / "t.csv").write_text("benchmark_id\nA1\n")
    (tmp_path / "feat").mkdir()
    (tmp_path / "feat" / "a_trd.csv").write_text("benchmark_id,v\nA1,1\n")
    tables = {"t": dict(files=["t.csv"], id="benchmark_id", builder="b.py", workflow=None, paired=["feat"], group="order_dependent", survey=1)}
    m = TM.build(tmp_path, tables)
    (tmp_path / "feat" / "a_trd.csv").write_text("benchmark_id,v\nA1,2\n")  # a column was re-collected on purpose (augment-ls-columns): the names are the same
    assert TM.verify(m, tmp_path) == []
    assert TM.verify(m, tmp_path, paired="strict") != []
    (tmp_path / "feat" / "b_trd.csv").write_text("benchmark_id\nA1\n")  # a file that the manifest does not have
    assert "other files" in TM.verify(m, tmp_path)[0]


def _protected_paths() -> list[str]:
    return ["v2/" + f for t in TM.TABLES.values() for f in t["files"]]


def _git_add_paths(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.split(" #")[0]  # a shell comment after the command
        m = re.match(r"\s*(?:\[ -d [^\]]+\] && )?git add (.*)", line)
        if m:
            out += [t.strip("\"'") for t in m.group(1).replace(";", " ").replace("||", " ").split() if not t.startswith("-") and t != "true"]
    return out


def _triggers(y: dict) -> set[str]:
    on = y.get("on", y.get(True))  # PyYAML reads the key `on` as True
    return {on} if isinstance(on, str) else set(on)


def test_workflows_that_commit_a_truth_table_run_by_hand_only():
    """A workflow that ``git add``s a committed truth table (or a directory holding one) must have no trigger but ``workflow_dispatch``: a push, a pull request or a schedule would
    rebuild a table nobody decided to rebuild (build-reference-objects.yml did, for a push to a working branch that touched the builder)."""
    protected = _protected_paths()
    bad = []
    seen = 0
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        y = yaml.safe_load(wf.read_text())
        adds = [a.rstrip("/") for job in y["jobs"].values() for s in job.get("steps", []) if "run" in s for a in _git_add_paths(s["run"])]
        hits = [a for a in adds if any(p == a or p.startswith(a + "/") for p in protected)]
        if hits:
            seen += 1
            if _triggers(y) != {"workflow_dispatch"}:
                bad.append(f"{wf.name}: triggers {sorted(_triggers(y))} but it commits {hits[:2]}")
    assert seen >= 8, "the scan should find the builder workflows of the manifest tables"
    assert not bad, "\n".join(bad)


def test_the_two_regeneration_paths_do_not_overwrite_by_default():
    """The two paths of the survey (WORK_REPORT_2026-11-28a.md 2.5): ``build-reference-objects.yml`` and ``v2_desi_external_validation.yml``."""
    ref = yaml.safe_load((WORKFLOWS / "build-reference-objects.yml").read_text())
    assert _triggers(ref) == {"workflow_dispatch"}
    inp = ref.get("on", ref.get(True))["workflow_dispatch"]["inputs"]["regenerate"]
    assert inp["default"] is False and inp["type"] == "boolean"
    steps = ref["jobs"]["build"]["steps"]
    text = json.dumps(steps)
    assert "truth_manifest.py verify --only reference_objects" in text  # the default: check the committed file
    build = next(s for s in steps if s.get("name", "").startswith("Build"))
    assert "inputs.regenerate" in build["if"] and "reference_objects_regenerated" in build["env"]["V2_REFERENCE_OBJECTS_OUT"]
    assert not re.search(r"git add v2/reference_objects(?!_regenerated)", text), "the committed table must not be added by the workflow"

    desi = yaml.safe_load((WORKFLOWS / "v2_desi_external_validation.yml").read_text())
    assert _triggers(desi) == {"workflow_dispatch"}
    inp = desi.get("on", desi.get(True))["workflow_dispatch"]["inputs"]["regenerate"]
    assert inp["default"] is False and inp["type"] == "boolean"
    jobs = desi["jobs"]
    assert "inputs.regenerate" in jobs["truth"]["if"] and "inputs.regenerate" in jobs["collect"]["if"]  # the service collection needs the explicit input
    assert "truth_manifest.py verify --only desi_external_truth" in json.dumps(jobs["verify"])
    text = json.dumps(jobs["evaluate"]["steps"])
    assert "desi_external_regenerated" in text
    assert not re.search(r"cp [^\"]*v2/benchmark/desi_external/truth\.csv", text)  # nothing is copied over the committed truth
    commit = next(s for s in jobs["evaluate"]["steps"] if s.get("name") == "Commit")["run"]
    default_add = [a for a in _git_add_paths(commit) if a != '$D']
    assert all(a.endswith(("coarse_metrics.json", "coarse_by_magnitude.csv")) for a in default_add), default_add  # default run: the two result files


def test_reference_objects_builder_redirects_with_the_environment(monkeypatch):
    spec = importlib.util.spec_from_file_location("bro_default", V2 / "benchmark" / "build_reference_objects.py")
    monkeypatch.delenv("V2_REFERENCE_OBJECTS_OUT", raising=False)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.OUT == V2 / "reference_objects"  # unchanged without the variable
    monkeypatch.setenv("V2_REFERENCE_OBJECTS_OUT", "/tmp/side")
    m2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m2)
    assert m2.OUT == Path("/tmp/side").resolve()

"""``.github/scripts/commit_frozen_truth.py`` and its workflow (2.62.8): a frozen truth list reaches v2/Classifier/truth/fixed/ only checked, and two freeze runs must agree."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".github" / "scripts" / "commit_frozen_truth.py"
WORKFLOW = ROOT / ".github" / "workflows" / "v2_commit_frozen_truth.yml"
_spec = importlib.util.spec_from_file_location("truth_deterministic_t", ROOT / "v2" / "Classifier" / "truth" / "deterministic.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)


def _list(d: Path, ids=("a", "b"), status="ok", extra=False) -> Path:
    d.mkdir(parents=True)
    df = pd.DataFrame(dict(truth_axis=["primary"] * len(ids), truth_class=["STAR"] * len(ids), truth_id=list(ids)))
    df.to_csv(d / "set1.csv", index=False)
    sets = {"set1": {"file": "set1.csv", "sha256": D.file_sha256(d / "set1.csv"), "rows": len(df), "status": status,
                     "classes": {"primary|STAR": {"rows": len(df), "ids_sha256": D.ids_sha256(df.truth_id)}}}}
    (d / "truth_manifest.json").write_text(json.dumps({"sets": sets}))
    if extra:
        (d / "work_log.txt").write_text("not part of the list")
    return d


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_a_verified_list_is_copied_with_only_its_manifest_files(tmp_path):
    a = _list(tmp_path / "a", extra=True)
    r = _run(a, "--into", tmp_path / "fixed")
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in (tmp_path / "fixed").iterdir()) == ["set1.csv", "truth_manifest.json"]
    assert "list_sha256" in r.stdout


def test_two_freeze_runs_must_give_the_same_list(tmp_path):
    same = _run(_list(tmp_path / "a"), _list(tmp_path / "b"), "--into", tmp_path / "fixed")
    assert same.returncode == 0 and "the same" in same.stdout
    diff = _run(_list(tmp_path / "c"), _list(tmp_path / "d", ids=("a", "x")), "--into", tmp_path / "fixed2")
    assert diff.returncode == 1 and "DIFFERENT" in diff.stdout and not (tmp_path / "fixed2").exists()


def test_an_incomplete_or_altered_list_is_refused(tmp_path):
    bad = _run(_list(tmp_path / "a", status="error_partial"), "--into", tmp_path / "fixed")
    assert bad.returncode != 0 and not (tmp_path / "fixed").exists()
    b = _list(tmp_path / "b")
    (b / "set1.csv").write_text("truth_axis,truth_class,truth_id\nprimary,STAR,a\n")  # changed after the manifest
    assert _run(b, "--into", tmp_path / "fixed").returncode != 0


def test_the_workflow_is_manual_refuses_main_and_downloads_the_named_runs():
    y = yaml.safe_load(WORKFLOW.read_text())
    assert set(y[True]) == {"workflow_dispatch"}  # PyYAML reads the key `on` as True
    steps = y["jobs"]["commit"]["steps"]
    assert steps[0]["if"] == "${{ github.ref_name == 'main' }}" and "exit 1" in steps[0]["run"]
    runs = [s["with"]["run-id"] for s in steps if s.get("uses", "").startswith("actions/download-artifact")]
    assert runs == ["${{ inputs.run_id }}", "${{ inputs.compare_run_id }}"]

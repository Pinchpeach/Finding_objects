"""CI runs the tests the way CLAUDE.md says (2.62.3, task 타).

CLAUDE.md names the local command ``cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests``.  CI used to run Preprocess/tests (test-preprocess.yml) and
Classifier/tests (v2_scientific_cross_validation.yml) and never app/tests, so the 17 integration tests of the app -- "the only integration test that catches an association
regression" -- ran on a developer's machine only.  These tests keep three things the same set: the command in CLAUDE.md, the command of ``.github/workflows/unit-tests.yml`` and the
folders named ``tests`` under v2.
"""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
V2 = REPO / "v2"
WORKFLOW = REPO / ".github" / "workflows" / "unit-tests.yml"
SCRIPT = REPO / ".github" / "scripts" / "assert_no_skips.py"


def _claude_md_folders() -> set[str]:
    m = re.search(r"`cd v2 && python -m pytest -q ([^`]+)`", (REPO / "CLAUDE.md").read_text(encoding="utf-8"))
    assert m, "CLAUDE.md no longer names the local test command (cd v2 && python -m pytest -q ...)"
    return {t for t in m.group(1).split() if not t.startswith("-")}


def _workflow_folders(path: Path) -> set[str]:
    """Folders of the pytest command of a workflow, relative to v2 (``working-directory: v2`` or a ``v2/`` prefix)."""
    text = path.read_text(encoding="utf-8")
    out = set()
    for line in text.splitlines():
        s = line.strip().removeprefix("run: ")
        if "pytest" in s and "pip install" not in s and "tests" in s and not s.startswith("#"):
            for t in s.split():
                if t.endswith("tests") and not t.startswith("-"):
                    out.add(t.removeprefix("v2/"))
    return out


def test_ci_runs_the_folders_claude_md_names():
    assert _workflow_folders(WORKFLOW) == _claude_md_folders() == {"Preprocess/tests", "Classifier/tests", "app/tests"}


def test_the_workflow_runs_from_v2_like_the_local_command():
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text[text.index("Tests (the command of CLAUDE.md)"):]
    assert "working-directory: v2" in step.split("- name:")[0]  # tests such as test_host_groups depend on the working directory


def test_every_tests_folder_of_v2_is_in_that_set():
    """A new folder of tests that nobody adds to CLAUDE.md and the workflow would run nowhere."""
    found = {str(p.parent.relative_to(V2)) for p in V2.rglob("test_*.py") if p.parent.name == "tests" and "__pycache__" not in p.parts}
    assert found == _claude_md_folders(), f"tests folders under v2 {sorted(found)} differ from the CLAUDE.md command {sorted(_claude_md_folders())}"


def test_the_other_workflows_run_only_folders_of_the_set():
    """test-preprocess.yml and the cross-validation workflow run a subset on their own triggers; none runs a tests folder the set does not name."""
    allowed = _claude_md_folders()
    for f in (REPO / ".github" / "workflows").glob("*.yml"):
        for folder in _workflow_folders(f):
            assert folder in allowed, f"{f.name} runs {folder}, which CLAUDE.md does not name"


def test_the_junit_check_asks_for_the_same_folders():
    text = WORKFLOW.read_text(encoding="utf-8")
    required = re.search(r"assert_no_skips\.py unit-tests\.xml --require ([^\n]+)", text).group(1).split()
    assert set(required) == {f.replace("/", ".") for f in _claude_md_folders()}


def _junit(tmp_path, cases):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for cls, name, skipped in cases:
        tc = ET.SubElement(suite, "testcase", classname=cls, name=name)
        if skipped:
            ET.SubElement(tc, "skipped", message="could not import 'PySide6'")
    p = tmp_path / "r.xml"
    ET.ElementTree(root).write(p)
    return p


def _run(p, *require):
    return subprocess.run([sys.executable, str(SCRIPT), str(p), "--require", *require], capture_output=True, text=True)


def test_assert_no_skips_passes_a_complete_run(tmp_path):
    p = _junit(tmp_path, [("v2.Preprocess.tests.test_a", "t1", False), ("v2.Classifier.tests.test_b", "t2", False), ("v2.app.tests.test_app", "t3", False)])
    r = _run(p, "Preprocess.tests", "Classifier.tests", "app.tests")
    assert r.returncode == 0 and "3 tests, none skipped" in r.stdout


def test_assert_no_skips_fails_on_a_skipped_app_test(tmp_path):
    """No Qt on the runner: app/tests call importorskip('PySide6') and would be reported as skipped, not failed."""
    p = _junit(tmp_path, [("v2.Preprocess.tests.test_a", "t1", False), ("v2.app.tests.test_app", "t3", True)])
    r = _run(p, "Preprocess.tests", "app.tests")
    assert r.returncode == 1 and "app.tests.test_app::t3" in r.stdout


def test_assert_no_skips_fails_when_a_folder_collected_nothing(tmp_path):
    p = _junit(tmp_path, [("v2.Preprocess.tests.test_a", "t1", False)])
    r = _run(p, "Preprocess.tests", "app.tests")
    assert r.returncode == 1 and "no test of app.tests" in r.stdout

#!/usr/bin/env python3
"""Which tests the workflows really run, against the tests that exist (2.61.9, workflows run from v2 understood in 2.62.3).

    python ci_test_inventory.py --out ci_test_inventory.csv

For every folder / file of tests under ``v2``: how many tests pytest collects, how many ``unittest discover`` collects (only ``unittest.TestCase``
classes; the function-style tests of pytest are silently skipped) and which workflow commands name it.  A workflow step is read from the
``.github/workflows`` files: a ``run:`` line with ``pytest`` or ``unittest`` and a ``v2/...`` path.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
V2 = REPO / "v2"


def pytest_count(target: Path) -> int:
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", str(target)], cwd=REPO, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", r.stdout + r.stderr)
    return int(m.group(1)) if m else 0


def unittest_count(folder: Path) -> int:
    suite = unittest.TestLoader().discover(str(folder), top_level_dir=str(folder))
    return suite.countTestCases()


def workflow_commands() -> list[tuple[str, str]]:
    out = []
    for f in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = f.read_text(encoding="utf-8")
        in_v2 = "working-directory: v2\n" in text or "working-directory: v2\r" in text  # unit-tests.yml runs from v2 like CLAUDE.md (2.62.3)
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            cmd = line.strip().removeprefix("run: ")
            if ("pytest" in line or "unittest" in line) and "pip install" not in line and ("v2/" in line or (in_v2 and "tests" in line)):
                if in_v2 and "v2/" not in cmd:  # paths relative to v2: name them as the table does
                    cmd = " ".join(("v2/" + t) if ("/" in t and not t.startswith(("-", "v2/", ".."))) else t for t in cmd.split())
                out.append((f.name, cmd))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cmds = workflow_commands()
    targets = [V2 / "Preprocess" / "tests", V2 / "Classifier" / "tests", V2 / "app" / "tests", V2 / "Classifier" / "test_star_diverse.py"]
    rows = []
    for t in targets:
        rel = str(t.relative_to(REPO))
        used = [(w, c) for w, c in cmds if rel in c]
        rows.append(
            dict(
                target=rel,
                pytest_collects=pytest_count(t),
                unittest_discover_collects=unittest_count(t) if t.is_dir() else None,
                workflow_runs_it="; ".join(f"{w}: {c}" for w, c in used) or "no workflow",
                tests_run_by_ci=("pytest_collects" if any("pytest" in c for _, c in used) else ("unittest_discover_collects" if used else "none")),
            )
        )
    t = pd.DataFrame(rows)
    t["tests_run_by_ci"] = [int(r[r.tests_run_by_ci]) if r.tests_run_by_ci != "none" else 0 for _, r in t.iterrows()]
    t.to_csv(a.out, index=False)
    with pd.option_context("display.width", 250, "display.max_colwidth", 90):
        print(t.to_string(index=False))
    print(f"\nexist (pytest): {int(t.pytest_collects.sum())}   run by CI: {int(t.tests_run_by_ci.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

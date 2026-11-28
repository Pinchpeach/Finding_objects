#!/usr/bin/env python3
"""Fail a test run that skipped a test or lost a whole test folder (2.62.3).

    python assert_no_skips.py unit-tests.xml --require Preprocess.tests Classifier.tests app.tests

``pytest --junitxml`` writes one ``testcase`` per test.  Two silences are made loud here: (1) a skipped test -- ``app/tests`` calls ``pytest.importorskip("PySide6")``, so a runner
without Qt would report them as skipped, not failed, and the 17 integration tests of the app would not have run; (2) a folder that contributed no test at all (a path typo
in the pytest command would collect 0 tests of it and still pass).  Exit status 1 with the offending tests listed; 0 and a one-line summary otherwise.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter


def check(path: str, require: list[str]) -> tuple[list[str], Counter]:
    root = ET.parse(path).getroot()
    skipped, per_folder = [], Counter()
    for tc in root.iter("testcase"):
        cls = tc.get("classname", "")
        for folder in require:
            if f".{folder}" in f".{cls}" or cls.startswith(folder):
                per_folder[folder] += 1
        if tc.find("skipped") is not None:
            skipped.append(f"{cls}::{tc.get('name')}  ({(tc.find('skipped').get('message') or '').strip()[:100]})")
    problems = list(skipped)
    problems += [f"no test of {folder} in the report" for folder in require if per_folder[folder] == 0]
    return problems, per_folder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("junit")
    ap.add_argument("--require", nargs="*", default=[], help="folders (dotted, as in the junit classname) that must contribute at least one test")
    a = ap.parse_args()
    problems, per_folder = check(a.junit, a.require)
    total = sum(1 for _ in ET.parse(a.junit).getroot().iter("testcase"))
    if problems:
        print(f"FAILED: {len(problems)} problem(s) in {a.junit} ({total} tests)")
        for p in problems:
            print("  -", p)
        return 1
    print(f"ok: {total} tests, none skipped; " + ", ".join(f"{k}: {v}" for k, v in per_folder.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

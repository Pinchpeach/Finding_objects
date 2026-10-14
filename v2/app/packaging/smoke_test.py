#!/usr/bin/env python3
"""Smoke test of a frozen Finding Objects build (no network).

Runs the bundled executable in ``--pipeline`` worker mode on the committed
NGC 4522 raw catalogues, checks that progress lines reach stdout (the GUI
reads them; a windowed build starts without stdout) and that the result is
identical to the same pipeline run from source.

    python v2/app/packaging/smoke_test.py dist/FindingObjects/FindingObjects[.exe]
"""

from __future__ import annotations
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def main() -> int:
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        frozen, source = Path(tmp) / "frozen", Path(tmp) / "source"
        p = subprocess.run(
            [str(exe), "--pipeline", "--raw-dir", str(V2 / "rawdata"), "--work", str(frozen)],
            capture_output=True,
            text=True,
            timeout=900,
        )
        print(p.stdout[-2000:], p.stderr[-2000:], sep="\n")
        assert p.returncode == 0, f"frozen pipeline exit code {p.returncode}"
        assert "[pipeline]" in p.stdout, "no progress on stdout (GUI progress would stay empty)"
        subprocess.run(
            [sys.executable, str(V2 / "pipeline.py"), "--raw-dir", str(V2 / "rawdata"), "--work", str(source)],
            check=True,
            capture_output=True,
            timeout=900,
        )
        a = pd.read_csv(frozen / "classified_objects.csv", low_memory=False).fillna("").astype(str)
        b = pd.read_csv(source / "classified_objects.csv", low_memory=False).fillna("").astype(str)
        assert len(a) > 0, "no objects classified"
        assert a.equals(b), "frozen result differs from the source run"
        print(f"OK: {len(a)} objects, identical to the source run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

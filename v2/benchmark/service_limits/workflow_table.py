#!/usr/bin/env python3
"""Which workflow jobs ask NED and the SDSS SkyServer, and how many at once (2.60.7).

    python v2/benchmark/service_limits/workflow_table.py [CHECKOUT] > v2/benchmark/service_limits/workflows_2026-11-25.md

Reads ``.github/workflows/*.yml``: for every job that runs the collectors (``pipeline.py --ra``, ``controller.py
--ra``, ``validate_reference_objects.py run``) it prints the matrix size, ``max-parallel`` as written, whether the job
(or a step) sets ``V2_SKIP_COLLECTORS`` and with which value, and what that means for NED and for the SkyServer.
Per search (2.60.2 logs, three fields): NED 1 request, SkyServer 4-7 requests (``sdss_dr18`` 3-4, ``sdss_spectroscopy`` 1-3),
SIMBAD 2-3 requests; the 3-5 s pause before every request is per process.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RUNS = re.compile(r"pipeline\.py --ra|controller\.py --ra|validate_reference_objects\.py run")
SERVICES_PER_SEARCH = {"ned": 1, "skyserver": (4, 7), "skyserver_spectra_part": (1, 3)}


def matrix_size(job) -> int | str:
    m = (job.get("strategy") or {}).get("matrix")
    if isinstance(m, dict):
        sizes = [len(v) for v in m.values() if isinstance(v, list)]
        if sizes:
            return max(sizes)
        return "dynamic"
    return 1


def skip_value(job) -> str:
    text = yaml.safe_dump(job)
    m = re.search(r"V2_SKIP_COLLECTORS: (.+)", text)
    return m.group(1).strip().strip("'\"") if m else ""


def rows(root: Path = ROOT):
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        y = yaml.safe_load(path.read_text())
        for name, job in (y.get("jobs") or {}).items():
            body = "\n".join(str(s.get("run", "")) for s in job.get("steps") or [] if isinstance(s, dict))
            if not RUNS.search(body):
                continue
            n = matrix_size(job)
            mp = (job.get("strategy") or {}).get("max-parallel", "")
            sv = skip_value(job)
            yield path.name, name, n, mp, sv


def meaning(n, mp, sv) -> str:
    if n == 1:
        return "single job"
    if "blind" in sv:
        return "NED, SIMBAD, SDSS spectra and the other blind-dropped collectors are not asked"
    if "ned" in sv:
        return "NED not asked unless `with_ned=true` (then one job at a time)"
    if str(mp).strip() == "1":
        return "NED asked, one job at a time"
    return "**NED asked by up to " + (str(mp) if mp else "all") + " jobs at once**"


def main() -> int:
    root = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    )  # a checkout of another version (for a before / after table)
    print("| workflow | job | matrix | max-parallel | V2_SKIP_COLLECTORS | NED |")
    print("|---|---|---|---|---|---|")
    for wf, job, n, mp, sv in rows(root):
        mp_txt = (
            re.sub(r"\$\{\{ .*with_ned == 'true' && (\d+) \|\| (\d+) \}\}", r"\1 with `with_ned`, else \2", str(mp))
            if mp
            else "-"
        )
        sv_txt = "`ned` unless `with_ned=true`" if "with_ned" in sv else (f"`{sv}`" if sv else "-")
        print(f"| `{wf}` | `{job}` | {n} | {mp_txt} | {sv_txt} | {meaning(n, mp, sv)} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())

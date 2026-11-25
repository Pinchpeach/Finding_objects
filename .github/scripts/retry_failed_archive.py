"""Ask a failed archive of a collected field again, once, inside the same workflow job (2.60.10).

    python .github/scripts/retry_failed_archive.py RAW_ROOT RA DEC RADIUS [--only desi_legacy] [--wait 120]

RAW_ROOT is the ``--work`` folder of ``v2/pipeline.py`` (its ``raw/<tag>/`` holds the collected csv files and
``collection_summary_*.csv``).  When one of the ``--only`` collectors is among the failed key archives, the job waits
``--wait`` seconds (the 2026-11-25 Data Lab outages lasted minutes: 09:19-09:21 and 09:32-09:41 UTC, HTTP 502) and
asks that collector again through ``controller.retry_failed`` -- the same one retry a user gets with
``pipeline.py --retry-failed``.  The collection summary is rewritten, so whatever reads it later (the blind copy, the
set-C archive-health gate) sees the outcome of the retry; the gate itself is not changed.  A healthy day asks nothing.
It never fails the job: a collector that still fails stays failed in the summary, which is what the gate counts.
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_controller():
    sys.path.insert(0, str(ROOT / "v2" / "Get_data"))
    spec = importlib.util.spec_from_file_location("v2_controller_retry", ROOT / "v2" / "Get_data" / "controller.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    return ctl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("ra", type=float)
    ap.add_argument("dec", type=float)
    ap.add_argument("radius", type=float)
    ap.add_argument("--only", default="desi_legacy", help="comma list of collectors worth waiting for")
    ap.add_argument("--wait", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    ctl = load_controller()
    raws = sorted(p for p in (a.work / "raw").glob("*") if p.is_dir())
    if not raws:
        print("[retry] no collected field in", a.work)
        return 0
    only = tuple(x for x in a.only.split(",") if x)
    todo = [n for n in ctl.failed_collectors(raws[0], "key") if n in only]
    print("[retry] failed key archives to ask again:", todo or "none", flush=True)
    if not todo:
        return 0
    time.sleep(max(0.0, a.wait))
    ctl.retry_failed(raws[0], a.ra, a.dec, a.radius, a.workers, "key", only=only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

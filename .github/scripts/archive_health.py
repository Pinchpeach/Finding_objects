#!/usr/bin/env python3
"""Archive health check before long validation runs (2.51.1).

On 2026-11-11 VizieR (404) and NOIRLab Legacy Surveys (502) were down for
hours and every field run of the day silently lost AllWISE / 2MASS or Legacy
Surveys (WORK_REPORT_2026-11-11.md 3.4).  This runs the real collectors on one
small cone where every core survey has data (COSMOS centre, 3') and exits 1
when any core collector errors, times out or returns no rows, so a workflow can
stop before spending hours (and, for locked set C, the release's single look)
on degraded data.

    python .github/scripts/archive_health.py [--ra 150.12 --dec 2.21 --radius 3]
"""

import argparse
import glob
import subprocess
import sys

import pandas as pd

CORE = ["gaia_dr3", "desi_legacy", "panstarrs1", "allwise", "twomass"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", type=float, default=150.12)
    ap.add_argument("--dec", type=float, default=2.21)
    ap.add_argument("--radius", type=float, default=3.0)
    a = ap.parse_args()
    subprocess.run([sys.executable, "-u", "v2/Get_data/controller.py", "--ra", str(a.ra), "--dec", str(a.dec),
                    "--radius", str(a.radius), "--out-dir", "/tmp/health", "--workers", "6"], check=False)
    files = glob.glob("/tmp/health/**/collection_summary_*.csv", recursive=True)
    if not files:
        sys.exit("archive health: no collection summary written")
    s = pd.read_csv(files[0]).set_index("collector")
    bad = {c: f"{s.status.get(c, 'missing')} ({int(s.rows.get(c, 0))} rows)" for c in CORE
           if s.status.get(c, "missing") != "ok" or int(s.rows.get(c, 0)) == 0}
    print(s[["status", "rows", "elapsed_seconds"]].to_string())
    if bad:
        sys.exit(f"archive health: core collectors unhealthy: {bad}")
    print("archive health: all core collectors ok")


if __name__ == "__main__":
    main()

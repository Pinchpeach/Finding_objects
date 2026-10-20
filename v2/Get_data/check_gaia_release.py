#!/usr/bin/env python3
"""Check a Gaia release on the ESA archive against what the collector needs
(2.9.0).  Lists, per table, the columns gaia_dr3.py requests that the archive
does not have, and the reference epoch the archive reports.

    python v2/Get_data/check_gaia_release.py --release DR4

Exit code 1 if a table or a required column is missing, so the switch to a
new release (``V2_GAIA_RELEASE``) is a checked step, not a guess.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaia_dr3 as g  # noqa: E402
import throttle  # noqa: E402
from gaia_release import RELEASES, table  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

NEEDED = {
    "gaia_source": g.SOURCE,
    "astrophysical_parameters": g.AP + g.SPEC_AP,
    "vari_classifier_result": ["best_class_name", "best_class_score"],
    "vari_summary": g.VAR_SUMMARY,
}


def main() -> None:
    from astroquery.gaia import Gaia

    p = argparse.ArgumentParser()
    p.add_argument("--release", default="DR4", choices=sorted(RELEASES))
    a = p.parse_args()
    rel = RELEASES[a.release]
    bad = False
    for name, cols in NEEDED.items():
        t = table(rel, name)
        try:
            meta = Gaia.load_table(t)
        except Exception as exc:
            print(f"{t}: NOT AVAILABLE ({type(exc).__name__}: {str(exc)[:120]})")
            bad = True
            continue
        have = {c.name.lower() for c in meta.columns}
        missing = [c for c in cols if c.lower() not in have]
        print(f"{t}: {len(have)} columns; missing {len(missing)}: {missing}")
        bad |= bool(missing)
    try:
        r = Gaia.launch_job(f"SELECT TOP 1 ref_epoch FROM {table(rel, 'gaia_source')}").get_results()
        ep = float(r["ref_epoch"][0])
        print(f"ref_epoch on archive: {ep}; gaia_release.py: {rel.ref_epoch}")
        bad |= abs(ep - rel.ref_epoch) > 1e-6
    except Exception as exc:
        print("ref_epoch query failed:", str(exc)[:120])
        bad = True
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

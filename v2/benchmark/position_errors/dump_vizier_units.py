#!/usr/bin/env python3
"""Print the unit and description VizieR itself stores for the position-error columns (2.62.2).

    python dump_vizier_units.py [--out FILE.csv]

Needs the network (astroquery -> VizieR); the cloud session of this study cannot reach ``cdsarc``, so this is for a workflow or a desktop run.  For each
catalogue it queries one small cone where the survey has sources and writes, per column named below, the ``unit`` and ``description`` of the returned table.
It exists to turn the "none" evidence entries of ``UNITS.md`` into the documented unit.
"""

from __future__ import annotations

import argparse
import sys

# catalogue -> (cone centre RA, Dec in deg, radius deg, columns whose unit is wanted)
TARGETS = {
    # 0.5 deg (2.62.3): the 0.1 deg COSMOS cone held no VLASS row (run 46087889093), and an empty answer carries no column metadata
    "J/ApJS/255/30": (150.1, 2.2, 0.5, ["e_RAJ2000", "e_DEJ2000", "e_RAMdeg", "e_DEMdeg", "RAJ2000", "Maj", "e_Maj"]),
    "VIII/65/nvss": (150.1, 2.2, 0.5, ["e_RAJ2000", "e_DEJ2000", "RAJ2000", "DEJ2000"]),
    "J/A+A/659/A1": (190.0, 55.0, 0.3, ["e_RAJ2000", "e_DEJ2000", "RAJ2000"]),
    "J/A+A/598/A78": (150.1, 2.2, 0.5, ["e_RAJ2000", "e_DEJ2000"]),
    "II/335/galex_ais": (150.1, 2.2, 0.1, ["Nerr", "Ferr", "Ierr", "Nperr", "Fperr", "Sep"]),
    "II/328/allwise": (150.1, 2.2, 0.1, ["eeMaj", "eeMin", "e_RA_pm", "e_DE_pm"]),
    "II/246/out": (150.1, 2.2, 0.1, ["errMaj", "errMin"]),
    "IX/57/csc2master": (150.1, 2.2, 0.2, ["r0", "r1", "PA"]),
    "J/A+A/682/A34": (150.1, 2.2, 0.5, ["posErr", "RADEErr", "e_RA_ICRS", "E_RA_ICRS"]),
    "IX/69/xmm4d13s": (150.1, 2.2, 0.2, ["ePos"]),
    "VIII/92/first14": (150.1, 2.2, 0.2, ["Rms", "Maj", "Min"]),
}


def describe(table, columns) -> list[dict]:
    """(column, unit, description) of ``columns`` that exist in the astropy table, in the order asked."""
    out = []
    for c in columns:
        if c in table.colnames:
            col = table[c]
            out.append(dict(column=c, unit=str(col.unit) if col.unit is not None else "", description=str(col.description or "")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="vizier_units.csv")
    a = ap.parse_args()
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Get_data"))
    import throttle  # VizieR mirror failover (CfA, NAOJ, IDIA, ...): a Strasbourg outage must not stop the check (2.62.2)

    throttle.install()
    import astropy.units as u
    import pandas as pd
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    rows = []
    for cat, (ra, dec, rad, cols) in TARGETS.items():
        try:
            res = Vizier(columns=["**"], row_limit=3).query_region(SkyCoord(ra, dec, unit="deg"), radius=rad * u.deg, catalog=cat)
        except Exception as e:  # noqa: BLE001
            rows.append(dict(catalog=cat, table="", column="", unit="", description=f"QUERY FAILED: {e}"))
            continue
        for t in res:
            for d in describe(t, cols):
                rows.append(dict(catalog=cat, table=t.meta.get("name", ""), **d))
        if not len(res):
            rows.append(dict(catalog=cat, table="", column="", unit="", description="NO ROWS in the cone"))
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

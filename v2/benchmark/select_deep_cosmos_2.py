#!/usr/bin/env python3
"""A second set of deep COSMOS fields for the faint-QSO candidate measurement (2.59.0 preparation).

Why.  The faint QSO candidate flag of 2.58.0 (secondary_class = QSO, FAINT_QSO_CANDIDATE) is measured on the nine
deep_cosmos fields: 63 Chandra type-1 AGN at 22 <= LS r < 24, 21 of them in the test fields.  The test-field
purity 0.21 (Wilson 95 % 0.10-0.37) and recall 0.33 (0.17-0.55) are wide because of that sample size, not
because of the threshold.  More fields from the same sky, measured the same way, narrow them.

The rule (fixed here, before any new field is collected or classified; the output file's SHA-256 is recorded in
DEEP_COSMOS_EXPANSION.md and the collection workflow refuses a changed file):

  1. Grid.  Centres on a square grid anchored at the COSMOS centre (RA 150.12, Dec 2.21), steps GRID_STEP_DEG in
     Dec and GRID_STEP_DEG / cos(Dec) in RA, indices -MAX_INDEX..MAX_INDEX.  Radius 6' as the first nine.
  2. No overlap.  A centre closer than GRID_STEP_DEG (12.6' = 2 x 6' + 0.6') to a centre of the nine existing
     fields (measure_cosmos_xray_agn.FIELDS) is dropped; two grid centres are GRID_STEP_DEG apart at least.
  3. Coverage by the truth.  The 5.75' disc (6' minus the 0.25' edge cut of the measurement) must hold at least
     MIN_COVERAGE x the median number of Chandra COSMOS Legacy sources of the nine existing discs (Chandra
     Legacy covers 2.2 deg^2, deepest in the centre).  --check also asks the archives and applies the same
     fraction to the COSMOS2020 Classic counts and to the Legacy Surveys DR10 objects of the disc, so a disc
     that falls outside either is dropped.  These are source counts of the truth and of the imaging; no
     classifier output enters the selection.
  4. Order and names.  By distance from the anchor, then RA; deep_cosmos_10, 11, ... .
  5. Split.  The parity rule of 2.52.0: odd number = calibration, even = test.  (The nine existing fields keep
     theirs.)  See DEEP_COSMOS_EXPANSION.md for what the new fields are used for.

    python v2/benchmark/select_deep_cosmos_2.py [--check]

writes v2/benchmark/deep_cosmos_fields_2.csv.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
OUT = B / "deep_cosmos_fields_2.csv"
TRUTH = B / "cosmos_xray_agn" / "chandra_cosmos_legacy_ids.csv.gz"
ANCHOR = (150.12, 2.21)
GRID_STEP_DEG = 0.21
MAX_INDEX = 5
RADIUS_ARCMIN, EDGE_ARCMIN = 6.0, 0.25
MIN_COVERAGE = 0.6
FIRST_NUMBER = 10
EXISTING = {
    "deep_cosmos_1": (149.85, 1.95),
    "deep_cosmos_2": (149.85, 2.21),
    "deep_cosmos_3": (149.85, 2.47),
    "deep_cosmos_4": (150.12, 1.95),
    "deep_cosmos_5": (150.12, 2.21),
    "deep_cosmos_6": (150.12, 2.47),
    "deep_cosmos_7": (150.39, 1.95),
    "deep_cosmos_8": (150.39, 2.21),
    "deep_cosmos_9": (150.39, 2.47),
}  # same as measure_cosmos_xray_agn.FIELDS and experiment-ab-fields.yml


def sep_deg(ra1, de1, ra2, de2):
    a, d = np.radians(ra1), np.radians(de1)
    b, e = np.radians(ra2), np.radians(de2)
    x = np.sin((e - d) / 2) ** 2 + np.cos(d) * np.cos(e) * np.sin((b - a) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(x, 0, 1))))


def chandra_positions() -> tuple[np.ndarray, np.ndarray]:
    t = pd.read_csv(TRUTH)
    return t.RAOdeg.fillna(t.RAJ2000).to_numpy(float), t.DEOdeg.fillna(t.DEJ2000).to_numpy(float)


def count_within(ra, dec, ras, decs, arcmin):
    return int((sep_deg(ra, dec, ras, decs) <= arcmin / 60.0).sum())


def candidates() -> pd.DataFrame:
    ras, decs = chandra_positions()
    cut = RADIUS_ARCMIN - EDGE_ARCMIN
    base = np.array([count_within(ra, de, ras, decs, cut) for ra, de in EXISTING.values()])
    floor = MIN_COVERAGE * float(np.median(base))
    rows = []
    for i in range(-MAX_INDEX, MAX_INDEX + 1):
        for j in range(-MAX_INDEX, MAX_INDEX + 1):
            dec = ANCHOR[1] + j * GRID_STEP_DEG
            ra = ANCHOR[0] + i * GRID_STEP_DEG / math.cos(math.radians(dec))
            gap = min(float(sep_deg(ra, dec, r0, d0)) for r0, d0 in EXISTING.values())
            n = count_within(ra, dec, ras, decs, cut)
            rows.append(
                {
                    "i": i,
                    "j": j,
                    "ra": round(ra, 5),
                    "dec": round(dec, 5),
                    "gap_to_existing_deg": round(gap, 4),
                    "n_chandra": n,
                    "distance_deg": float(sep_deg(ra, dec, *ANCHOR)),
                }
            )
    c = pd.DataFrame(rows)
    keep = c[(c.gap_to_existing_deg >= GRID_STEP_DEG - 1e-9) & (c.n_chandra >= floor)].copy()
    keep.attrs["floor"], keep.attrs["median_existing"] = floor, float(np.median(base))
    return keep.sort_values(["distance_deg", "ra"]).reset_index(drop=True)


def check_archives(df: pd.DataFrame) -> pd.DataFrame:
    """COSMOS2020 Classic and Legacy Surveys DR10 counts of every disc (needs the archives)."""
    import sys

    sys.path.insert(0, str(B.parent / "Get_data"))
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    import desi_legacy as ls

    out = df.copy()
    cut = RADIUS_ARCMIN - EDGE_ARCMIN
    n_cos, n_ls = [], []
    for r in df.itertuples():
        v = Vizier(columns=["_RAJ2000"], row_limit=-1)
        t = v.query_region(
            SkyCoord(r.ra * u.deg, r.dec * u.deg), radius=cut * u.arcmin, catalog="J/ApJS/258/11/classic"
        )
        n_cos.append(0 if not t else len(t[0]))
        n_ls.append(len(ls._viewer_fetch(r.ra, r.dec, cut)))
    out["n_cosmos2020"], out["n_ls"] = n_cos, n_ls
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--check", action="store_true", help="also count COSMOS2020 and Legacy Surveys objects (needs the archives)"
    )
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    c = candidates()
    print(
        f"grid {2 * MAX_INDEX + 1}^2 = {(2 * MAX_INDEX + 1) ** 2} points; Chandra floor {c.attrs['floor']:.1f} "
        f"(median of the nine existing discs {c.attrs['median_existing']:.0f}); {len(c)} kept"
    )
    if a.check:
        c = check_archives(c)
        m_cos, m_ls = c.n_cosmos2020.median(), c.n_ls.median()
        c = c[(c.n_cosmos2020 >= MIN_COVERAGE * m_cos) & (c.n_ls >= MIN_COVERAGE * m_ls)].reset_index(drop=True)
        print(
            f"after the archive counts (>= {MIN_COVERAGE} x the median: COSMOS2020 {m_cos:.0f}, LS {m_ls:.0f}): {len(c)} kept"
        )
    c.insert(0, "name", [f"deep_cosmos_{FIRST_NUMBER + k}" for k in range(len(c))])
    c["r"] = RADIUS_ARCMIN
    c["split"] = ["cal" if (FIRST_NUMBER + k) % 2 else "test" for k in range(len(c))]
    cols = ["name", "ra", "dec", "r", "split", "n_chandra"] + [k for k in ("n_cosmos2020", "n_ls") if k in c]
    c[cols].to_csv(a.out, index=False)
    print(c[cols].to_string(index=False))
    print("sha256", hashlib.sha256(a.out.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

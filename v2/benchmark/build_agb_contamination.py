#!/usr/bin/env python3
"""Sample of AGB-gate stars for measuring non-AGB contamination.

The photometric AGB chemistry of Classifier/subclass.py is applied to every
"AGB candidate", and the commonest way in is membership of the Gaia DR3
long-period-variable catalogue (Lebzelter et al. 2023, VizieR I/358/vlpv).
That catalogue also holds red giants below the RGB tip, red supergiants and
young stellar objects (Mowlavi et al. 2018 for DR2).  The Suh (2021) truth set
contains AGB stars only, so it cannot show how often such stars are
labelled AGB.  This script collects an unbiased sample of the gate:

* Gaia DR3 LPV stars inside ``--cones`` random 1-degree cones (uniform on the
  sky, fixed seed), with is_cstar / frequency / amplitude;
* Gaia DR3 G, BP, RP, parallax; 2MASS J, H, Ks; AllWISE W1-W4 (nearest
  source, VizieR multi-position cone search as in build_agb_chemistry_truth);
* SIMBAD main type and spectral type (nearest within 3", TAP upload).

Contamination truth is (a) the SIMBAD type and (b) the Gaia absolute Ks
magnitude against the RGB tip.  Output:
v2/benchmark/agb_truth/agb_gate_sample.csv.gz
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_agb_chemistry_truth import ASU_CATALOGS, retry, vizier_asu  # noqa: E402

SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap"
SIMBAD_Q = """SELECT t.agb_id, b.main_id, b.otype, b.sp_type,
 DISTANCE(POINT('ICRS', b.ra, b.dec), POINT('ICRS', t.ra, t.dec)) * 3600 AS simbad_sep
 FROM TAP_UPLOAD.t AS t JOIN basic AS b
 ON 1 = CONTAINS(POINT('ICRS', b.ra, b.dec), CIRCLE('ICRS', t.ra, t.dec, 3.0 / 3600))"""


def lpv_cones(n: int, radius_deg: float, seed: int) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    rng = np.random.default_rng(seed)
    ra = rng.uniform(0, 360, n)
    dec = np.degrees(np.arcsin(rng.uniform(-1, 1, n)))       # uniform on the sphere
    v = Vizier(columns=["Source", "RA_ICRS", "DE_ICRS", "isCstar", "Freq", "Amp"], row_limit=-1, timeout=600)
    parts = []
    for i, (r, d) in enumerate(zip(ra, dec)):
        t0 = time.time()
        try:
            res = retry(lambda: v.query_region(SkyCoord(r * u.deg, d * u.deg), radius=radius_deg * u.deg,
                                               catalog="I/358/vlpv"), tries=3, wait=20)
        except Exception as exc:
            print(f"cone {i}: failed {str(exc)[:150]}", flush=True)
            continue
        if res:
            t = res[0].to_pandas()
            t["cone"] = i
            parts.append(t)
        print(f"cone {i} ({r:.1f}, {d:+.1f}): {len(parts[-1]) if res else 0} LPVs in {time.time() - t0:.0f} s", flush=True)
    df = pd.concat(parts, ignore_index=True).drop_duplicates("Source")
    df = df.rename(columns={"Source": "lpv_source_id", "RA_ICRS": "ra", "DE_ICRS": "dec", "isCstar": "lpv_is_cstar",
                            "Freq": "lpv_frequency", "Amp": "lpv_amplitude"})
    df.insert(0, "agb_id", np.arange(len(df)))
    return df


def simbad(df: pd.DataFrame, chunk: int = 2000) -> pd.DataFrame:
    import pyvo
    from astropy.table import Table
    svc = pyvo.dal.TAPService(SIMBAD_TAP)
    parts = []
    for s0 in range(0, len(df), chunk):
        up = Table.from_pandas(df.iloc[s0:s0 + chunk][["agb_id", "ra", "dec"]])
        t0 = time.time()
        try:
            r = retry(lambda: svc.run_sync(SIMBAD_Q, uploads={"t": up}, maxrec=10 * chunk).to_table().to_pandas(),
                      tries=3, wait=30)
        except Exception as exc:
            print(f"simbad rows {s0}+: failed {str(exc)[:200]}", flush=True)
            continue
        parts.append(r.sort_values("simbad_sep").drop_duplicates("agb_id"))
        print(f"simbad rows {s0}-{s0 + len(up)}: {len(parts[-1])} matched in {time.time() - t0:.0f} s", flush=True)
    if not parts:
        return df
    s = pd.concat(parts, ignore_index=True)
    for c in ("main_id", "otype", "sp_type"):
        s[c] = s[c].astype(str).str.strip()
    return df.merge(s.rename(columns={"main_id": "simbad_main_id", "otype": "simbad_otype", "sp_type": "simbad_sp_type"}),
                    on="agb_id", how="left")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cones", type=int, default=80)
    p.add_argument("--radius", type=float, default=1.0, help="cone radius, degrees")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "agb_truth" / "agb_gate_sample.csv.gz")
    a = p.parse_args()
    df = lpv_cones(a.cones, a.radius, a.seed)
    print(f"{len(df)} Gaia DR3 LPVs in {df.cone.nunique()} cones", flush=True)
    df = vizier_asu(df, catalogs={k: ASU_CATALOGS[k] for k in ("gaia", "2mass", "allwise")})
    df = simbad(df)
    phot = [c for c in df.columns if c.startswith(("g_", "tm_", "aw_"))]
    if not phot or df[phot].notna().any(axis=1).mean() < 0.2:
        raise SystemExit(f"photometry missing for most stars ({phot}); not writing {a.out}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(df.shape, "->", a.out)
    if "simbad_otype" in df:
        print(df.simbad_otype.value_counts().head(40).to_string())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Radio properties of known pulsars and of ordinary radio sources, to build
and calibrate a pulsar rule that does not use the ATNF catalogue (2.6.3).

The scientific cross-validation recovers 0 % of ATNF pulsars without ATNF,
because the compact axis has no other route.  Literature signatures:

* steep radio spectrum: pulsars alpha ~ -1.6 (Jankowski et al. 2018; -1.4,
  Bates et al. 2013); ordinary radio sources -0.73.  Frail et al. (2018)
  select alpha <= -1.5 between TGSS (150 MHz) and NVSS (1.4 GHz) with
  compactness S_int / S_peak <= 1.5;
* linear polarisation: NVSS fractional polarisation > 5 % keeps ~90 % of
  pulsars and removes ~90 % of other sources (Han & Tian 1999);
* no optical counterpart; concentration to the Galactic plane.

Samples:
* pulsars  ATNF (Manchester et al. 2005, VizieR B/psr) positions;
* control  NVSS sources in random 0.5-degree cones (fixed seed).
Both are re-centred on their NVSS position (15"), and every other quantity is
measured around that radio position (so the timing positions of pulsars give
them no advantage): TGSS ADR1 (Intema et al. 2017), LoTSS DR2, FIRST, VLASS,
Gaia DR3.  Output: v2/benchmark/pulsar_truth/radio_sample.csv.gz
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import retry  # noqa: E402
from build_bright_truth import nearest  # noqa: E402

OUT = BENCH / "pulsar_truth"


def pulsars() -> pd.DataFrame:
    from astroquery.vizier import Vizier
    t = retry(lambda: Vizier(columns=["PSRJ", "_RAJ2000", "_DEJ2000"], row_limit=-1, timeout=600).get_catalogs("B/psr/psr"),
              tries=3, wait=30)[0].to_pandas()
    print("ATNF rows:", len(t), list(t.columns), flush=True)
    return pd.DataFrame({"name": t["PSRJ"].astype(str), "ra": pd.to_numeric(t["_RAJ2000"], errors="coerce"),
                         "dec": pd.to_numeric(t["_DEJ2000"], errors="coerce"), "is_pulsar": 1}).dropna(subset=["ra", "dec"])


def control(n_cones: int, seed: int) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    rng = np.random.default_rng(seed)
    ra = rng.uniform(0, 360, n_cones)
    dec = np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(-40)), 1, n_cones)))    # NVSS: dec > -40
    v = Vizier(columns=["NVSS", "_RAJ2000", "_DEJ2000"], row_limit=-1, timeout=600)
    parts = []
    for r, d in zip(ra, dec):
        try:
            res = retry(lambda: v.query_region(SkyCoord(r * u.deg, d * u.deg), radius=0.5 * u.deg, catalog="VIII/65/nvss"),
                        tries=3, wait=20)
        except Exception as exc:
            print("control cone failed", str(exc)[:120], flush=True)
            continue
        if res:
            parts.append(res[0].to_pandas())
    t = pd.concat(parts, ignore_index=True).drop_duplicates("NVSS")
    print("control NVSS sources:", len(t), flush=True)
    return pd.DataFrame({"name": "NVSS " + t["NVSS"].astype(str), "ra": t["_RAJ2000"], "dec": t["_DEJ2000"], "is_pulsar": 0})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cones", type=int, default=60)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d = pd.concat([pulsars(), control(a.cones, a.seed)], ignore_index=True)
    d.insert(0, "rid", np.arange(len(d)))
    d = nearest(d, "VIII/65/nvss", 15.0, ["**", "_RAJ2000", "_DEJ2000"], "nvss_")
    print("NVSS detected:", d.groupby("is_pulsar")["nvss_S1.4"].apply(lambda s: s.notna().sum()).to_dict(), flush=True)
    d = d[d["nvss_S1.4"].notna()].copy()
    d["truth_ra"], d["truth_dec"] = d.ra, d.dec
    d["ra"], d["dec"] = d["nvss__RAJ2000"], d["nvss__DEJ2000"]          # measure everything around the radio position
    # Column names differ between surveys: keep all, choose in the analysis.
    for table, radius, cols, prefix in (("J/A+A/598/A78/table3", 25.0, ["**"], "tgss_"),
                                        ("J/A+A/659/A1", 10.0, ["**"], "lotss_"),
                                        ("VIII/92/first14", 5.0, ["**"], "first_"),
                                        ("J/ApJS/255/30", 5.0, ["**"], "vlass_"),
                                        ("I/355/gaiadr3", 5.0, ["Source", "Gmag", "Plx", "e_Plx"], "gaia_")):
        try:                     # one failing survey must not lose the others
            d = nearest(d, table, radius, cols, prefix)
        except Exception as exc:
            print(f"{table}: skipped ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
    d.to_csv(OUT / "radio_sample.csv.gz", index=False, compression="gzip")
    print(d.shape, d.groupby("is_pulsar").size().to_dict(), flush=True)
    print(d.notna().groupby(d.is_pulsar).mean().T.round(2).to_string(), flush=True)


if __name__ == "__main__":
    main()

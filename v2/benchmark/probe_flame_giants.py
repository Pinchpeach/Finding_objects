#!/usr/bin/env python3
"""Gaia DR3 FLAME / GSP-Phot / GSP-Spec values of the Kepler RGB / AGB truth
(Vrard et al. 2025; Classifier/truth/generated/rgb_agb_truth.csv), to see why
the FLAME RGB rule (Classifier/branches/evolved_star.py) rarely applies (2.13.0).

Output: v2/benchmark/flame_giants/rgb_agb_gaia.csv.gz
"""
from pathlib import Path
import pandas as pd

BENCH = Path(__file__).resolve().parent
OUT = BENCH / "flame_giants"


def main():
    from astroquery.xmatch import XMatch
    from astropy.table import Table
    import astropy.units as u
    OUT.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(BENCH.parent / "Classifier" / "truth" / "generated" / "rgb_agb_truth.csv")
    t = t.dropna(subset=["ra", "dec"]).reset_index(drop=True)
    t["rid"] = range(len(t))
    m = XMatch.query(cat1=Table.from_pandas(t[["rid", "ra", "dec"]]), cat2="vizier:I/355/paramp",
                     max_distance=2 * u.arcsec, colRA1="ra", colDec1="dec").to_pandas()
    print("columns:", list(m.columns), flush=True)
    m = m.sort_values("angDist").drop_duplicates("rid")
    out = t.merge(m.drop(columns=["ra", "dec"], errors="ignore"), on="rid", how="left")
    out.to_csv(OUT / "rgb_agb_gaia.csv.gz", index=False, compression="gzip")
    print(out.groupby("truth_class").size().to_dict(), flush=True)


if __name__ == "__main__":
    main()

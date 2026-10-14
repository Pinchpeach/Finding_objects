#!/usr/bin/env python3
"""Mira vs semi-regular truth for a Gaia DR3 LPV criterion (2.13.0).

ASAS-SN types M (Mira) and SR (Jayasinghe et al. 2018-2021, VizieR II/366)
matched (CDS XMatch, 2") to the Gaia DR3 long-period-variable SOS table
(Lebzelter et al. 2023, VizieR I/358/vlpv: period, G amplitude, C-star flag).
Miras are defined by large visual amplitude (GCVS: dV > 2.5 mag); in the Gaia
G band the Mira-like LPVs sit at G amplitudes (5-95 %) of ~1-2.5 mag and the
semi-regulars below ~1 mag (Mowlavi et al. 2018, Gaia DR2 LPV catalogue).
The threshold is fitted on one half of this sample and checked on the other.

Output: v2/benchmark/mira_truth/asassn_gaia_lpv.csv.gz
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import retry  # noqa: E402

OUT = BENCH / "mira_truth"


def main() -> None:
    from astroquery.vizier import Vizier
    from astroquery.xmatch import XMatch
    import astropy.units as u
    from astropy.table import Table

    p = argparse.ArgumentParser()
    p.add_argument("--per-type", type=int, default=4000)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for t in ("M", "SR"):
        v = Vizier(
            columns=["ASASSN-V", "RAJ2000", "DEJ2000", "Type", "Per", "Vmag", "Amp", "Prob"],
            column_filters={"Type": f"={t}", "Prob": ">0.9"},
            row_limit=a.per_type * 3,
        )
        tab = retry(lambda: v.get_catalogs("II/366/catv2021"), tries=3, wait=30)[0].to_pandas()
        tab = tab.sample(min(len(tab), a.per_type), random_state=2)
        print(t, len(tab), flush=True)
        parts.append(tab)
    d = pd.concat(parts, ignore_index=True)
    d["ra"] = pd.to_numeric(d.RAJ2000, errors="coerce")
    d["dec"] = pd.to_numeric(d.DEJ2000, errors="coerce")
    d = d.dropna(subset=["ra", "dec"]).reset_index(drop=True)
    d["rid"] = range(len(d))
    m = retry(
        lambda: XMatch.query(
            cat1=Table.from_pandas(d[["rid", "ra", "dec"]]),
            cat2="vizier:I/358/vlpv",
            max_distance=2 * u.arcsec,
            colRA1="ra",
            colDec1="dec",
        ),
        tries=3,
        wait=30,
    ).to_pandas()
    print("Gaia LPV columns:", list(m.columns), flush=True)
    m = m.sort_values("angDist").drop_duplicates("rid")
    m = m.rename(columns={c: "lpv_" + c for c in m.columns if c not in ("rid", "ra", "dec")}).drop(
        columns=["ra", "dec"], errors="ignore"
    )
    out = d.merge(m, on="rid", how="left")
    print(
        "Gaia LPV matched:", out.groupby("Type")["lpv_angDist"].apply(lambda s: s.notna().sum()).to_dict(), flush=True
    )
    out.to_csv(OUT / "asassn_gaia_lpv.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()

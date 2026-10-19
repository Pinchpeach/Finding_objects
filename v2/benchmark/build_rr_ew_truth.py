#!/usr/bin/env python3
"""RR Lyrae vs contact/eclipsing binaries in ZTF (2.12.0).

ASAS-SN variable-star types (Jayasinghe et al. 2018-2021, VizieR II/366) are
the truth; the ZTF periodic-variable catalogue (Chen et al. 2020, J/ApJS/249/18)
gives the ZTF type, period, g/r amplitudes and Fourier parameters for the same
stars (CDS XMatch, 2").  Used to measure how often ZTF calls an ASAS-SN RR
Lyrae an eclipsing binary (EW/EA) and which ZTF quantity separates them.

Physical basis: a pulsating star changes temperature over its cycle, so its
amplitude grows towards the blue (RR Lyrae A_g/A_r ~ 1.3-1.4); a W UMa
contact binary changes mainly in projected area of two similar-temperature
stars, so its amplitude is nearly the same in g and r.

Output: v2/benchmark/rr_ew_truth/asassn_ztf.csv.gz
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import retry  # noqa: E402

OUT = BENCH / "rr_ew_truth"
TYPES = ("RRAB", "RRC", "EW", "EA")


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Get_data"))
    import throttle

    throttle.install()  # 3-5 s before every archive request (2.33.0)
    from astroquery.vizier import Vizier
    from astroquery.xmatch import XMatch
    import astropy.units as u
    from astropy.table import Table

    p = argparse.ArgumentParser()
    p.add_argument("--per-type", type=int, default=3000)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for t in TYPES:
        v = Vizier(
            columns=["ASASSN-V", "RAJ2000", "DEJ2000", "Type", "Per", "Vmag", "Amp", "Prob"],
            column_filters={"Type": f"={t}", "DEJ2000": ">-27", "Prob": ">0.95"},
            row_limit=a.per_type * 3,
        )
        tab = retry(lambda: v.get_catalogs("II/366/catv2021"), tries=3, wait=30)[0].to_pandas()
        tab = tab.sample(min(len(tab), a.per_type), random_state=1)
        print(t, len(tab), flush=True)
        parts.append(tab)
    d = pd.concat(parts, ignore_index=True)
    d["ra"] = pd.to_numeric(d.RAJ2000, errors="coerce")
    d["dec"] = pd.to_numeric(d.DEJ2000, errors="coerce")
    d = d.dropna(subset=["ra", "dec"]).reset_index(drop=True)
    d["rid"] = range(len(d))
    up = Table.from_pandas(d[["rid", "ra", "dec"]])
    m = retry(
        lambda: XMatch.query(
            cat1=up, cat2="vizier:J/ApJS/249/18/table2", max_distance=2 * u.arcsec, colRA1="ra", colDec1="dec"
        ),
        tries=3,
        wait=30,
    ).to_pandas()
    m = m.sort_values("angDist").drop_duplicates("rid")
    keep = ["rid", "angDist"] + [
        c for c in m.columns if c in ("ID", "Type", "Per", "gAmp", "rAmp", "R21", "phi21", "gmag", "rmag", "Ng", "Nr")
    ]
    m = m[keep].rename(columns={c: "ztf_" + c for c in keep if c != "rid"})
    out = d.merge(m, on="rid", how="left")
    print("ZTF matched:", out.groupby("Type")["ztf_Type"].apply(lambda s: s.notna().sum()).to_dict(), flush=True)
    out.to_csv(OUT / "asassn_ztf.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()

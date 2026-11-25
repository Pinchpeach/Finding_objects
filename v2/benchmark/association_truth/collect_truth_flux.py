#!/usr/bin/env python3
"""COSMOS2020 Classic positions, i-band magnitude and the fluxes of the blend model, per deep field (2.60.8).

    python collect_truth_flux.py --out DIR [--fields-file fields_split.csv]

The deep-field truth kept by ``collect_deep_cosmos.py`` has six columns (positions, ACS F814W, morphology class, SED
type, HSC i).  The association measurement also needs, for the low-resolution catalogues, how much flux each truth
source puts into the PSF of an AllWISE / 2MASS / GALEX row: IRAC ch1 (``FIRACCH1``, 3.6 um, the closest band to WISE W1),
UltraVISTA Ks (``FUVISTAKs``, 2MASS Ks) and CFHT u (``FCFHTu``; GALEX NUV is detected for few sources, so the u flux is
the proxy; ``FGALEXNUV`` is kept to check it).  One VizieR cone per field (6'), through the usual mirror failover and
throttle; writes DIR/<field>.csv.gz.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))
import throttle  # noqa: E402

throttle.install()
import _catalog_utils  # noqa: E402

COLUMNS = ["RAJ2000", "DEJ2000", "HSCimagAuto", "ACSF814Wmag", "ACSmuClass", "lptype", "FIRACCH1", "FSPLASHCH1",
           "FUVISTAKs", "FCFHTu", "FGALEXNUV", "FGALEXFUV"]  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields-file", type=Path, default=Path(__file__).with_name("fields_split.csv"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for r in pd.read_csv(a.fields_file).itertuples():
        dst = a.out / f"{r.name}.csv.gz"
        if dst.exists():
            continue
        tl = _catalog_utils.vizier_query("J/ApJS/258/11/classic", float(r.ra), float(r.dec), 6.0, columns=COLUMNS)
        if not len(tl):
            print("no rows", r.name, flush=True)
            continue
        df = tl[0].to_pandas()
        df.to_csv(dst, index=False)
        print(r.name, len(df), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

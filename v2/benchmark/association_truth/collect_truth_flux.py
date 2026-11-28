#!/usr/bin/env python3
"""COSMOS2020 Classic positions, i-band magnitude and the fluxes of the blend model, per deep field (2.60.9).

    python collect_truth_flux.py --out DIR [--fields-file fields_split.csv] [--radius 6.35]

The deep-field truth kept by ``collect_deep_cosmos.py`` has six columns (positions, ACS F814W, morphology class, SED
type, HSC i).  The association measurement also needs, for the low-resolution catalogues, how much flux each truth
source puts into the PSF of an AllWISE / 2MASS / GALEX row: IRAC ch1 (``FIRACCH1``, 3.6 um, the closest band to WISE W1),
UltraVISTA Ks (``FUVISTAKs``, 2MASS Ks) and CFHT u (``FCFHTu``; GALEX NUV is detected for few sources, so the u flux is
the proxy; ``FGALEXNUV`` is kept to check it).  One VizieR cone per field, through the usual mirror failover and
throttle; writes DIR/<field>.csv.gz.

Radius (2.60.11): the fields are 6' cones but the search for the flux-dominant counterpart of a low-resolution row looks
3 FWHM around it (AllWISE 18.3'', GALEX 15.9''), so a row near the edge needs truth sources up to 0.31' outside the
field.  The default 6.35' leaves that margin; the columns ``r_arcmin`` (distance from the field centre) added here let the
scoring keep every count inside 6'.
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


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields-file", type=Path, default=Path(__file__).with_name("fields_split.csv"))
    ap.add_argument(
        "--radius", type=float, default=6.35, help="cone radius in arcmin (6.35 = the field's 6' + 3 FWHM of AllWISE)"
    )
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    for r in pd.read_csv(a.fields_file).itertuples():
        dst = a.out / f"{r.name}.csv.gz"
        if dst.exists():
            continue
        tl = _catalog_utils.vizier_query("J/ApJS/258/11/classic", float(r.ra), float(r.dec), a.radius, columns=COLUMNS)
        if not len(tl):
            print("no rows", r.name, flush=True)
            continue
        df = tl[0].to_pandas()
        df.to_csv(dst, index=False)
        print(r.name, len(df), flush=True)
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

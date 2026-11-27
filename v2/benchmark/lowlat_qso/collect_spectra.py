#!/usr/bin/env python3
"""Collect only the spectroscopic catalogues for the low-latitude regions (2.61.5): how many objects have a spectral class QSO.

    python collect_spectra.py --regions fields_lowlat.csv fields_lowlat_confirm.csv --out ROOT [--jobs 3]
    python collect_spectra.py merge --raw RAWROOT:fields.csv ... --spectra ROOT --out MERGED

The blind runs of the 169 + 140 regions have no spectroscopic catalogue (``V2_SKIP_COLLECTORS=blind``).  ``collect_spectra``
asks the SDSS DR18, DESI DR1 and LAMOST DR5 spectroscopy collectors only, for the 3' cone of each region, into
``ROOT/<region>/``.  ``merge`` copies the blind raw files of a region and adds those files, so that
``pipeline.py --raw-dir MERGED/<region>/raw`` classifies the same objects with spectra (``V2_LOWLAT_QSO=surveys2`` etc.):
the labels of the objects with a spectral class QSO then show what a label switch does to them, and ``spectro_keep``
what it keeps.  The 310 regions are centred on quasars of the Huo et al. (2025, LAMOST DR10) and Fu et al. (2022) samples.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
WANTED = ("sdss_spectroscopy", "desi_spectroscopy", "lamost_spectroscopy")


def controller():
    sys.path.insert(0, str(V2 / "Get_data"))
    spec = importlib.util.spec_from_file_location("v2_get_data_controller_spectra", V2 / "Get_data" / "controller.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def collect(regions: list[Path], out: Path, jobs: int, radius: float, collectors) -> None:
    c = controller()
    os.environ["V2_SKIP_COLLECTORS"] = ",".join(n for n in c.COLLECTORS if n not in collectors)
    os.environ["V2_CACHE"] = "0"
    rows = pd.concat([pd.read_csv(p) for p in regions], ignore_index=True)
    rows = rows[rows.kind == "qso"]

    def one(r):
        d = out / r.name
        if (d / "done.txt").exists():
            return
        t0 = time.time()
        c.collect_all(float(r.ra), float(r.dec), radius, d, workers=len(collectors))
        (d / "done.txt").write_text(f"{time.time() - t0:.1f} s\n")
        print(f"done {r.name} {time.time() - t0:.0f} s", flush=True)

    with ThreadPoolExecutor(max(1, jobs)) as ex:
        list(ex.map(one, rows.itertuples()))


def merge(raw_sets: list[str], spectra: Path, out: Path) -> None:
    for spec in raw_sets:
        root, fields = spec.rsplit(":", 1)
        reg = pd.read_csv(fields)
        for r in reg[reg.kind == "qso"].name:
            dst = out / r / "raw"
            if dst.exists():
                continue
            shutil.copytree(Path(root) / r / "raw", dst)
            for f in (spectra / r).glob("*spectroscopy*_ra*.csv"):
                shutil.copy(f, dst / f.name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="collect", choices=["collect", "merge"])
    ap.add_argument("--regions", type=Path, nargs="*")
    ap.add_argument("--raw", nargs="*")
    ap.add_argument("--spectra", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--radius", type=float, default=3.0)
    a = ap.parse_args()
    if a.cmd == "collect":
        collect(a.regions, a.out, a.jobs, a.radius, WANTED)
    else:
        merge(a.raw, a.spectra, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

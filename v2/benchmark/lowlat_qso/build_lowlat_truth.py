#!/usr/bin/env python3
"""The compact truth table of the low-latitude quasar recall measurement (2.61.2).

    python build_lowlat_truth.py --out lowlat_truth.csv.gz [--huo FILE.fits[.gz]] [--fu-votable FILE.xml]

Two public spectroscopic samples of quasars behind the Galactic plane, both found by a photometric selection on
Pan-STARRS1 + AllWISE (so a recall measured on them is an upper bound, benchmark/lowlat_qso/LOWLAT_QSO.md):

* ``huo``  Huo et al. 2025 (arXiv:2502.05480): 1,982 quasars at |b| <= 20 deg from LAMOST DR10 (NADC PaperData,
  doi:10.12149/101489, ``GPQs_LAMOST_DR10.fits.gz``).  Columns used: NAME, RA, DEC, Z_VI, EBV (Planck, line of sight),
  PS1 mean PSF imag, NOTE (N new / K known).
* ``fu``   Fu et al. 2022 (ApJS 261, 32; arXiv:2206.05704): 204 quasars (``gpqcat``) and the 17 stars and 2 galaxies of
  the observed candidates (``tablec1``), VizieR J/ApJS/261/32.  The stars and galaxies are the only known non-quasars
  of a quasar-candidate list at low latitude and are kept as ``fu_contaminant``.

One row per object: ``sample, name, ra, dec, l, b, z, imag, ebv, cls`` (qso / star / galaxy), ``also_in``: the other sample
that lists the same quasar within 3'' (the Fu quasars that are also in the Huo table).  Downloads need only the two public
hosts above; without a network use ``--huo`` / ``--fu-votable`` with the files.  The SHA-256 of the sources is printed.
"""

from __future__ import annotations

import sys

import argparse
import gzip
import hashlib
import io
import shutil
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.table import Table

HUO_URL = "https://nadc.china-vo.org/res/file_upload/download?id=48427"
FU_URLS = (
    "https://vizier.cds.unistra.fr/viz-bin/votable?-source=J/ApJS/261/32&-out.max=unlimited",
    "https://vizier.cfa.harvard.edu/viz-bin/votable?-source=J/ApJS/261/32&-out.max=unlimited",
)
MATCH_ARCSEC = 3.0


def fetch(urls) -> bytes:
    last = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"none of {urls} answered: {last}")


def galactic(ra, dec):
    c = SkyCoord(np.asarray(ra, float) * u.deg, np.asarray(dec, float) * u.deg).galactic
    return c.l.deg, c.b.deg


def read_huo(raw: bytes) -> pd.DataFrame:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    t = Table.read(io.BytesIO(raw), format="fits")
    ra, dec = np.asarray(t["RA"], float), np.asarray(t["DEC"], float)
    l, b = galactic(ra, dec)
    return pd.DataFrame(
        dict(sample="huo", name=[str(x).strip() for x in t["NAME"]], ra=ra, dec=dec, l=l, b=b,
             z=np.asarray(t["Z_VI"], float), imag=np.asarray(t["IMAG"], float), ebv=np.asarray(t["EBV"], float), cls="qso")
    )  # fmt: skip


def read_fu(raw: bytes) -> pd.DataFrame:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(raw)
    ns = {"v": root.tag.split("}")[0].strip("{")}
    out = []
    for tab in root.iter(f"{{{ns['v']}}}TABLE"):
        name = tab.get("name", "")
        fields = [f.get("name") for f in tab.findall("v:FIELD", ns)]
        rows = [[(td.text or "").strip() for td in tr.findall("v:TD", ns)] for tr in tab.iter(f"{{{ns['v']}}}TR")]
        d = pd.DataFrame(rows, columns=fields)
        out.append((name, d))
    got = dict(out)
    q = got["J/ApJS/261/32/gpqcat"]
    c = got["J/ApJS/261/32/tablec1"]
    num = lambda s: pd.to_numeric(s, errors="coerce")  # noqa: E731
    qso = pd.DataFrame(
        dict(sample="fu", name=q.Name, ra=num(q.RAdeg), dec=num(q.DEdeg), l=num(q.GLON), b=num(q.GLAT), z=num(q.z),
             imag=num(q.imag), ebv=np.nan, cls="qso")
    )  # fmt: skip
    non = pd.DataFrame(
        dict(sample="fu_contaminant", name=c.Name, ra=num(c.RAJ2000), dec=num(c.DEJ2000), l=num(c.GLON), b=num(c.GLAT),
             z=np.nan, imag=num(c.imag), ebv=np.nan, cls=c.Class.str.lower())
    )  # fmt: skip
    return pd.concat([qso, non], ignore_index=True)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--huo", type=Path, help="GPQs_LAMOST_DR10.fits[.gz] instead of the download")
    ap.add_argument("--fu-votable", type=Path, help="VizieR J/ApJS/261/32 votable instead of the download")
    a = ap.parse_args()
    t0 = RI.start()
    huo_raw = a.huo.read_bytes() if a.huo else fetch([HUO_URL])
    fu_raw = a.fu_votable.read_bytes() if a.fu_votable else fetch(FU_URLS)
    print("sha256 huo", hashlib.sha256(huo_raw).hexdigest(), len(huo_raw), "bytes")
    print("sha256 fu ", hashlib.sha256(fu_raw).hexdigest(), len(fu_raw), "bytes")
    H, F = read_huo(huo_raw), read_fu(fu_raw)
    d = pd.concat([H, F], ignore_index=True)
    # the same quasar in both samples
    q = d[d.cls == "qso"]
    ch = SkyCoord(H.ra.values * u.deg, H.dec.values * u.deg)
    fq = q[q["sample"] == "fu"]
    cf = SkyCoord(fq.ra.values * u.deg, fq.dec.values * u.deg)
    idx, sep, _ = cf.match_to_catalog_sky(ch)
    d["also_in"] = ""
    d.loc[fq.index[sep.arcsec < MATCH_ARCSEC], "also_in"] = "huo"
    d.loc[H.index[np.unique(idx[sep.arcsec < MATCH_ARCSEC])], "also_in"] = "fu"
    for c in ("ra", "dec", "l", "b", "z", "imag", "ebv"):
        d[c] = d[c].astype(float).round(7 if c in ("ra", "dec") else 4)
    d.to_csv(a.out, index=False)
    print(d.groupby(["sample", "cls"]).size().to_string())
    print("quasars in both samples:", int((d.also_in == "huo").sum()))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

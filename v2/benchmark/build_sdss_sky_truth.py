#!/usr/bin/env python3
"""Sky-spread SDSS spectroscopic benchmark (2.52.0).

The 2.x SDSS benchmark (truth_data/ground_truth.csv, build_truth_sets.py)
took the first spectra in specObjID order: 9,999 objects from 142 plates, the
3,333 galaxies from only 7 plates, no |b| < 20 deg object.  The scientific
review (SCIENTIFIC_REVIEW_2026-11-11.md 3.1, items 6.7-6.8) asked for a
benchmark drawn over the whole spectroscopic footprint, low latitude
included, with a spatial train / calibration / test split.

Sampling
  1. Pseudo-random subset of SpecObj per class: specObjID % m = r.  The id
     packs plate, fibre and MJD bits, so the residue class is spread over all
     plates (no ORDER BY, no plate clustering).  ZWARNING = 0, sciencePrimary.
  2. Equal-area sky cells: 24 bands uniform in sin(Dec) x 32 in RA = 768
     cells of 53.7 deg^2 (HEALPix nside = 8 has the same count and area;
     a plain grid needs no healpy).
  3. Per class, objects are taken one per occupied cell in turn (pseudo-random
     order inside a cell) until the quota is filled, so every cell with that
     class contributes before any cell contributes twice.  Low latitude is
     kept wherever SDSS has spectra there (SEGUE / BOSS plates); the natural
     shortage of |b| < 20 deg galaxies and QSOs is reported, not hidden.
  4. Objects within 1.5" of any object the models were trained or tuned on
     (old SDSS benchmark, DESI external and fusion sets, LS-GBM training set;
     score_independent_fields.benchmark_positions) are removed first, so the
     whole set is new to the current models.

Split: the column sky_cell drives validate_catalog_truth.py --split-column,
so train / calibration / test are disjoint on the sky (neighbouring objects
share depth, extinction and plate; Roberts et al. 2017 on spatial
cross-validation).

    python v2/benchmark/build_sdss_sky_truth.py --per-class 3333 --out truth.csv
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
SKY_URL = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
CLASSES = ("STAR", "GALAXY", "QSO")
# residue modulus per class: ~3-6x the quota from DR18 (≈1M stars, 3M
# galaxies, 1M QSO spectra with ZWARNING = 0)
MODULUS = {"STAR": 64, "GALAXY": 256, "QSO": 64}
N_DEC, N_RA = 24, 32


def fetch(sql, retries=5, timeout=600):
    url = SKY_URL + "?" + urllib.parse.urlencode({"cmd": sql, "format": "csv"})
    last = None
    for k in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                d = pd.read_csv(io.BytesIO(r.read()), comment="#")
            d.columns = [str(c).strip().lower() for c in d.columns]
            if "specobjid" not in d:
                raise RuntimeError(f"unexpected SkyServer answer: {list(d.columns)[:5]}")
            return d
        except Exception as e:  # noqa: BLE001 - SkyServer times out transiently
            last = e
            time.sleep(min(60, 4 * 2**k))
    raise RuntimeError(f"SDSS query failed: {last}")


def candidates(cls, residue):
    m = MODULUS[cls]
    sql = f"""SELECT s.specObjID, s.bestObjID, s.ra, s.dec, s.class, s.subClass, s.z, s.zErr,
 s.zWarning, s.plate, s.mjd, s.fiberID, s.survey, p.psfMag_r, p.type AS photo_type
 FROM SpecObj AS s LEFT JOIN PhotoObj AS p ON p.objID = s.bestObjID
 WHERE s.class = '{cls}' AND s.zWarning = 0 AND s.sciencePrimary = 1
   AND (s.specObjID % {m}) = {residue}"""
    d = fetch(sql)
    print(f"[{cls}] residue {residue}/{m}: {len(d)} spectra", flush=True)
    return d


def sky_cell(ra, dec):
    band = np.clip(((np.sin(np.radians(dec)) + 1) / 2 * N_DEC).astype(int), 0, N_DEC - 1)
    col = np.clip((np.mod(ra, 360) / 360 * N_RA).astype(int), 0, N_RA - 1)
    return band * N_RA + col


def gal_b(ra, dec):
    a, d = np.radians(ra), np.radians(dec)
    return np.degrees(np.arcsin(-0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d)))


def spread(d, quota, seed):
    """One object per occupied cell in turn, pseudo-random order inside a cell."""
    rng = np.random.default_rng(seed)
    d = d.assign(_r=rng.random(len(d))).sort_values(["sky_cell", "_r"])
    d["_rank"] = d.groupby("sky_cell").cumcount()
    d = d.sort_values(["_rank", "_r"]).head(quota)
    return d.drop(columns=["_r", "_rank"])


def exclude_known(d):
    sys.path.insert(0, str(B))
    import score_independent_fields as S

    known = S.benchmark_positions()
    _, sep = S._nearest(d.ra.to_numpy(float), d.dec.to_numpy(float), known.ra.to_numpy(float), known.dec.to_numpy(float))
    keep = sep >= 1.5
    print(f"removed {int((~keep).sum())} objects already in a training / tuning set", flush=True)
    return d[keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=3333)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=2052)
    a = ap.parse_args()
    sys.path.insert(0, str(B.parent / "Get_data"))
    import throttle

    throttle.install()
    blocks = []
    for cls in CLASSES:
        got, residue = [], 7  # fixed residues: reproducible
        while sum(len(g) for g in got) < 3 * a.per_class and residue < 7 + 6:
            got.append(candidates(cls, residue))
            residue += 1
        d = pd.concat(got, ignore_index=True).drop_duplicates("specobjid")
        d["truth_class"] = cls
        d["sky_cell"] = sky_cell(d.ra.to_numpy(float), d.dec.to_numpy(float))
        d = exclude_known(d)
        if len(d) < a.per_class:
            raise SystemExit(f"{cls}: only {len(d)} candidates for {a.per_class}")
        blocks.append(spread(d, a.per_class, a.seed + CLASSES.index(cls)))
    t = pd.concat(blocks, ignore_index=True)
    t["gal_b"] = gal_b(t.ra.to_numpy(float), t.dec.to_numpy(float)).round(3)
    t["truth_source"] = "SDSS_DR18_SPECTROSCOPY"
    t["truth_quality"] = "ZWARNING_0_SCIENCEPRIMARY"
    t["truth_selection"] = "SKY_SPREAD"
    t["benchmark_id"] = [f"SKY{i + 1:06d}" for i in range(len(t))]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)
    bb = pd.cut(t.gal_b.abs(), [0, 10, 20, 30, 60, 90])
    print(pd.crosstab(bb, t.truth_class).to_string())
    print("plates per class:", t.groupby("truth_class").plate.nunique().to_dict())
    print("sky cells per class:", t.groupby("truth_class").sky_cell.nunique().to_dict())
    print(f"[OK] {len(t)} objects -> {a.out}")


if __name__ == "__main__":
    main()

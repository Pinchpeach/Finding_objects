#!/usr/bin/env python3
"""Bright-star truth for the spectroscopic rules that the faint SDSS/DESI
benchmark cannot test (2.6.2):

* apogee   APOGEE DR17 (Abdurro'uf et al. 2022, VizieR III/286) high-resolution
           Teff / log g / [Fe/H] for stars with high S/N, in RA slices across
           the survey, with Gaia DR3 astrophysical parameters (I/355/paramp:
           GSP-Phot and GSP-Spec) and parallaxes (I/355/gaiadr3), and LAMOST
           LASP parameters (V/164/stellar5).  Tests luminosity class and
           metallicity from GSP-Spec / LAMOST / GSP-Phot against APOGEE.
* els      Gaia DR3 ESP-ELS emission-line stars (I/355/paramp, one query per
           class label) with SIMBAD main types (TAP upload).  Tests the
           ESP-ELS classes against the literature types.
* lpv      the field Gaia LPV sample (agb_truth/agb_gate_sample.csv.gz)
           matched to LAMOST DR5 spectra (V/164/dr5 class / subclass): an
           independent C / M chemistry check of the AGB models on faint field
           LPVs.

Output: v2/benchmark/bright_truth/{apogee,els,lpv_lamost}.csv.gz
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import retry  # noqa: E402

OUT = BENCH / "bright_truth"
ELS_LABELS = ["beStar", "HerbigStar", "TTauri", "RedDwarfEmStar", "wC", "wN", "PlanetaryNebula"]
SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap"
SIMBAD_Q = """SELECT t.rid, b.main_id, b.otype, b.sp_type,
 DISTANCE(POINT('ICRS', b.ra, b.dec), POINT('ICRS', t.ra, t.dec)) * 3600 AS simbad_sep
 FROM TAP_UPLOAD.t AS t JOIN basic AS b
 ON 1 = CONTAINS(POINT('ICRS', b.ra, b.dec), CIRCLE('ICRS', t.ra, t.dec, 2.0 / 3600))"""


def nearest(df: pd.DataFrame, table: str, radius: float, cols: list[str], prefix: str, chunk: int = 500) -> pd.DataFrame:
    """Nearest row of a VizieR table for each (rid, ra, dec); columns prefixed."""
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    v = Vizier(columns=cols + ["+_r"], row_limit=-1, timeout=600)
    parts = []
    for s0 in range(0, len(df), chunk):
        sub = df.iloc[s0:s0 + chunk]
        coords = SkyCoord(sub.ra.to_numpy() * u.deg, sub.dec.to_numpy() * u.deg)
        t0 = time.time()
        try:
            res = retry(lambda: v.query_region(coords, radius=radius * u.arcsec, catalog=table), tries=3, wait=20)
        except Exception as exc:
            print(f"{table} rows {s0}+: failed {str(exc)[:160]}", flush=True)
            continue
        if not res:
            continue
        t = res[0].to_pandas()
        t["rid"] = sub.rid.to_numpy()[t["_q"].astype(int).to_numpy() - 1]
        parts.append(t.sort_values("_r").drop_duplicates("rid"))
        print(f"{table} rows {s0}-{s0 + len(sub)}: {len(parts[-1])} in {time.time() - t0:.0f} s", flush=True)
    if not parts:
        return df
    t = pd.concat(parts, ignore_index=True).drop(columns=["_q"], errors="ignore")
    t = t.rename(columns={c: f"{prefix}{c}" for c in t.columns if c != "rid"})
    return df.merge(t, on="rid", how="left")


def simbad(df: pd.DataFrame, chunk: int = 2000) -> pd.DataFrame:
    import pyvo
    from astropy.table import Table
    svc = pyvo.dal.TAPService(SIMBAD_TAP)
    parts = []
    for s0 in range(0, len(df), chunk):
        up = Table.from_pandas(df.iloc[s0:s0 + chunk][["rid", "ra", "dec"]])
        try:
            r = retry(lambda: svc.run_sync(SIMBAD_Q, uploads={"t": up}, maxrec=10 * chunk).to_table().to_pandas(),
                      tries=3, wait=30)
        except Exception as exc:
            print(f"simbad rows {s0}+: failed {str(exc)[:160]}", flush=True)
            continue
        parts.append(r.sort_values("simbad_sep").drop_duplicates("rid"))
        print(f"simbad rows {s0}-{s0 + len(up)}: {len(parts[-1])}", flush=True)
    if not parts:
        return df
    s = pd.concat(parts, ignore_index=True)
    for c in ("main_id", "otype", "sp_type"):
        s[c] = s[c].astype(str).str.strip()
    return df.merge(s.rename(columns={"main_id": "simbad_main_id", "otype": "simbad_otype", "sp_type": "simbad_sp_type"}),
                    on="rid", how="left")


def _pick(cols, *cands):
    low = {c.lower(): c for c in cols}
    for c in cands:
        if c.lower() in low:
            return low[c.lower()]
    return None


def apogee(per_slice: int, slices: int) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    cat = "III/286/catalog"
    meta = retry(lambda: Vizier(columns=["**"], row_limit=1, timeout=300).get_catalogs(cat), tries=3, wait=20)[0]
    cols = list(meta.colnames)
    print("APOGEE columns:", " ".join(cols), flush=True)
    ra_c = _pick(cols, "RAJ2000", "RAdeg", "RA_ICRS", "_RAJ2000")
    de_c = _pick(cols, "DEJ2000", "DEdeg", "DE_ICRS", "_DEJ2000")
    want = {"apo_teff": _pick(cols, "Teff"), "apo_logg": _pick(cols, "logg"), "apo_feh": _pick(cols, "[Fe/H]", "[M/H]"),
            "apo_snr": _pick(cols, "S/N", "SNR", "snr"), "apo_id": _pick(cols, "APOGEE", "APOGEE_ID", "ID")}
    print("APOGEE picked:", ra_c, de_c, want, flush=True)
    keep = [c for c in [ra_c, de_c, *want.values()] if c]
    parts = []
    for i in range(slices):
        lo, hi = 360.0 * i / slices, 360.0 * (i + 1) / slices
        cons = {ra_c: f"{lo:.1f}..{hi:.1f}"}
        if want["apo_snr"]:
            cons[want["apo_snr"]] = ">100"
        v = Vizier(columns=keep, row_limit=per_slice, timeout=600)
        try:
            res = retry(lambda: v.query_constraints(catalog=cat, **cons), tries=3, wait=20)
        except Exception as exc:
            print(f"APOGEE slice {i}: failed {str(exc)[:160]}", flush=True)
            continue
        if res:
            parts.append(res[0].to_pandas())
            print(f"APOGEE RA {lo:.0f}-{hi:.0f}: {len(parts[-1])}", flush=True)
    d = pd.concat(parts, ignore_index=True)
    d = d.rename(columns={ra_c: "ra", de_c: "dec", **{v: k for k, v in want.items() if v}})
    d = d.dropna(subset=["ra", "dec", "apo_logg", "apo_teff"]).reset_index(drop=True)
    if "apo_id" in d:
        d = d.drop_duplicates("apo_id").reset_index(drop=True)
    d.insert(0, "rid", np.arange(len(d)))
    d = nearest(d, "I/355/gaiadr3", 1.5, ["Source", "Gmag", "BPmag", "RPmag", "Plx", "e_Plx", "RUWE"], "g_")
    d = nearest(d, "I/355/paramp", 1.5, ["Source", "Teff", "logg", "[Fe/H]", "Teff-S", "logg-S", "[M/H]-S", "Flags",
                                          "ClassELS", "f_ClassELS"], "ap_")
    d = nearest(d, "V/164/stellar5", 3.0, ["ObsID", "Teff", "logg", "[Fe/H]"], "lam_")
    return d


def els(per_class: int) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    parts = []
    for lab in ELS_LABELS:
        v = Vizier(columns=["Source", "RA_ICRS", "DE_ICRS", "ClassELS", "f_ClassELS", "EWHa", "Teff", "logg"],
                   row_limit=per_class, timeout=600)
        try:
            res = retry(lambda: v.query_constraints(catalog="I/355/paramp", ClassELS=f"={lab}"), tries=3, wait=20)
        except Exception as exc:
            print(f"ESP-ELS {lab}: failed {str(exc)[:160]}", flush=True)
            continue
        n = len(res[0]) if res else 0
        print(f"ESP-ELS {lab}: {n}", flush=True)
        if n:
            parts.append(res[0].to_pandas())
    d = pd.concat(parts, ignore_index=True).drop_duplicates("Source")
    d = d.rename(columns={"RA_ICRS": "ra", "DE_ICRS": "dec"})
    d.insert(0, "rid", np.arange(len(d)))
    return simbad(d)


def lpv_lamost() -> pd.DataFrame:
    d = pd.read_csv(BENCH / "agb_truth" / "agb_gate_sample.csv.gz", low_memory=False)
    d = d.rename(columns={"agb_id": "rid"})
    return nearest(d, "V/164/dr5", 3.0, ["ObsID", "Class", "SubClass", "snrg"], "lam_")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--parts", default="apogee,els,lpv")
    p.add_argument("--apogee-slices", type=int, default=24)
    p.add_argument("--apogee-per-slice", type=int, default=400)
    p.add_argument("--els-per-class", type=int, default=1500)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = set(a.parts.split(","))
    if "apogee" in parts:
        d = apogee(a.apogee_per_slice, a.apogee_slices)
        d.to_csv(OUT / "apogee.csv.gz", index=False, compression="gzip")
        print("apogee ->", d.shape, d.notna().mean().round(2).to_dict(), flush=True)
    if "els" in parts:
        d = els(a.els_per_class)
        d.to_csv(OUT / "els.csv.gz", index=False, compression="gzip")
        print("els ->", d.shape, d.ClassELS.value_counts().to_dict(), flush=True)
    if "lpv" in parts:
        d = lpv_lamost()
        d.to_csv(OUT / "lpv_lamost.csv.gz", index=False, compression="gzip")
        print("lpv ->", d.shape, d.get("lam_SubClass", pd.Series(dtype=str)).value_counts().head(15).to_dict(), flush=True)


if __name__ == "__main__":
    main()

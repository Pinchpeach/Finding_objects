#!/usr/bin/env python3
"""Spectroscopic catalogue products for the benchmark objects, to validate the
spectroscopic sub-class criteria (Classifier/subclass.py).

* SDSS galaxies of truth_data/ground_truth.csv: emission-line fluxes and
  equivalent widths, and the 4000 A break, from the MPA-JHU tables
  (galSpecLine, galSpecIndx; Brinchmann et al. 2004, Kauffmann et al. 2003)
  and the Portsmouth emission-line fits (emissionLinesPort; Thomas et al.
  2013) by specobjid.
* Benchmark stars (Gaia DR3 positions of catalog_features/gaia_dr3_trd):
  Gaia DR3 astrophysical parameters (VizieR I/355/paramp: GSP-Spec from RVS
  spectra, ESP-ELS emission-line class) and LAMOST DR5 LASP parameters
  (VizieR V/164 stellar tables), nearest source.

All catalogue columns are kept (the column names are checked here, not
assumed).  Runs in GitHub Actions (.github/workflows/build-spectro-truth.yml);
output: v2/benchmark/spectro_truth/*.csv.gz
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import retry  # noqa: E402

MPA_SQL = """SELECT l.specobjid, l.h_alpha_flux, l.h_alpha_flux_err, l.h_beta_flux, l.h_beta_flux_err,
 l.oiii_5007_flux, l.oiii_5007_flux_err, l.nii_6584_flux, l.nii_6584_flux_err,
 l.h_alpha_eqw, l.h_alpha_eqw_err, l.nii_6584_eqw, l.nii_6584_eqw_err, l.sigma_balmer, i.d4000_n, i.d4000_n_err
 FROM galSpecLine AS l LEFT JOIN galSpecIndx AS i ON i.specobjid = l.specobjid
 WHERE l.specobjid IN ({ids})"""
PORT_SQL = "SELECT * FROM emissionLinesPort WHERE specobjid IN ({ids})"


def sdss_sql(template: str, ids: list[str], name: str, chunk: int = 400) -> pd.DataFrame:
    from astroquery.sdss import SDSS
    parts = []
    for s0 in range(0, len(ids), chunk):
        q = template.format(ids=",".join(ids[s0:s0 + chunk]))
        t0 = time.time()
        try:
            t = retry(lambda: SDSS.query_sql(q, data_release=18, timeout=600), tries=3, wait=20)
        except Exception as exc:
            print(f"{name} rows {s0}+: failed {str(exc)[:200]}", flush=True)
            continue
        if t is not None and len(t):
            parts.append(t.to_pandas())
        print(f"{name} rows {s0}-{s0 + chunk}: {0 if t is None else len(t)} in {time.time() - t0:.0f} s", flush=True)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out.columns = [c.lower() for c in out.columns]
    out["specobjid"] = out["specobjid"].astype("uint64").astype(str)
    return out


def asu_all(df: pd.DataFrame, table: str, radius: float, chunk: int = 500) -> pd.DataFrame:
    """Nearest row of a VizieR table, all columns, for each (benchmark_id, ra, dec)."""
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    v = Vizier(columns=["**", "+_r"], row_limit=-1, timeout=600)
    parts = []
    for s0 in range(0, len(df), chunk):
        sub = df.iloc[s0:s0 + chunk]
        coords = SkyCoord(sub.ra.to_numpy() * u.deg, sub.dec.to_numpy() * u.deg)
        t0 = time.time()
        try:
            res = retry(lambda: v.query_region(coords, radius=radius * u.arcsec, catalog=table), tries=3, wait=20)
        except Exception as exc:
            print(f"{table} rows {s0}+: failed {str(exc)[:200]}", flush=True)
            continue
        if not res:
            continue
        t = res[0].to_pandas()
        t["benchmark_id"] = sub.benchmark_id.to_numpy()[t["_q"].astype(int).to_numpy() - 1]
        parts.append(t.sort_values("_r").drop_duplicates("benchmark_id"))
        print(f"{table} rows {s0}-{s0 + len(sub)}: {len(parts[-1])} matched in {time.time() - t0:.0f} s", flush=True)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    print(f"{table}: {len(out)} rows; columns: {' '.join(map(str, out.columns))}", flush=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=BENCH / "spectro_truth")
    p.add_argument("--parts", default="galaxies,gaia,lamost")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    parts = set(a.parts.split(","))
    truth = pd.read_csv(BENCH / "truth_data" / "ground_truth.csv", dtype={"specobjid": str}, low_memory=False)
    if "galaxies" in parts:
        gal = truth[truth["class"].eq("GALAXY")]
        ids = gal.specobjid.dropna().astype(str).tolist()
        print(f"{len(ids)} SDSS galaxies", flush=True)
        mpa = sdss_sql(MPA_SQL, ids, "galSpecLine")
        port = sdss_sql(PORT_SQL, ids, "emissionLinesPort")
        out = gal[["benchmark_id", "specobjid", "subclass", "z"]]
        if not mpa.empty:
            out = out.merge(mpa.drop_duplicates("specobjid").add_prefix("mpa_").rename(columns={"mpa_specobjid": "specobjid"}),
                            on="specobjid", how="left")
        if not port.empty:
            keep = ["specobjid"] + [c for c in port.columns if c.startswith(("flux_", "ew_", "sigma_", "bpt"))]
            out = out.merge(port[keep].drop_duplicates("specobjid").add_prefix("port_").rename(columns={"port_specobjid": "specobjid"}),
                            on="specobjid", how="left")
            print("Portsmouth columns:", " ".join(port.columns), flush=True)
        out.to_csv(a.out / "sdss_galaxy_lines.csv.gz", index=False, compression="gzip")
        print("galaxies ->", out.shape, flush=True)
    pos = pd.read_csv(BENCH / "catalog_features" / "gaia_dr3_trd.csv.gz", usecols=["benchmark_id", "truth_class", "ra", "dec", "source_id"],
                      low_memory=False)
    stars = pos[pos.truth_class.eq("STAR")].dropna(subset=["ra", "dec"]).drop_duplicates("benchmark_id").reset_index(drop=True)
    print(f"{len(stars)} benchmark stars with Gaia positions", flush=True)
    if "gaia" in parts:
        ap = asu_all(stars, "I/355/paramp", 1.0)
        if not ap.empty:
            ap.to_csv(a.out / "star_gaia_ap.csv.gz", index=False, compression="gzip")
    if "lamost" in parts:
        for table in ("V/164/stellar5", "V/164/mstars5", "V/164/dr5"):
            t = asu_all(stars, table, 3.0)
            if not t.empty:
                t.to_csv(a.out / f"star_lamost_{table.split('/')[-1]}.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()

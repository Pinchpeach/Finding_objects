#!/usr/bin/env python3
"""Truth set for AGB chemistry (C-rich vs O-rich) with Gaia, 2MASS and AllWISE photometry.

Labels: Suh (2021, ApJS 256, 43; VizieR J/ApJS/256/43) AllWISE-based tables
11 (O-rich AGB, "OAGB_WISE") and 12 (C-rich AGB, "CAGB_WISE"); the labels
come from spectra / IR spectral features collected in that catalogue.
Photometry comes from the Gaia archive (CDS XMatch timed out on this sample;
a designation-string join scanned the full 2MASS table):

* Gaia DR3 G, BP, RP, parallax, RUWE within 2" of the AllWISE position;
* 2MASS PSC J, H, Ks and AllWISE W1-W4 of that Gaia source through the
  official best-neighbour tables;
* Gaia DR3 LPV ``is_cstar`` (gaiadr3.vari_long_period_variable; Lebzelter et
  al. 2023) for an independent check.

Run by .github/workflows/build-agb-chemistry-truth.yml (archives are not
reachable from every environment); output: v2/benchmark/agb_truth/agb_chemistry_truth.csv.gz
"""
from __future__ import annotations
import argparse, time
from pathlib import Path
import pandas as pd

TABLES = {"J/ApJS/256/43/table11": "O", "J/ApJS/256/43/table12": "C"}
def retry(fn, tries=6, wait=30):
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:  # archive overload ("Too many jobs", 503) is common
            print(f"  attempt {i + 1} failed: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            if i == tries - 1:
                raise
            time.sleep(wait * (i + 1))


def labels() -> pd.DataFrame:
    from astroquery.vizier import Vizier
    frames = []
    for table, chem in TABLES.items():
        t = retry(lambda: Vizier(columns=["**"], row_limit=-1).get_catalogs(table))[0].to_pandas()
        ra = next(c for c in ("RAJ2000", "RAdeg", "_RAJ2000", "RA_ICRS") if c in t)
        de = next(c for c in ("DEJ2000", "DEdeg", "_DEJ2000", "DE_ICRS") if c in t)
        out = pd.DataFrame({"ra": pd.to_numeric(t[ra], errors="coerce"), "dec": pd.to_numeric(t[de], errors="coerce")})
        if out.ra.isna().all():  # sexagesimal columns
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            c = SkyCoord(t[ra].astype(str), t[de].astype(str), unit=(u.hourangle, u.deg))
            out = pd.DataFrame({"ra": c.ra.deg, "dec": c.dec.deg})
        out["chem"] = chem
        out["suh_table"] = table.split("/")[-1]
        for col in t.columns:      # keep the catalogue's own identifiers / classes
            if col in {"WISEA", "2MASS", "OW-N", "CW-N", "AType", "APer", "Var", "Simbad", "Ref"}:
                out[f"suh_{col}"] = t[col].astype(str).to_numpy()
        frames.append(out)
        print(f"{table}: {len(out)} rows, columns {list(t.columns)[:25]}", flush=True)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["ra", "dec"])
    df.insert(0, "agb_id", [f"AGB{i:05d}" for i in range(len(df))])
    return df


GAIA_Q = """SELECT u.agb_id, g.source_id AS g_source_id,
       DISTANCE(POINT(u.ra, u.dec), POINT(g.ra, g.dec)) * 3600 AS g_sep,
       g.phot_g_mean_mag AS g_gmag, g.phot_bp_mean_mag AS g_bp, g.phot_rp_mean_mag AS g_rp,
       g.parallax AS g_plx, g.parallax_error AS g_eplx, g.ruwe AS g_ruwe,
       l.is_cstar AS lpv_is_cstar, l.frequency AS lpv_frequency, l.amplitude AS lpv_amplitude
FROM tap_upload.ids AS u
JOIN gaiadr3.gaia_source AS g ON 1 = CONTAINS(POINT(g.ra, g.dec), CIRCLE(u.ra, u.dec, 2.0 / 3600.0))
LEFT JOIN gaiadr3.vari_long_period_variable AS l ON l.source_id = g.source_id"""
# Gaia archive documentation: tmass_psc_xsc_join.original_psc_source_id is the
# 2MASS designation (joins tmass_original_valid.designation).
TMASS_Q = """SELECT u.agb_id, tm.j_m AS tm_j, tm.h_m AS tm_h, tm.ks_m AS tm_ks, tm.ph_qual AS tm_qual
FROM tap_upload.ids AS u
JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xn ON xn.source_id = u.g_source_id
JOIN gaiadr3.tmass_psc_xsc_join AS xj ON xj.clean_tmass_psc_xsc_oid = xn.clean_tmass_psc_xsc_oid
JOIN gaiadr1.tmass_original_valid AS tm ON tm.designation = xj.original_psc_source_id"""
WISE_Q = """SELECT u.agb_id, aw.w1mpro AS aw_w1, aw.w1mpro_error AS aw_ew1, aw.w2mpro AS aw_w2, aw.w2mpro_error AS aw_ew2,
       aw.w3mpro AS aw_w3, aw.w3mpro_error AS aw_ew3, aw.w4mpro AS aw_w4, aw.w4mpro_error AS aw_ew4
FROM tap_upload.ids AS u
JOIN gaiadr3.allwise_best_neighbour AS an ON an.source_id = u.g_source_id
JOIN gaiadr1.allwise_original_valid AS aw ON aw.allwise_oid = an.allwise_oid"""


def _run(query: str, table: pd.DataFrame, name: str, chunk: int = 2000):
    """Run ``query`` on ``table`` uploaded in chunks; a 50-row probe first, so a
    query error shows up in seconds.  Returns a DataFrame or None."""
    from astroquery.gaia import Gaia
    from astropy.table import Table
    def one(part):
        return Gaia.launch_job_async(query, upload_resource=Table.from_pandas(part),
                                     upload_table_name="ids").get_results().to_pandas()
    try:
        probe = one(table.head(50))
        print(f"{name}: probe ok ({len(probe)} rows from 50)", flush=True)
    except Exception as exc:
        print(f"{name}: probe failed: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return None
    parts = []
    for s0 in range(0, len(table), chunk):
        part = table.iloc[s0:s0 + chunk]
        t0 = time.time()
        try:
            res = retry(lambda: one(part), tries=3)
        except Exception as exc:
            print(f"{name}: rows {s0}+ failed: {str(exc)[:200]}", flush=True)
            continue
        print(f"{name}: rows {s0}-{s0 + len(part)}: {len(res)} in {time.time() - t0:.0f} s", flush=True)
        parts.append(res)
    return pd.concat(parts, ignore_index=True) if parts else None


def gaia_tap(df: pd.DataFrame) -> pd.DataFrame:
    """Gaia DR3 (2" from the AllWISE position) with the Gaia LPV C-star flag, then
    2MASS and AllWISE photometry of that Gaia source through the archive's
    best-neighbour tables (Marrese et al. 2019).  Each part is optional."""
    g = _run(GAIA_Q, df[["agb_id", "ra", "dec"]], "gaia")
    if g is None:
        return df
    g = g.sort_values("g_sep").drop_duplicates("agb_id")
    df = df.merge(g, on="agb_id", how="left")
    ids = df.dropna(subset=["g_source_id"])[["agb_id", "g_source_id"]].copy()
    ids["g_source_id"] = ids["g_source_id"].astype("int64")
    for q, name in ((TMASS_Q, "2mass"), (WISE_Q, "allwise")):
        res = _run(q, ids, name)
        if res is not None:
            df = df.merge(res.drop_duplicates("agb_id"), on="agb_id", how="left")
    return df


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "agb_truth" / "agb_chemistry_truth.csv.gz")
    a = p.parse_args()
    df = gaia_tap(labels())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(df.chem.value_counts().to_dict(), "->", a.out)


if __name__ == "__main__":
    main()

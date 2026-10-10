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


def gaia_tap(df: pd.DataFrame, chunk: int = 2000) -> pd.DataFrame:
    """Gaia DR3, 2MASS, AllWISE and Gaia LPV columns for the Suh stars.

    Indexed route of the Gaia archive (Marrese et al. 2019 best-neighbour
    tables): a 2" positional join to gaia_source (Q3C index), then
    tmass_psc_xsc_best_neighbour -> tmass_psc_xsc_join -> tmass_original_valid
    and allwise_best_neighbour -> allwise_original_valid by their keys.
    Joining the 2MASS designation strings directly scanned the whole table.
    """
    from astroquery.gaia import Gaia
    from astropy.table import Table
    q = """SELECT u.agb_id, g.source_id AS g_source_id, DISTANCE(POINT(u.ra, u.dec), POINT(g.ra, g.dec)) * 3600 AS g_sep,
       g.phot_g_mean_mag AS g_gmag, g.phot_bp_mean_mag AS g_bp, g.phot_rp_mean_mag AS g_rp,
       g.parallax AS g_plx, g.parallax_error AS g_eplx, g.ruwe AS g_ruwe,
       tm.j_m AS tm_j, tm.h_m AS tm_h, tm.ks_m AS tm_ks, tm.ph_qual AS tm_qual,
       aw.w1mpro AS aw_w1, aw.w1mpro_error AS aw_ew1, aw.w2mpro AS aw_w2, aw.w2mpro_error AS aw_ew2,
       aw.w3mpro AS aw_w3, aw.w3mpro_error AS aw_ew3, aw.w4mpro AS aw_w4, aw.w4mpro_error AS aw_ew4,
       l.is_cstar AS lpv_is_cstar, l.frequency AS lpv_frequency, l.amplitude AS lpv_amplitude
FROM tap_upload.ids AS u
JOIN gaiadr3.gaia_source AS g ON 1 = CONTAINS(POINT(g.ra, g.dec), CIRCLE(u.ra, u.dec, 2.0 / 3600.0))
LEFT JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xn ON xn.source_id = g.source_id
LEFT JOIN gaiadr3.tmass_psc_xsc_join AS xj ON xj.clean_tmass_psc_xsc_oid = xn.clean_tmass_psc_xsc_oid
LEFT JOIN gaiadr1.tmass_original_valid AS tm ON tm.tmass_oid = xj.original_psc_source_id
LEFT JOIN gaiadr3.allwise_best_neighbour AS an ON an.source_id = g.source_id
LEFT JOIN gaiadr1.allwise_original_valid AS aw ON aw.allwise_oid = an.allwise_oid
LEFT JOIN gaiadr3.vari_long_period_variable AS l ON l.source_id = g.source_id"""
    parts = []
    for s0 in range(0, len(df), chunk):
        up = Table.from_pandas(df[["agb_id", "ra", "dec"]].iloc[s0:s0 + chunk])
        t0 = time.time()
        res = retry(lambda: Gaia.launch_job_async(q, upload_resource=up, upload_table_name="ids").get_results(),
                    tries=3).to_pandas()
        print(f"rows {s0}-{s0 + len(up)}: {len(res)} matches in {time.time() - t0:.0f} s", flush=True)
        parts.append(res)
    res = pd.concat(parts, ignore_index=True).sort_values("g_sep").drop_duplicates("agb_id")
    print(f"Gaia matches: {len(res)} / {len(df)}", flush=True)
    return df.merge(res, on="agb_id", how="left")


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

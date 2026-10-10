#!/usr/bin/env python3
"""Truth set for AGB chemistry (C-rich vs O-rich) with Gaia, 2MASS and AllWISE photometry.

Labels: Suh (2021, ApJS 256, 43; VizieR J/ApJS/256/43) AllWISE-based tables
11 (O-rich AGB, "OAGB_WISE") and 12 (C-rich AGB, "CAGB_WISE"); the labels
come from spectra / IR spectral features collected in that catalogue.
Photometry comes from the Gaia archive by identifier (the Suh tables carry
the 2MASS and AllWISE designations, so no positional cross-match is needed;
CDS XMatch timed out on this sample):

* 2MASS PSC J, H, Ks (gaiadr1.tmass_original_valid, by 2MASS designation);
* AllWISE W1-W4 (gaiadr1.allwise_original_valid, by AllWISE designation);
* Gaia DR3 G, BP, RP, parallax, RUWE via the Gaia-2MASS best-neighbour table
  (gaiadr3.tmass_psc_xsc_best_neighbour);
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


def gaia_tap(df: pd.DataFrame) -> pd.DataFrame:
    """2MASS, AllWISE, Gaia DR3 and Gaia LPV columns for the Suh stars, by designation."""
    from astroquery.gaia import Gaia
    from astropy.table import Table
    ids = df[["agb_id"]].copy()
    ids["tmass"] = df.get("suh_2MASS", pd.Series("", index=df.index)).fillna("").astype(str).str.replace("J", "", regex=False).str.strip()
    ids["wisea"] = df.get("suh_WISEA", pd.Series("", index=df.index)).fillna("").astype(str).str.replace("WISEA ", "", regex=False).str.strip()
    up = Table.from_pandas(ids)
    queries = {
        "tm": ("SELECT u.agb_id, tm.* FROM tap_upload.ids AS u "
               "JOIN gaiadr1.tmass_original_valid AS tm ON tm.designation = u.tmass"),
        "aw": ("SELECT u.agb_id, aw.* FROM tap_upload.ids AS u "
               "JOIN gaiadr1.allwise_original_valid AS aw ON aw.designation = u.wisea"),
        "g": ("SELECT u.agb_id, g.source_id, g.phot_g_mean_mag, g.phot_bp_mean_mag, g.phot_rp_mean_mag, "
              "g.parallax, g.parallax_error, g.ruwe FROM tap_upload.ids AS u "
              "JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xn ON xn.original_ext_source_id = u.tmass "
              "JOIN gaiadr3.gaia_source AS g ON g.source_id = xn.source_id"),
        "lpv": ("SELECT u.agb_id, l.is_cstar, l.median_delta_wl_rp, l.frequency, l.amplitude FROM tap_upload.ids AS u "
                "JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xn ON xn.original_ext_source_id = u.tmass "
                "JOIN gaiadr3.vari_long_period_variable AS l ON l.source_id = xn.source_id"),
    }
    print("example ids:", ids.head(3).to_dict("records"), flush=True)
    for key, q in queries.items():
        try:
            res = retry(lambda: Gaia.launch_job_async(q, upload_resource=up, upload_table_name="ids").get_results(),
                        tries=4).to_pandas()
        except Exception as exc:
            print(f"{key}: failed ({type(exc).__name__}: {str(exc)[:200]})", flush=True)
            continue
        res = res.drop_duplicates("agb_id")
        res = res.rename(columns={c: f"{key}_{c}" for c in res.columns if c != "agb_id"})
        print(f"{key}: {len(res)} / {len(df)} rows; columns {list(res.columns)[:30]}", flush=True)
        df = df.merge(res, on="agb_id", how="left")
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

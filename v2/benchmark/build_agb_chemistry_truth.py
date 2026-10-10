#!/usr/bin/env python3
"""Truth set for AGB chemistry (C-rich vs O-rich) with Gaia, 2MASS and AllWISE photometry.

Labels: Suh (2021, ApJS 256, 43; VizieR J/ApJS/256/43) AllWISE-based tables
11 (O-rich AGB, "OAGB_WISE") and 12 (C-rich AGB, "CAGB_WISE"); the labels
come from spectra / IR spectral features collected in that catalogue.
Photometry is cross-matched with CDS XMatch around the AllWISE positions:

* Gaia DR3 (I/355/gaiadr3) within 1.5": G, BP, RP, parallax, RUWE;
* 2MASS PSC (II/246/out) within 1.5": J, H, Ks;
* AllWISE (II/328/allwise) within 1.0": W1-W4 with errors;
* Gaia DR3 LPV table (gaiadr3.vari_long_period_variable, Lebzelter et al.
  2023): ``is_cstar`` for an independent check, via Gaia TAP.

Run by .github/workflows/build-agb-chemistry-truth.yml (archives are not
reachable from every environment); output: v2/benchmark/agb_truth/agb_chemistry_truth.csv.gz
"""
from __future__ import annotations
import argparse, time
from pathlib import Path
import pandas as pd

TABLES = {"J/ApJS/256/43/table11": "O", "J/ApJS/256/43/table12": "C"}
XMATCH = {
    "gaia": ("vizier:I/355/gaiadr3", 1.5, ["Source", "Gmag", "BPmag", "RPmag", "Plx", "e_Plx", "RUWE"]),
    "tmass": ("vizier:II/246/out", 1.5, ["2MASS", "Jmag", "e_Jmag", "Hmag", "e_Hmag", "Kmag", "e_Kmag", "Qflg"]),
    "wise": ("vizier:II/328/allwise", 1.0, ["AllWISE", "W1mag", "e_W1mag", "W2mag", "e_W2mag", "W3mag", "e_W3mag", "W4mag", "e_W4mag", "ccf"]),
}


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
            if col.lower() in {"wisea", "allwise", "ow-n", "cw-n", "class", "type", "obj", "sptype"}:
                out[f"suh_{col}"] = t[col].astype(str).to_numpy()
        frames.append(out)
        print(f"{table}: {len(out)} rows, columns {list(t.columns)[:25]}", flush=True)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["ra", "dec"])
    df.insert(0, "agb_id", [f"AGB{i:05d}" for i in range(len(df))])
    return df


def xmatch(df: pd.DataFrame, name: str) -> pd.DataFrame:
    from astroquery.xmatch import XMatch
    import astropy.units as u
    from astropy.table import Table
    cat, radius, cols = XMATCH[name]
    rows = []
    for s in range(0, len(df), 5000):
        part = Table.from_pandas(df[["agb_id", "ra", "dec"]].iloc[s:s + 5000])
        res = retry(lambda: XMatch.query(cat1=part, cat2=cat, max_distance=radius * u.arcsec, colRA1="ra", colDec1="dec"))
        rows.append(res.to_pandas())
        time.sleep(5)
    m = pd.concat(rows, ignore_index=True).sort_values("angDist").drop_duplicates("agb_id")
    keep = ["agb_id", "angDist"] + [c for c in cols if c in m.columns]
    m = m[keep].rename(columns={c: f"{name}_{c}" for c in keep if c != "agb_id"})
    print(f"{name}: {len(m)} / {len(df)} matched", flush=True)
    return df.merge(m, on="agb_id", how="left")


def lpv_flags(df: pd.DataFrame) -> pd.DataFrame:
    from astroquery.gaia import Gaia
    from astropy.table import Table
    ids = pd.to_numeric(df.get("gaia_Source"), errors="coerce").dropna().astype("int64").unique()
    if len(ids) == 0:
        return df
    q = ("SELECT l.source_id, l.is_cstar, l.median_delta_wl_rp, l.frequency, l.amplitude "
         "FROM gaiadr3.vari_long_period_variable AS l JOIN tap_upload.ids AS u ON l.source_id = u.source_id")
    tab = Table({"source_id": ids})
    res = retry(lambda: Gaia.launch_job_async(q, upload_resource=tab, upload_table_name="ids").get_results()).to_pandas()
    res = res.rename(columns={c: f"lpv_{c}" for c in res.columns if c != "source_id"})
    print(f"Gaia LPV: {len(res)} of {len(ids)} Gaia sources are DR3 LPVs", flush=True)
    df["gaia_Source"] = pd.to_numeric(df["gaia_Source"], errors="coerce").astype("Int64")
    return df.merge(res.rename(columns={"source_id": "gaia_Source"}), on="gaia_Source", how="left")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "agb_truth" / "agb_chemistry_truth.csv.gz")
    a = p.parse_args()
    df = labels()
    for name in XMATCH:
        df = xmatch(df, name)
    try:
        df = lpv_flags(df)
    except Exception as exc:
        print(f"Gaia LPV flags skipped: {exc}", flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(df.chem.value_counts().to_dict(), "->", a.out)


if __name__ == "__main__":
    main()

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


VIZIER_TAP = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap"
VIZIER_Q = {
    "gaia": """SELECT u.agb_id, g.Source AS g_source_id, g.Gmag AS g_gmag, g.BPmag AS g_bp, g.RPmag AS g_rp,
       g.Plx AS g_plx, g.e_Plx AS g_eplx, g.RUWE AS g_ruwe,
       DISTANCE(POINT('ICRS', u.ra, u.dec), POINT('ICRS', g.RA_ICRS, g.DE_ICRS)) * 3600 AS g_sep
FROM TAP_UPLOAD.ids AS u JOIN "I/355/gaiadr3" AS g
  ON 1 = CONTAINS(POINT('ICRS', g.RA_ICRS, g.DE_ICRS), CIRCLE('ICRS', u.ra, u.dec, 2.0 / 3600.0))""",
    "2mass": """SELECT u.agb_id, t.Jmag AS tm_j, t.Hmag AS tm_h, t.Kmag AS tm_ks, t.Qflg AS tm_qual,
       DISTANCE(POINT('ICRS', u.ra, u.dec), POINT('ICRS', t.RAJ2000, t.DEJ2000)) * 3600 AS tm_sep
FROM TAP_UPLOAD.ids AS u JOIN "II/246/out" AS t
  ON 1 = CONTAINS(POINT('ICRS', t.RAJ2000, t.DEJ2000), CIRCLE('ICRS', u.ra, u.dec, 2.0 / 3600.0))""",
    "allwise": """SELECT u.agb_id, w.W1mag AS aw_w1, w.e_W1mag AS aw_ew1, w.W2mag AS aw_w2, w.e_W2mag AS aw_ew2,
       w.W3mag AS aw_w3, w.e_W3mag AS aw_ew3, w.W4mag AS aw_w4, w.e_W4mag AS aw_ew4,
       DISTANCE(POINT('ICRS', u.ra, u.dec), POINT('ICRS', w.RAJ2000, w.DEJ2000)) * 3600 AS aw_sep
FROM TAP_UPLOAD.ids AS u JOIN "II/328/allwise" AS w
  ON 1 = CONTAINS(POINT('ICRS', w.RAJ2000, w.DEJ2000), CIRCLE('ICRS', u.ra, u.dec, 1.0 / 3600.0))""",
}
VIZIER_LPV_Q = """SELECT u.agb_id, v.isCstar AS lpv_is_cstar, v.Freq AS lpv_frequency, v.Amp AS lpv_amplitude
FROM TAP_UPLOAD.ids AS u JOIN "I/358/vlpv" AS v ON v.Source = u.g_source_id"""


def vizier_tap(df: pd.DataFrame, chunk: int = 2000) -> pd.DataFrame:
    """Same columns from TAPVizieR (positional joins: Gaia 2", 2MASS 2", AllWISE 1";
    Gaia DR3 LPV I/358/vlpv by Gaia source id).  Fallback when the Gaia archive is down."""
    import pyvo
    from astropy.table import Table
    svc = pyvo.dal.TAPService(VIZIER_TAP)

    def run(query, table, name):
        parts = []
        for s0 in range(0, len(table), chunk):
            part = Table.from_pandas(table.iloc[s0:s0 + chunk])
            t0 = time.time()
            try:
                res = retry(lambda: svc.run_async(query, uploads={"ids": part}).to_table().to_pandas(), tries=3)
            except Exception as exc:
                print(f"{name}: rows {s0}+ failed: {str(exc)[:200]}", flush=True)
                continue
            print(f"{name}: rows {s0}-{s0 + len(part)}: {len(res)} in {time.time() - t0:.0f} s", flush=True)
            parts.append(res)
        return pd.concat(parts, ignore_index=True) if parts else None

    base = df[["agb_id", "ra", "dec"]]
    for name, q in VIZIER_Q.items():
        res = run(q, base, name)
        if res is None:
            continue
        sep = [c for c in res.columns if c.endswith("_sep")]
        res = res.sort_values(sep[0]).drop_duplicates("agb_id") if sep else res.drop_duplicates("agb_id")
        df = df.merge(res, on="agb_id", how="left")
    if "g_source_id" in df:
        ids = df.dropna(subset=["g_source_id"])[["agb_id", "g_source_id"]].copy()
        ids["g_source_id"] = ids["g_source_id"].astype("int64")
        res = run(VIZIER_LPV_Q, ids, "lpv")
        if res is not None:
            df = df.merge(res.drop_duplicates("agb_id"), on="agb_id", how="left")
    return df


ASU_CATALOGS = {   # name: (VizieR table, radius arcsec, columns, renames)
    "gaia": ("I/355/gaiadr3", 2.0, ["Source", "Gmag", "BPmag", "RPmag", "Plx", "e_Plx", "RUWE"],
             {"Source": "g_source_id", "Gmag": "g_gmag", "BPmag": "g_bp", "RPmag": "g_rp", "Plx": "g_plx",
              "e_Plx": "g_eplx", "RUWE": "g_ruwe"}),
    "2mass": ("II/246/out", 2.0, ["Jmag", "Hmag", "Kmag", "Qflg"],
              {"Jmag": "tm_j", "Hmag": "tm_h", "Kmag": "tm_ks", "Qflg": "tm_qual"}),
    "allwise": ("II/328/allwise", 1.0, ["W1mag", "e_W1mag", "W2mag", "e_W2mag", "W3mag", "e_W3mag", "W4mag", "e_W4mag"],
                {"W1mag": "aw_w1", "e_W1mag": "aw_ew1", "W2mag": "aw_w2", "e_W2mag": "aw_ew2", "W3mag": "aw_w3",
                 "e_W3mag": "aw_ew3", "W4mag": "aw_w4", "e_W4mag": "aw_ew4"}),
    "lpv": ("I/358/vlpv", 2.0, ["isCstar", "Freq", "Amp"],
            {"isCstar": "lpv_is_cstar", "Freq": "lpv_frequency", "Amp": "lpv_amplitude"}),
}


def vizier_asu(df: pd.DataFrame, chunk: int = 500, catalogs: dict | None = None) -> pd.DataFrame:
    """Multi-position cone searches on the standard VizieR service (the route that
    fetched the Suh tables; TAPVizieR uploads failed).  Nearest source per star."""
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    for name, (table, radius, cols, ren) in (catalogs or ASU_CATALOGS).items():
        v = Vizier(columns=cols + ["+_r"], row_limit=-1, timeout=600)
        parts = []
        for s0 in range(0, len(df), chunk):
            sub = df.iloc[s0:s0 + chunk]
            coords = SkyCoord(sub.ra.to_numpy() * u.deg, sub.dec.to_numpy() * u.deg)
            t0 = time.time()
            try:
                res = retry(lambda: v.query_region(coords, radius=radius * u.arcsec, catalog=table), tries=3, wait=20)
            except Exception as exc:
                print(f"{name}: rows {s0}+ failed: {str(exc)[:200]}", flush=True)
                continue
            if not res:
                continue
            t = res[0].to_pandas()
            t["agb_id"] = sub.agb_id.to_numpy()[t["_q"].astype(int).to_numpy() - 1]   # _q: 1-based input row
            parts.append(t.sort_values("_r").drop_duplicates("agb_id"))
            print(f"{name}: rows {s0}-{s0 + len(sub)}: {len(parts[-1])} matched in {time.time() - t0:.0f} s", flush=True)
        if parts:
            t = pd.concat(parts, ignore_index=True).rename(columns=ren)
            t = t.rename(columns={"_r": f"{name}_sep"})
            keep = ["agb_id", f"{name}_sep"] + [c for c in ren.values() if c in t.columns]
            df = df.merge(t[keep], on="agb_id", how="left")
    return df


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "agb_truth" / "agb_chemistry_truth.csv.gz")
    p.add_argument("--source", choices=("gaia", "vizier", "asu"), default="asu",
                   help="photometry service: VizieR cone searches (asu), TAPVizieR uploads (vizier) or the Gaia archive")
    a = p.parse_args()
    df = {"gaia": gaia_tap, "vizier": vizier_tap, "asu": vizier_asu}[a.source](labels())
    phot = [c for c in df.columns if c.startswith(("g_", "tm_", "aw_"))]
    if not phot or df[phot].notna().any(axis=1).mean() < 0.2:
        # Never overwrite the truth file with labels only (archive outage).
        raise SystemExit(f"photometry missing for most stars (columns {phot}); not writing {a.out}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(df.chem.value_counts().to_dict(), "->", a.out)


if __name__ == "__main__":
    main()

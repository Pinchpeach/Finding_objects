#!/usr/bin/env python3
"""Cross-query balanced truth coordinates against existing v2 catalog collectors."""

from __future__ import annotations
import argparse, importlib.util, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np, pandas as pd

V2 = Path(__file__).resolve().parents[1]
GET = V2 / "Get_data"
DEFAULT_TRUTH = Path(__file__).resolve().parent / "truth_data" / "ground_truth.csv"
DEFAULT_OUT = Path(__file__).resolve().parent / "catalog_data"
RADII = {
    "gaia_dr3": 0.10,
    "panstarrs1": 0.10,
    "allwise": 0.15,
    "twomass": 0.10,
    "galex": 0.15,
    "desi_legacy": 0.10,
    "nvss": 0.25,
    "first": 0.10,
    "lotss": 0.15,
    "vlass": 0.10,
    "chandra": 0.15,
    "xmm": 0.20,
    "erosita": 0.30,
    "ztf_lightcurve": 0.05,
}
COLLECTORS = list(RADII)  # query order
MATCH_ARCSEC = {
    "gaia_dr3": 2.0,
    "panstarrs1": 2.0,
    "allwise": 3.0,
    "twomass": 2.5,
    "galex": 5.0,
    "desi_legacy": 2.0,
    "nvss": 10.0,
    "first": 3.0,
    "lotss": 5.0,
    "vlass": 3.0,
    "chandra": 5.0,
    "xmm": 8.0,
    "erosita": 10.0,
    "ztf_lightcurve": 1.5,
}


def load(name):
    # Collectors import their shared helpers (_catalog_utils) by module name,
    # as Get_data/controller.py does with Get_data on sys.path.
    if str(GET) not in sys.path:
        sys.path.insert(0, str(GET))
    p = GET / f"{name}.py"
    s = importlib.util.spec_from_file_location("trd_" + name, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def sep_arcsec(ra1, dec1, ra2, dec2):
    r1, d1, r2, d2 = map(np.radians, [ra1, dec1, ra2, dec2])
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin((r2 - r1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))) * 3600


def query_one(mod, name, radius, t):
    for attempt in range(5):
        try:
            d = mod.fetch(float(t.ra), float(t.dec), radius)
            break
        except Exception as e:
            last = e
            # MAST/other public services can throttle bursts. Retry transient failures,
            # with stronger backoff for explicit HTTP 429 responses (and IRSA
            # ZTF refusals, which come back as HTTP 400 under load).
            delay = (2**attempt) * (1.0 if "429" in repr(e) or "IRSA ZTF HTTP" in repr(e) else 0.5)
            if attempt < 4:
                time.sleep(delay)
    else:  # all attempts failed
        return "error", None, repr(last)
    try:
        if d is None or d.empty:
            return "empty", None, None
        d = d.copy()
        d["_sep_arcsec"] = sep_arcsec(
            float(t.ra),
            float(t.dec),
            pd.to_numeric(d.ra, errors="coerce").to_numpy(),
            pd.to_numeric(d.dec, errors="coerce").to_numpy(),
        )
        d = (
            d[np.isfinite(d["_sep_arcsec"]) & (d["_sep_arcsec"] <= MATCH_ARCSEC[name])]
            .sort_values("_sep_arcsec")
            .head(1)
        )
        if d.empty:
            return "empty", None, None
        d.insert(0, "benchmark_id", t.benchmark_id)
        d.insert(1, "truth_class", t.truth_class)
        d.insert(2, "truth_source", t.truth_source)
        d.insert(3, "truth_ra", t.ra)
        d.insert(4, "truth_dec", t.dec)
        d.insert(5, "match_threshold_arcsec", MATCH_ARCSEC[name])
        return "matched", d, None
    except Exception as e:
        return "error", None, repr(e)


# Gaia DR3 positions are at epoch 2016.0 (Lindegren et al. 2021); SDSS truth
# positions are 1998-2008 imaging.  A 0.3"/yr M dwarf moves ~5" in between,
# so high-motion stars missed the 2" match and had no Gaia evidence at all
# (8 of 9 SDSS test stars left UNKNOWN in 2.25.0).  Candidates are searched
# within PM_SEARCH_ARCSEC and the Gaia position is moved to the truth epoch
# (the spectrum MJD, ``mjd``, when the truth set has one) before the 2" test.
PM_SEARCH_ARCSEC = 15.0
GAIA_EPOCH = 2016.0


def _finish(name, out_dir, targets, out=None, matched=0, empty=None, errors=0):
    """Write ``<name>_trd.csv`` (an empty table when ``out`` is None) and
    return the catalog's coverage-summary row."""
    if out is None:
        out = pd.DataFrame(columns=["benchmark_id", "truth_class"])
    out.to_csv(out_dir / f"{name}_trd.csv", index=False)
    counts = out["truth_class"].value_counts().to_dict() if len(out) else {}
    return {
        "catalog": name,
        "targets": targets,
        "matched": matched,
        "empty": targets - matched if empty is None else empty,
        "errors": errors,
        **{c: counts.get(c, 0) for c in ("STAR", "GALAXY", "QSO")},
    }


def _truth_epoch(truth):
    if "mjd" in truth.columns:
        mjd = pd.to_numeric(truth["mjd"], errors="coerce")
        return (2000.0 + (mjd - 51544.5) / 365.25).fillna(GAIA_EPOCH)
    return pd.Series(GAIA_EPOCH, index=truth.index)


def run_gaia(truth, out_dir):
    from astroquery.xmatch import XMatch
    from astropy.table import Table
    import astropy.units as u

    mod = load("gaia_dr3")
    # Gaia Archive can be unstable during DR4 preparation.  For benchmark
    # crossmatching use the CDS/VizieR mirror of the Gaia DR3 main-source table,
    # which supports a single bulk XMatch for all truth coordinates.
    upload = truth[["benchmark_id", "ra", "dec"]].rename(columns={"ra": "truth_ra", "dec": "truth_dec"}).copy()
    epoch = dict(zip(truth.benchmark_id, _truth_epoch(truth)))
    try:
        xm = XMatch.query(
            cat1=Table.from_pandas(upload),
            cat2="vizier:I/355/gaiadr3",
            max_distance=PM_SEARCH_ARCSEC * u.arcsec,
            colRA1="truth_ra",
            colDec1="truth_dec",
        ).to_pandas()
    except Exception as e:
        print(f"[gaia_dr3] CDS XMatch ERROR {e!r}", flush=True)
        return _finish("gaia_dr3", out_dir, len(truth), errors=1)
    if xm.empty:
        return _finish("gaia_dr3", out_dir, len(truth))

    # Normalize VizieR Gaia DR3 column names to the same schema used by the native
    # Gaia collector.  Missing optional fields remain NaN rather than being forged.
    mp = {
        "Source": "source_id",
        "RA_ICRS": "ra",
        "DE_ICRS": "dec",
        "RAdeg": "ra",
        "DEdeg": "dec",
        "e_RA_ICRS": "ra_error",
        "e_DE_ICRS": "dec_error",
        "Plx": "parallax",
        "e_Plx": "parallax_error",
        "pmRA": "pmra",
        "e_pmRA": "pmra_error",
        "pmDE": "pmdec",
        "e_pmDE": "pmdec_error",
        "RUWE": "ruwe",
        "FG": "phot_g_mean_flux",
        "e_FG": "phot_g_mean_flux_error",
        "Gmag": "phot_g_mean_mag",
        "FBP": "phot_bp_mean_flux",
        "e_FBP": "phot_bp_mean_flux_error",
        "BPmag": "phot_bp_mean_mag",
        "FRP": "phot_rp_mean_flux",
        "e_FRP": "phot_rp_mean_flux_error",
        "RPmag": "phot_rp_mean_mag",
        "BP-RP": "bp_rp",
        "RV": "radial_velocity",
        "e_RV": "radial_velocity_error",
        "Teff": "teff_gspphot",
        "logg": "logg_gspphot",
    }
    for old, new in mp.items():
        if old in xm.columns and new not in xm.columns:
            xm = xm.rename(columns={old: new})
    if "source_id" not in xm.columns:
        raise KeyError(f"Gaia VizieR XMatch missing source identifier; columns={list(xm.columns)}")
    if "ra" not in xm.columns or "dec" not in xm.columns:
        raise KeyError(f"Gaia VizieR XMatch missing coordinates; columns={list(xm.columns)}")
    # Gaia position moved to the truth epoch (no motion: unchanged).
    dt = xm["benchmark_id"].map(epoch).astype(float) - GAIA_EPOCH
    pmra = pd.to_numeric(xm.get("pmra"), errors="coerce").fillna(0.0)
    pmdec = pd.to_numeric(xm.get("pmdec"), errors="coerce").fillna(0.0)
    g_dec = pd.to_numeric(xm["dec"], errors="coerce")
    g_ra = pd.to_numeric(xm["ra"], errors="coerce")
    dec_t = g_dec + pmdec * dt / 3.6e6
    ra_t = g_ra + pmra * dt / 3.6e6 / np.cos(np.radians(g_dec))
    xm["_sep_arcsec"] = sep_arcsec(
        pd.to_numeric(xm["truth_ra"], errors="coerce").to_numpy(),
        pd.to_numeric(xm["truth_dec"], errors="coerce").to_numpy(),
        ra_t.to_numpy(),
        dec_t.to_numpy(),
    )
    sep = pd.to_numeric(xm["_sep_arcsec"], errors="coerce")
    xm = xm[np.isfinite(sep) & (sep <= MATCH_ARCSEC["gaia_dr3"])]
    xm = xm.sort_values(["benchmark_id", "_sep_arcsec"]).drop_duplicates("benchmark_id", keep="first")
    # Gaia DSC-Combmod class probabilities live in the astrophysical-parameter
    # table (I/355/paramp); join them by source_id when available.
    try:
        ap = XMatch.query(
            cat1=Table.from_pandas(upload),
            cat2="vizier:I/355/paramp",
            max_distance=PM_SEARCH_ARCSEC * u.arcsec,
            colRA1="truth_ra",
            colDec1="truth_dec",
        ).to_pandas()
        dsc = {
            "PQSO": "classprob_dsc_combmod_quasar",
            "PGal": "classprob_dsc_combmod_galaxy",
            "Pstar": "classprob_dsc_combmod_star",
            "PWD": "classprob_dsc_combmod_whitedwarf",
            "Pbin": "classprob_dsc_combmod_binarystar",
        }
        if "Source" in ap.columns and set(dsc) <= set(ap.columns):
            ap = ap[["Source", *dsc]].rename(columns={"Source": "source_id", **dsc}).drop_duplicates("source_id")
            xm = xm.merge(ap, on="source_id", how="left")
            print(
                f"[gaia_dr3] DSC joined for {int(xm['classprob_dsc_combmod_star'].notna().sum())} sources", flush=True
            )
    except Exception as e:
        print(f"[gaia_dr3] DSC XMatch skipped: {e!r}", flush=True)
    xm.insert(0, "catalog", mod.CATALOG)
    xm.insert(1, "catalog_object_id", pd.to_numeric(xm["source_id"], errors="coerce").astype("Int64").astype(str))
    xm.insert(2, "object_name", "Gaia DR3 " + xm["catalog_object_id"].astype(str))
    meta = truth[["benchmark_id", "truth_class", "truth_source", "ra", "dec"]].rename(
        columns={"ra": "truth_ra_meta", "dec": "truth_dec_meta"}
    )
    out = meta.merge(xm, on="benchmark_id", how="inner")
    # Keep the benchmark truth coordinates in canonical columns.
    out["truth_ra"] = out.pop("truth_ra_meta")
    out["truth_dec"] = out.pop("truth_dec_meta")
    out["match_threshold_arcsec"] = MATCH_ARCSEC["gaia_dr3"]
    out = out.sort_values("benchmark_id")
    ok = len(out)
    print(f"[gaia_dr3] CDS targets={len(truth)} matched={ok} empty={len(truth)-ok}", flush=True)
    return _finish("gaia_dr3", out_dir, len(truth), out, matched=ok)


def run_catalog(name, truth, out_dir, workers):
    if name == "gaia_dr3":
        return run_gaia(truth, out_dir)
    mod = load(name)
    radius = RADII[name]
    rows = []
    ok = empty = errors = done = 0
    # Pan-STARRS MAST endpoint throttles aggressive parallel cone searches.
    workers = min(workers, 2) if name == "panstarrs1" else workers
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(query_one, mod, name, radius, t): t for _, t in truth.iterrows()}
        for f in as_completed(futs):
            t = futs[f]
            status, d, err = f.result()
            done += 1
            if status == "matched":
                rows.append(d)
                ok += 1
            elif status == "empty":
                empty += 1
            else:
                errors += 1
                print(f"[{name}] {t.benchmark_id} ERROR {err}", flush=True)
            if done % 25 == 0 or done == len(truth):
                print(f"[{name}] {done}/{len(truth)} matched={ok} empty={empty} errors={errors}", flush=True)
    out = pd.concat(rows, ignore_index=True).sort_values("benchmark_id") if rows else None
    return _finish(name, out_dir, len(truth), out, matched=ok, empty=empty, errors=errors)


def run(truth_path, out_dir, limit=None, catalog=None, workers=8, shard=None):
    truth = pd.read_csv(truth_path)
    if limit:
        truth = pd.concat([g.head(limit) for _, g in truth.groupby("truth_class")], ignore_index=True)
    if shard:
        # k/n: every n-th object from k, so a slow service (IRSA ZTF light
        # curves, ~minutes per cone at 8 workers) can be split over runners.
        k, n = map(int, shard.split("/"))
        truth = truth.iloc[k::n].reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = [catalog] if catalog else COLLECTORS
    summary = [run_catalog(name, truth, out_dir, workers) for name in names]
    pd.DataFrame(summary).to_csv(out_dir / "catalog_coverage.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--limit-per-class", type=int)
    p.add_argument("--catalog", choices=COLLECTORS)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--shard", help="k/n: collect every n-th truth object starting at k (0-based)")
    a = p.parse_args()
    run(a.truth, a.out_dir, a.limit_per_class, a.catalog, max(1, a.workers), a.shard)


if __name__ == "__main__":
    main()

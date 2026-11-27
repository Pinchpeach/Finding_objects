#!/usr/bin/env python3
"""Bulk-crossmatch STAR-branch spectroscopy truth to Gaia DR3 via CDS XMatch."""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


VIZIER_RETRIES = 4  # attempts at a batch before its error is raised (a refused connection, an error status, a timeout: as before 2.61.6)
VIZIER_RETRIES_UNREADABLE = 2  # attempts whose answer could not be read before a batch larger than MIN_SPLIT is halved
RETRY_SLEEP_S = 15.0  # backoff after a failed attempt, on top of the 3-5 s pause before every request (throttle)
MIN_SPLIT = 50  # the batch is halved down to this many positions
# VizieR cones are centred on the catalogue's J2000 positions, which for
# Gaia DR3 are propagated from epoch 2016.0 by the proper motion; CDS XMatch
# matches the epoch-2016 RA_ICRS / DE_ICRS.  The fallback queries this much
# wider and measures the separation on RA_ICRS / DE_ICRS, so the 2" cut in
# run() keeps the XMatch meaning (a white dwarf moving 0.5"/yr is 8" apart
# between the two epochs; 59 of 290 LAMOST WD matches move > 1").
EPOCH_MARGIN_ARCSEC = 10.0


def _unreadable_answer(e: Exception) -> bool:
    """The failure is about the answer, not about reaching a mirror: its body was cut off (a connection reset
    during the transfer, a VOTable that stops half way) or the parser rejected it.  A long answer is what a mirror
    cuts off, so a smaller batch is the remedy; a refused connection or an error status is not about the size."""
    import requests

    text = f"{type(e).__name__} {e}"
    return isinstance(e, (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError, ValueError, SyntaxError)) or any(
        k in text for k in ("TableParseError", "no element found", "cut off", "ChunkedEncodingError", "IncompleteRead")
    )


def _batch_rows(v, chunk: pd.DataFrame, radius_arcsec: float, cct, throttle, halvable: bool) -> pd.DataFrame | None:
    """Gaia DR3 rows of the VizieR copy around the positions of ``chunk``, in the XMatch layout (None: no row).

    One attempt is one multi-target request, which ``throttle`` already sends to the VizieR mirrors in turn when one
    refuses, times out, answers an error status or cuts the VOTable off.  An attempt that still fails (the answer could
    not be read: ``TableParseError`` of a body that is complete but wrong, a failure of every mirror) marks the mirror
    of the last answer as failing (``throttle.distrust_last_mirror``), so the next attempt goes to another mirror, not
    to the one that just failed (until 2.61.6 a retry asked the same preferred mirror four times).  After
    ``VIZIER_RETRIES`` failures the last exception is raised; a ``halvable`` batch (larger than MIN_SPLIT) gives up
    after ``VIZIER_RETRIES_UNREADABLE`` unreadable answers, so that the caller halves it.  An outage (every mirror
    refuses, times out or answers an error status) keeps the four attempts of the code before 2.61.6: it says nothing
    about the size, and fewer attempts would only end the crossmatch sooner (2.61.6 review, CI run 46055319902)."""
    import time

    from astropy.coordinates import SkyCoord
    import astropy.units as u

    coords = SkyCoord(chunk.ra.to_numpy(float) * u.deg, chunk.dec.to_numpy(float) * u.deg)
    unreadable = 0
    for attempt in range(VIZIER_RETRIES):
        try:
            # astroquery caches an answer before it parses it: a retry with the cache would read the same unreadable body
            # again and never reach ``throttle`` (Codex review of 2.61.6), so retries go to the network
            res = v.query_region(coords, radius=(radius_arcsec + EPOCH_MARGIN_ARCSEC) * u.arcsec, catalog="I/355/gaiadr3", cache=attempt == 0)
            break
        except Exception as e:  # noqa: BLE001 - transient transfer / parse / server errors
            mirror = throttle.distrust_last_mirror()
            print(f"[collect_star_gaia] VizieR batch of {len(chunk)} (mirror {mirror}): {e!r}; attempt {attempt + 1}/{VIZIER_RETRIES}", flush=True)
            unreadable += _unreadable_answer(e)
            if attempt == VIZIER_RETRIES - 1 or (halvable and unreadable >= VIZIER_RETRIES_UNREADABLE):
                raise
            time.sleep(RETRY_SLEEP_S * (attempt + 1))
    if not len(res):
        return None
    part = cct.from_vizier_batch(res[0].to_pandas(), chunk)
    if {"RA_ICRS", "DE_ICRS"} <= set(part.columns):  # epoch 2016.0, as CDS XMatch
        part["angDist"] = cct.sep_arcsec(
            part.truth_ra.to_numpy(float),
            part.truth_dec.to_numpy(float),
            pd.to_numeric(part.RA_ICRS, errors="coerce").to_numpy(),
            pd.to_numeric(part.DE_ICRS, errors="coerce").to_numpy(),
        )
    return part


def _vizier_fallback(truth: pd.DataFrame, radius_arcsec: float) -> pd.DataFrame:
    import importlib.util
    import sys

    v2 = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(v2 / "Get_data"))
    import throttle  # VizieR mirror failover (CfA / NAOJ / IUCAA ...)

    throttle.install()
    spec = importlib.util.spec_from_file_location("v2_collect_catalog_truth", v2 / "benchmark" / "collect_catalog_truth.py")
    cct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cct)
    from astroquery.vizier import Vizier

    # cct.vizier_multi's batches (500 positions, the XMatch layout through cct.from_vizier_batch), each retried over
    # the mirrors (_batch_rows).  An answer cut off in transfer (ChunkedEncodingError, 2026-11-14; a VOTable cut off,
    # CI run 2026-11-27, and a connection reset by CfA for every 500-position batch from this container) ended a
    # 30-minute crossmatch: when the answer cannot be read the batch is halved, and the smaller size is kept for the
    # rest (the result does not depend on how the positions are batched: each truth object keeps its nearest row).
    v = Vizier(columns=["**"], row_limit=-1)
    v.TIMEOUT = 300
    t = truth[["benchmark_id", "ra", "dec"]]
    parts = []
    size, i = cct.VIZIER_BATCH, 0
    while i < len(t):
        chunk = t.iloc[i : i + size]
        small = len(chunk) <= MIN_SPLIT
        try:
            part = _batch_rows(v, chunk, radius_arcsec, cct, throttle, halvable=not small)
        except Exception as e:  # noqa: BLE001
            if small or not _unreadable_answer(e):
                raise
            size = max(MIN_SPLIT, len(chunk) // 2)
            print(f"[collect_star_gaia] VizieR answers of {len(chunk)} positions are unreadable: batches of {size} from here on", flush=True)
            continue
        if part is not None and len(part):
            parts.append(part)
        i += len(chunk)
        print(f"[collect_star_gaia] VizieR batch {i}/{len(t)}", flush=True)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["benchmark_id", "angDist"])


def run(truth_path: Path, out: Path, max_sep_arcsec: float = 2.0, min_matches: int = 500):
    from astroquery.xmatch import XMatch
    from astropy.table import Table
    import astropy.units as u

    truth = pd.read_csv(truth_path)
    req = {"benchmark_id", "ra", "dec", "star_truth_class"}
    if not req.issubset(truth.columns):
        raise KeyError(f"truth missing {sorted(req-set(truth.columns))}")
    upload = truth[["benchmark_id", "ra", "dec"]].rename(columns={"ra": "truth_ra", "dec": "truth_dec"})
    try:
        xm = XMatch.query(
            cat1=Table.from_pandas(upload),
            cat2="vizier:I/355/gaiadr3",
            max_distance=max_sep_arcsec * u.arcsec,
            colRA1="truth_ra",
            colDec1="truth_dec",
        ).to_pandas()
    except Exception as e:  # noqa: BLE001
        # cdsxmatch.u-strasbg.fr refuses connections at times (2026-11-12,
        # 2026-11-13): the same Gaia table through VizieR multi-target
        # queries with mirror failover, as benchmark/collect_catalog_truth.py
        # does since 2.51.3 (angDist / truth_ra / truth_dec in the XMatch layout).
        print(f"[collect_star_gaia] CDS XMatch ERROR {e!r}; trying VizieR multi-target batches", flush=True)
        xm = _vizier_fallback(truth, max_sep_arcsec)
    mp = {
        "Source": "source_id",
        "RA_ICRS": "ra",
        "DE_ICRS": "dec",
        "RAdeg": "ra",
        "DEdeg": "dec",
        "Plx": "parallax",
        "e_Plx": "parallax_error",
        "pmRA": "pmra",
        "e_pmRA": "pmra_error",
        "pmDE": "pmdec",
        "e_pmDE": "pmdec_error",
        "RUWE": "ruwe",
        "Gmag": "phot_g_mean_mag",
        "BPmag": "phot_bp_mean_mag",
        "RPmag": "phot_rp_mean_mag",
        "BP-RP": "bp_rp",
        "FG": "phot_g_mean_flux",
        "e_FG": "phot_g_mean_flux_error",
        "FBP": "phot_bp_mean_flux",
        "e_FBP": "phot_bp_mean_flux_error",
        "FRP": "phot_rp_mean_flux",
        "e_FRP": "phot_rp_mean_flux_error",
        "E(BP/RP)": "phot_bp_rp_excess_factor",
    }
    for old, new in mp.items():
        if old in xm.columns and new not in xm.columns:
            xm = xm.rename(columns={old: new})
    if "angDist" in xm.columns:
        xm["_sep_arcsec"] = pd.to_numeric(xm["angDist"], errors="coerce")
    else:

        def sep(ra1, dec1, ra2, dec2):
            r1, d1, r2, d2 = map(np.radians, [ra1, dec1, ra2, dec2])
            a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin((r2 - r1) / 2) ** 2
            return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))) * 3600

        xm["_sep_arcsec"] = sep(
            pd.to_numeric(xm.truth_ra, errors="coerce"),
            pd.to_numeric(xm.truth_dec, errors="coerce"),
            pd.to_numeric(xm.ra, errors="coerce"),
            pd.to_numeric(xm.dec, errors="coerce"),
        )
    xm = xm[pd.to_numeric(xm["_sep_arcsec"], errors="coerce") <= max_sep_arcsec]
    xm = xm.sort_values(["benchmark_id", "_sep_arcsec"]).drop_duplicates("benchmark_id")
    meta = truth[
        [
            c
            for c in ("benchmark_id", "star_truth_class", "truth_source", "truth_quality", "origin_class")
            if c in truth.columns
        ]
    ]
    outdf = meta.merge(xm, on="benchmark_id", how="inner")
    out.parent.mkdir(parents=True, exist_ok=True)
    outdf.to_csv(out, index=False)
    cov = len(outdf) / len(truth)
    print(f"[OK] truth={len(truth)} Gaia matched={len(outdf)} coverage={cov:.4f} -> {out}")
    print(outdf.star_truth_class.value_counts().to_string())
    if len(outdf) < min_matches:
        raise RuntimeError(f"Gaia coverage too low: {len(outdf)}/{len(truth)}; min_matches={min_matches}")
    return out


def main():
    p = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent
    p.add_argument("--truth", type=Path, default=root / "star_truth.csv")
    p.add_argument("--out", type=Path, default=root / "star_gaia_features.csv")
    p.add_argument("--min-matches", type=int, default=500)
    a = p.parse_args()
    run(a.truth, a.out, min_matches=a.min_matches)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""How long one VizieR mirror takes to answer a multi-target Gaia DR3 request of N positions (2.62.12).

    python probe_vizier_batch.py --truth v2/benchmark/truth_data/ground_truth.csv --hosts vizier.cfa.harvard.edu vizier.idia.ac.za \
        --sizes 50 125 250 500 --repeats 2 --out OUT

Why.  The WD HR-gates run of 2026-11-28 (46108906185, Strasbourg answering 404) sent the 500-position batches of
``Classifier/collect_star_gaia.py`` to CfA first: CfA answered HTTP 504 after 60.3 s, three times, and every batch went on to
IDIA, which answered in 78-819 s.  A 504 at a fixed 60 s is the gateway's time limit, not an outage (CfA answers small queries
normally), so the remedy is a batch size per mirror, not a smaller batch for every mirror.  This tool measures the size: one
request per (host, size, repeat), sent to that host only (no failover, no cache), the same positions for every host.

The request is the collector's: ``I/355/gaiadr3``, all columns, radius 2" + the 10" epoch margin of ``collect_star_gaia.py``,
positions taken in file order from the truth table (repeat k of size N = rows k*500 .. k*500+N-1, so the repeats do not overlap
and the server cannot answer from a cache).  Between two requests the 3-5 s pause of ``Get_data/throttle.py``.  After every repeat
of a size has failed on a host, the larger sizes are not sent to it (they would fail the same way).

Written (``OUT``): ``vizier_batch_probe.csv`` (host, size, repeat, first_row, status, seconds, bytes, rows, error),
``vizier_batch_summary.md`` (per host and size: answered, median and max seconds, positions per second) and ``run_info.json``.
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "benchmark"))
import run_info as RI  # noqa: E402

CATALOG = "I/355/gaiadr3"
RADIUS_ARCSEC = 2.0 + 10.0  # collect_star_gaia.py: the 2" match + EPOCH_MARGIN_ARCSEC
CONNECT_S, READ_S = 10.0, 900.0  # the collector's read timeout is 300 s; a longer one shows how long a mirror really takes


def request(host: str, chunk: pd.DataFrame) -> dict:
    """One multi-target request of ``chunk`` to ``host`` only: status, seconds, bytes, rows or the error."""
    import astropy.units as u
    import requests
    from astropy.coordinates import SkyCoord
    from astropy.io.votable import parse_single_table
    from astroquery.vizier import Vizier

    v = Vizier(columns=["**"], row_limit=-1)
    v.VIZIER_SERVER = host
    coords = SkyCoord(chunk.ra.to_numpy(float) * u.deg, chunk.dec.to_numpy(float) * u.deg)
    payload = v.query_region(coords, radius=RADIUS_ARCSEC * u.arcsec, catalog=CATALOG, get_query_payload=True)
    url = v._server_to_url(return_type="votable")
    t0 = time.monotonic()
    out = dict(status="", seconds=float("nan"), bytes=0, rows=-1, error="")
    try:
        r = requests.post(url, data=payload, timeout=(CONNECT_S, READ_S))
        out.update(status=str(r.status_code), seconds=round(time.monotonic() - t0, 1), bytes=len(r.content))
        if r.status_code == 200:
            try:
                out["rows"] = len(parse_single_table(io.BytesIO(r.content)).array)
            except Exception as e:  # noqa: BLE001 - a body that does not parse (cut off, no table) is a result here
                out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    except Exception as e:  # noqa: BLE001 - refused, timeout, reset: a result here
        out.update(status=type(e).__name__, seconds=round(time.monotonic() - t0, 1), error=str(e)[:160])
    return out


def summarize(t: pd.DataFrame) -> pd.DataFrame:
    ok = t[(t.status == "200") & (t.rows >= 0)]
    g = t.groupby(["host", "size"]).agg(sent=("status", "size")).join(
        ok.groupby(["host", "size"]).agg(answered=("status", "size"), median_s=("seconds", "median"), max_s=("seconds", "max")), how="left")
    g["answered"] = g.answered.fillna(0).astype(int)
    g["positions_per_s"] = (g.index.get_level_values("size") / g.median_s).round(2)
    fails = t[~t.index.isin(ok.index)].groupby(["host", "size"]).status.agg(lambda s: ", ".join(f"{k} x{n}" for k, n in s.value_counts().items()))
    g["failures"] = fails.reindex(g.index).fillna("")
    return g.reset_index()


def probe(truth: pd.DataFrame, hosts: list[str], sizes: list[int], repeats: int, send=None, sleep=time.sleep) -> pd.DataFrame:
    """One row per request, sizes in increasing order; a host whose every repeat of a size failed is not sent the larger sizes."""
    send = send or request
    rows, given_up, first = [], set(), True
    for size in sorted(sizes):
        for k in range(repeats):
            chunk = truth.iloc[k * 500 : k * 500 + size]
            for host in hosts:
                if host in given_up:
                    continue
                if not first:
                    sleep(random.uniform(3.0, 5.0))  # the pause of Get_data/throttle.py
                first = False
                r = dict(host=host, size=size, repeat=k, first_row=k * 500, **send(host, chunk))
                rows.append(r)
                print(f"[probe] {host} size {size} repeat {k}: {r['status']} {r['seconds']} s {r['bytes']} B rows {r['rows']} {r['error']}", flush=True)
        t = pd.DataFrame(rows)
        for host in hosts:
            mine = t[(t.host == host) & (t["size"] == size)]
            if len(mine) and not ((mine.status == "200") & (mine.rows >= 0)).any():
                given_up.add(host)
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--truth", type=Path, required=True, help="a table with ra, dec (the WD HR-gates mixed set: benchmark/truth_data/ground_truth.csv)")
    ap.add_argument("--hosts", nargs="+", required=True)
    ap.add_argument("--sizes", nargs="+", type=int, default=[50, 125, 250, 500])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    truth = pd.read_csv(a.truth, usecols=["ra", "dec"]).dropna().reset_index(drop=True)
    if a.repeats * 500 > len(truth) or max(a.sizes) > 500:
        raise SystemExit("repeats of up to 500 positions must fit in the truth table without overlap")
    t = probe(truth, a.hosts, a.sizes, a.repeats)
    t.to_csv(a.out / "vizier_batch_probe.csv", index=False)
    s = summarize(t)
    md = "### VizieR multi-target batch probe (I/355/gaiadr3, radius 12\")\n\n" + s.to_markdown(index=False) + "\n"
    (a.out / "vizier_batch_summary.md").write_text(md)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    RI.write_args(a, ["truth"], t0=t0, note="hosts: " + " ".join(a.hosts) + "; sizes: " + " ".join(map(str, a.sizes)) + f"; repeats {a.repeats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

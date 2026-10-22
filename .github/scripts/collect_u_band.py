"""u-band (and SkyMapper v) photometry at the benchmark truth positions
(2.36.0 experiment): does a u band separate the stars and quasars the
classifier still confuses?

One CDS XMatch request per (truth set, survey) uploads the truth positions and
returns every catalogue column within 1.5".  Surveys and their u depth:
  SDSS DR16 (single epoch, u ~ 22; Alam et al. 2015)
  SDSS Stripe 82 co-add (u ~ 23.9 5-sigma; Jiang et al. 2014 / Annis et al. 2014)
  KiDS DR4 (u ~ 24, GAaP; Kuijken et al. 2019)
  SkyMapper DR4 (u, v ~ 20; Onken et al. 2024)
VizieR identifiers are tried in order; the log lists what answered and the
columns, because they are checked here for the first time.

usage: python collect_u_band.py OUT_DIR
Every request waits 3-5 s first (v2/Get_data/throttle.py).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "v2/Get_data")
import throttle  # noqa: E402

throttle.install()

TRUTH = {
    "sdss": "v2/benchmark/truth_data/ground_truth.csv",
    "desi_external": "v2/benchmark/desi_external/truth.csv",
    "desi_fusion": "v2/benchmark/desi_fusion/truth.csv",
}
SURVEYS = {
    "sdss_dr16": ["V/154/sdss16"],
    "s82_coadd": ["J/ApJS/213/12/table1", "J/ApJS/213/12", "J/ApJ/794/120/catalog", "J/ApJ/794/120"],
    "kids_dr4": ["II/347/kids_dr4", "II/347"],
    "skymapper_dr4": ["II/379/smssdr4", "II/379", "II/358/smss"],
}


PROBE_S, FULL_S = 90, 600  # hard limits per XMatch request (a dead identifier must not stall the run)


def _bounded(fn, seconds):
    import threading

    box = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as exc:  # reported by the caller
            box["e"] = exc

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(seconds)
    if "v" in box:
        return box["v"]
    raise box.get("e") or TimeoutError(f"no answer in {seconds} s")


def main(out):
    import astropy.units as u
    from astropy.table import Table
    from astroquery.xmatch import XMatch

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log = {"probe": {}, "xmatch": {}}
    truth = {k: pd.read_csv(v, usecols=["benchmark_id", "ra", "dec"]).dropna() for k, v in TRUTH.items()}
    sample = Table.from_pandas(truth["desi_external"].head(5))

    def xm(table, cid, seconds):
        return _bounded(
            lambda: XMatch.query(cat1=table, cat2=f"vizier:{cid}", max_distance=1.5 * u.arcsec, colRA1="ra", colDec1="dec"),
            seconds,
        )

    # 1. Which identifier answers (5 positions, 90 s each).
    chosen = {}
    for sname, ids in SURVEYS.items():
        for cid in ids:
            try:
                r = xm(sample, cid, PROBE_S)
                log["probe"][cid] = {"ok": True, "rows": len(r), "columns": list(r.colnames)}
                chosen[sname] = cid
                print(f"[u] probe {sname} {cid}: ok, {len(r)} rows, columns {list(r.colnames)[:25]}", flush=True)
                break
            except Exception as exc:
                log["probe"][cid] = f"{type(exc).__name__}: {str(exc)[:160]}"
                print(f"[u] probe {sname} {cid}: {log['probe'][cid]}", flush=True)
    (out / "collect_log.json").write_text(json.dumps(log, indent=1, default=str))
    # 2. Full uploads with the identifiers that answered; each file is written as soon as it arrives.
    for tname, t in truth.items():
        up = Table.from_pandas(t)
        for sname, cid in chosen.items():
            key = f"{tname}/{sname}/{cid}"
            try:
                df = xm(up, cid, FULL_S).to_pandas()
            except Exception as exc:
                log["xmatch"][key] = f"failed: {type(exc).__name__}: {str(exc)[:160]}"
                print(f"[u] {key}: {log['xmatch'][key]}", flush=True)
                continue
            df.insert(0, "u_catalog", cid)
            df.to_csv(out / f"{tname}__{sname}.csv.gz", index=False)
            log["xmatch"][key] = {"rows": len(df), "unique_ids": int(df.benchmark_id.nunique())}
            print(f"[u] {key}: {len(df)} rows, {df.benchmark_id.nunique()} objects", flush=True)
            (out / "collect_log.json").write_text(json.dumps(log, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])

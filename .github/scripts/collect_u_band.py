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
SEARCH = ["Stripe 82 coadd", "Stripe 82 co-add", "KiDS DR4", "SkyMapper DR4", "CFIS u-band", "UNIONS"]


def main(out):
    import astropy.units as u
    from astropy.table import Table
    from astroquery.vizier import Vizier
    from astroquery.xmatch import XMatch

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log = {"search": {}, "xmatch": {}}
    for w in SEARCH:
        try:
            log["search"][w] = {k: v.description for k, v in list(Vizier.find_catalogs(w).items())[:12]}
        except Exception as exc:
            log["search"][w] = f"failed: {exc!r}"[:200]
    print(json.dumps(log["search"], indent=1))
    XMatch.TIMEOUT = 600
    for tname, tpath in TRUTH.items():
        t = pd.read_csv(tpath, usecols=["benchmark_id", "ra", "dec"]).dropna()
        up = Table.from_pandas(t)
        for sname, ids in SURVEYS.items():
            done = False
            for cid in ids:
                try:
                    res = XMatch.query(
                        cat1=up, cat2=f"vizier:{cid}", max_distance=1.5 * u.arcsec, colRA1="ra", colDec1="dec"
                    )
                except Exception as exc:
                    log["xmatch"][f"{tname}/{sname}/{cid}"] = f"failed: {type(exc).__name__}: {str(exc)[:160]}"
                    print(f"[u] {tname} {sname} {cid}: {log['xmatch'][f'{tname}/{sname}/{cid}']}", flush=True)
                    continue
                df = res.to_pandas()
                df.insert(0, "u_catalog", cid)
                df.to_csv(out / f"{tname}__{sname}.csv.gz", index=False)
                log["xmatch"][f"{tname}/{sname}/{cid}"] = {"rows": len(df), "unique_ids": int(df.benchmark_id.nunique()), "columns": list(df.columns)}
                print(f"[u] {tname} {sname} {cid}: {len(df)} rows, {df.benchmark_id.nunique()} objects", flush=True)
                done = True
                break
            if not done:
                print(f"[u] {tname} {sname}: no identifier answered", flush=True)
    (out / "collect_log.json").write_text(json.dumps(log, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])

"""Pan-STARRS1 multi-epoch variability at the u-band target list (2026-10-22
experiment): do quasars' stochastic variations (MacLeod et al. 2010) separate
the stars and quasars the classifier still confuses?

* PS1 DR2 MeanObject per-band statistics (MAST catalogs API): the standard
  deviation of the single-epoch PSF magnitudes, the number of epochs and the
  error of the mean (Flewelling et al. 2020).  About 12 epochs per band over
  ~4 years in the 3pi survey (Chambers et al. 2016).
* PS1 3pi variability classification (Hernitschek et al. 2016, ApJ 817, 73):
  QSO / RR Lyrae probabilities from structure-function fits; VizieR
  identifiers tried in order, the log records what answered.

usage: python collect_ps1_var.py TARGETS_CSV OUT_DIR
Every request waits 3-5 s first (v2/Get_data/throttle.py).
"""

import io
import json
import sys
import threading
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, "v2/Get_data")
import throttle  # noqa: E402

throttle.install()

MAST = "https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/mean.csv"
BANDS = "grizy"
COLS = ["objID", "raMean", "decMean", "nDetections", "objInfoFlag", "qualityFlag"] + [
    f"{b}{k}" for b in BANDS for k in ("MeanPSFMag", "MeanPSFMagErr", "MeanPSFMagStd", "MeanPSFMagNpt", "MeanPSFMagMin", "MeanPSFMagMax")
]
HERNITSCHEK = ["J/ApJ/817/73/table3", "J/ApJ/817/73"]


def _bounded(fn, seconds):
    box = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as exc:
            box["e"] = exc

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(seconds)
    if "v" in box:
        return box["v"]
    raise box.get("e") or TimeoutError(f"no answer in {seconds} s")


def ps1(ra, dec):
    r = requests.get(
        MAST,
        params={"ra": f"{ra:.10f}", "dec": f"{dec:.10f}", "radius": f"{1.5 / 3600:.10f}", "columns": "[" + ",".join(COLS) + "]"},
        timeout=60,
    )
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def main(targets, out):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tg = pd.read_csv(targets)
    log = {"ps1_fail": 0, "hern_probe": {}, "hern_fail": 0}
    # Hernitschek catalogue: which identifier answers (30' around the first target)
    hern = None
    c0 = SkyCoord(tg.ra.iloc[0] * u.deg, tg.dec.iloc[0] * u.deg)
    for cid in HERNITSCHEK:
        try:
            r = _bounded(lambda: Vizier(columns=["**"], row_limit=3).query_region(c0, radius=60 * u.arcmin, catalog=cid), 90)
            log["hern_probe"][cid] = {"tables": [t.meta.get("name") for t in r], "columns": list(r[0].colnames) if len(r) else []}
            print(f"[var] probe {cid}: {log['hern_probe'][cid]}", flush=True)
            if len(r):
                hern = r[0].meta.get("name", cid)
                break
        except Exception as exc:
            log["hern_probe"][cid] = f"{type(exc).__name__}: {str(exc)[:160]}"
            print(f"[var] probe {cid}: {log['hern_probe'][cid]}", flush=True)
    p_rows, h_rows = [], []
    v = Vizier(columns=["**", "_r"], row_limit=5)
    for i, row in tg.iterrows():
        try:
            d = _bounded(lambda: ps1(row.ra, row.dec), 90)
            if len(d):
                d.insert(0, "benchmark_id", row.benchmark_id)
                p_rows.append(d)
        except Exception as exc:
            log["ps1_fail"] += 1
            print(f"[var] ps1 {row.benchmark_id}: {type(exc).__name__}: {str(exc)[:100]}", flush=True)
        if hern:
            try:
                res = _bounded(lambda: v.query_region(SkyCoord(row.ra * u.deg, row.dec * u.deg), radius=1.5 * u.arcsec, catalog=hern), 60)
                for t in res:
                    h = t.to_pandas()
                    h.insert(0, "benchmark_id", row.benchmark_id)
                    h_rows.append(h)
            except Exception:
                log["hern_fail"] += 1
        if i % 50 == 0:
            print(f"[var] {i}/{len(tg)}", flush=True)
            if p_rows:
                pd.concat(p_rows, ignore_index=True).to_csv(out / "targets__ps1_mean.csv.gz", index=False)
    if p_rows:
        pd.concat(p_rows, ignore_index=True).to_csv(out / "targets__ps1_mean.csv.gz", index=False)
    if h_rows:
        pd.concat(h_rows, ignore_index=True).to_csv(out / "targets__hernitschek2016.csv.gz", index=False)
    log["ps1_rows"] = sum(len(x) for x in p_rows)
    log["hern_rows"] = sum(len(x) for x in h_rows)
    (out / "collect_log.json").write_text(json.dumps(log, indent=1, default=str))
    print(json.dumps(log, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

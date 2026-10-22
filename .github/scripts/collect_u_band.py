"""u-band (and SkyMapper v) photometry at the benchmark truth positions
(2.36.0 experiment): does a u band separate the stars and quasars the
classifier still confuses?

VizieR cone searches (1.5") at a target list (QSO-related test errors plus a
sample of correct test objects); SDSS u for every benchmark position through
SkyServer cross-id.  Surveys and their u depth:
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
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log = {"probe": {}, "targets": {}, "sdss_all": {}}

    def save():
        (out / "collect_log.json").write_text(json.dumps(log, indent=1, default=str))

    # CDS XMatch did not answer any request from the runners (2026-10-22,
    # run 2), so VizieR cone searches are used for a target list: the
    # QSO-related test errors and a sample of correct test objects
    # (targets.csv), enough to measure how often a u band is available.
    tg = pd.read_csv(out / "targets.csv")
    c0 = SkyCoord(tg.ra.iloc[0] * u.deg, tg.dec.iloc[0] * u.deg)
    chosen = {}
    for sname, ids in SURVEYS.items():
        for cid in ids:
            try:
                r = _bounded(lambda: Vizier(columns=["**"], row_limit=3).query_region(c0, radius=30 * u.arcmin, catalog=cid), PROBE_S)
                cols = list(r[0].colnames) if len(r) else []
                log["probe"][cid] = {"tables": [t.meta.get("name") for t in r], "columns": cols}
                print(f"[u] probe {sname} {cid}: {log['probe'][cid]}", flush=True)
                if len(r):
                    chosen[sname] = r[0].meta.get("name", cid)
                    break
            except Exception as exc:
                log["probe"][cid] = f"{type(exc).__name__}: {str(exc)[:160]}"
                print(f"[u] probe {sname} {cid}: {log['probe'][cid]}", flush=True)
    save()
    parts = {k: [] for k in chosen}
    v = Vizier(columns=["**", "_r"], row_limit=5)
    for i, row in tg.iterrows():
        c = SkyCoord(row.ra * u.deg, row.dec * u.deg)
        try:
            res = _bounded(lambda: v.query_region(c, radius=1.5 * u.arcsec, catalog=list(chosen.values())), 60)
        except Exception as exc:
            log["targets"][str(row.benchmark_id)] = f"{type(exc).__name__}"
            continue
        for t in res:
            name = t.meta.get("name")
            for k, cid in chosen.items():
                if name == cid:
                    d = t.to_pandas()
                    d.insert(0, "benchmark_id", row.benchmark_id)
                    parts[k].append(d)
        if i % 50 == 0:
            print(f"[u] targets {i}/{len(tg)}", flush=True)
    for k, ps in parts.items():
        if ps:
            pd.concat(ps, ignore_index=True).to_csv(out / f"targets__{k}.csv.gz", index=False)
        log["targets"][k] = sum(len(x) for x in ps)
    save()
    print(f"[u] target rows: { {k: log['targets'][k] for k in chosen} }", flush=True)
    # SDSS u for every benchmark position through SkyServer cross-id (batches of 300).
    try:
        from astroquery.sdss import SDSS

        fields = ["ra", "dec", "objID", "type", "clean"] + [f"psfMag_{b}" for b in "ugriz"] + [f"psfMagErr_{b}" for b in "ugriz"]
        for tname, tpath in TRUTH.items():
            t = pd.read_csv(tpath, usecols=["benchmark_id", "ra", "dec"]).dropna().reset_index(drop=True)
            got = []
            for s0 in range(0, len(t), 300):
                ch = t.iloc[s0 : s0 + 300]
                coords = SkyCoord(ch.ra.to_numpy() * u.deg, ch.dec.to_numpy() * u.deg)
                try:
                    r = _bounded(lambda: SDSS.query_crossid(coords, radius=1.5 * u.arcsec, photoobj_fields=fields, data_release=18), 180)
                except Exception as exc:
                    log["sdss_all"][f"{tname}:{s0}"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                    print(f"[u] sdss {tname} {s0}: {log['sdss_all'][f'{tname}:{s0}']}", flush=True)
                    continue
                if r is not None and len(r):
                    d = r.to_pandas()
                    # obj_id is the row index of the uploaded list ("obj_<i>" or i)
                    idx = d["obj_id"].astype(str).str.replace("obj_", "", regex=False).astype(int)
                    d.insert(0, "benchmark_id", ch.benchmark_id.to_numpy()[idx.clip(0, len(ch) - 1)])
                    got.append(d)
            if got:
                pd.concat(got, ignore_index=True).to_csv(out / f"{tname}__sdss_crossid.csv.gz", index=False)
            log["sdss_all"][tname] = sum(len(x) for x in got)
            print(f"[u] sdss crossid {tname}: {log['sdss_all'][tname]} rows", flush=True)
            save()
    except Exception as exc:
        log["sdss_all"]["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    save()


if __name__ == "__main__":
    main(sys.argv[1])

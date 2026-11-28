#!/usr/bin/env python3
"""The full pipeline on the regions whose position errors change, once per V2_POSERR_UNITS mode (2.63.0).

    python run_pe.py --regions results_2026-11-27h/regions_changed.csv --out DIR --roots raw=ROOT ll_run=ROOT ll_conf=ROOT B1=ROOT \\
        --modes legacy,fixed [--jobs 4]

``regions_changed.csv`` is the list ``check_units_from_rows.py`` writes: the regions that hold at least one row whose position error differs between the
modes (every other region is identical by construction: the pipeline is deterministic, PYTHONHASHSEED=0, and the same inputs give the same outputs, which the
row-by-row check proves for the one input that differs).  Per region and mode it keeps a slim ``classified_objects.csv`` (the label, axis and radio columns this
study compares) and a slim ``source_association.csv`` (the membership: ``detection_id`` is ``<file stem>:<row>`` and so the same in both modes).

Region layouts: ``raw`` = deep COSMOS ``ROOT/<field>/raw/<tag>`` (centre and radius in ``--cosmos-fields``), ``ll_run`` / ``ll_conf`` = the low-latitude regions
``ROOT/<name>/raw`` (centre in the field lists), ``B1`` = the real-use fields ``ROOT/<name>/raw/<tag>`` (centre and radius in the tag).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
LOWLAT = V2 / "benchmark" / "lowlat_qso"
KEEP_OBJECTS = ["object_id", "ra", "dec", "catalogs", "n_catalogs", "parent_object_id", "classification_status", "primary_class", "secondary_class", "detailed_class",
                "physical_class", "variability_class", "compact_class", "extragalactic_class", "extragalactic_subtype", "phenomenon_class", "subclass", "subclass_code",
                "high_confidence", "std_mag__ls_r", "std_radio_first_mjy", "std_radio_nvss_mjy", "std_radio_lotss_144mhz_mjy", "std_radio_vlass_3ghz_mjy",
                "std_radio_1p4ghz_mjy"]  # fmt: skip
KEEP_ASSOC = ["detection_id", "catalog", "ra", "dec", "poserr_arcsec", "object_id", "association_status", "association_method", "match_separation_arcsec",
              "association_confidence", "object_ra", "object_dec", "object_anchor_catalog", "final_anchor_separation_arcsec"]  # fmt: skip


def parse_tag(name: str) -> tuple[float, float, float]:
    """``ra188p4155_dec9p1751_r2arcmin`` / ``decm2p1`` -> (188.4155, 9.1751, 2.0)."""
    m = re.search(r"ra(m?)([0-9p]+)_dec(m?)([0-9p]+)_r([0-9p]+)arcmin", name)
    if not m:
        raise ValueError(name)
    f = lambda neg, s: (-1 if neg else 1) * float(s.replace("p", "."))  # noqa: E731
    return f(m.group(1), m.group(2)), f(m.group(3), m.group(4)), float(m.group(5).replace("p", "."))


def region_table(regions: pd.DataFrame, roots: dict[str, Path], cosmos_fields: Path) -> list[dict]:
    cos = pd.read_csv(cosmos_fields).set_index("name")
    cal = pd.read_csv(LOWLAT / "fields_lowlat.csv").set_index("name")
    conf = pd.read_csv(LOWLAT / "fields_lowlat_confirm.csv").set_index("name")
    out = []
    for r in regions.itertuples():
        root = roots[r.set]
        if r.set == "raw":
            raw = sorted((root / r.region / "raw").glob("ra*"))[0]
            out.append(dict(set=r.set, region=r.region, raw=raw, ra=float(cos.loc[r.region, "ra"]), dec=float(cos.loc[r.region, "dec"]), radius=float(cos.loc[r.region, "r"])))
        elif r.set in ("ll_run", "ll_conf"):
            t = cal if r.set == "ll_run" else conf
            out.append(dict(set=r.set, region=r.region, raw=root / r.region / "raw", ra=float(t.loc[r.region, "ra"]), dec=float(t.loc[r.region, "dec"]), radius=3.0))
        else:
            raw = sorted((root / r.region / "raw").glob("ra*"))[0]
            ra, dec, rad = parse_tag(raw.name)
            out.append(dict(set=r.set, region=r.region, raw=raw, ra=ra, dec=dec, radius=rad))
    return out


def run_one(job: dict, mode: str, out_root: Path, work_root: Path) -> str:
    out = out_root / mode / job["set"] / job["region"]
    if (out / "classified_objects.csv").exists():
        return "skip"
    work = work_root / mode / job["set"] / job["region"]
    shutil.rmtree(work, ignore_errors=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("V2_") or k in ("V2_CACHE_DIR",)}
    env.update({"PYTHONHASHSEED": "0", "V2_CACHE": "0", "V2_POSERR_UNITS": mode})
    cmd = [sys.executable, str(V2 / "pipeline.py"), "--raw-dir", str(job["raw"]), "--ra", str(job["ra"]), "--dec", str(job["dec"]), "--radius", str(job["radius"]), "--work", str(work)]
    subprocess.run(cmd, env=env, check=True, timeout=3600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out.mkdir(parents=True, exist_ok=True)
    pd.read_csv(work / "classified_objects.csv", usecols=lambda c: c in set(KEEP_OBJECTS), low_memory=False).to_csv(out / "classified_objects.csv", index=False)
    pd.read_csv(work / "source_association.csv", usecols=lambda c: c in set(KEEP_ASSOC), low_memory=False).to_csv(out / "source_association.csv", index=False)
    shutil.rmtree(work, ignore_errors=True)
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--roots", nargs="+", required=True, help="SET=ROOT for raw, ll_run, ll_conf, B1")
    ap.add_argument("--cosmos-fields", type=Path, required=True)
    ap.add_argument("--modes", default="legacy,fixed")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--work", type=Path, default=Path("/tmp/pe_work"))
    a = ap.parse_args()
    roots = {kv.split("=", 1)[0]: Path(kv.split("=", 1)[1]) for kv in a.roots}
    jobs = region_table(pd.read_csv(a.regions), roots, a.cosmos_fields)
    todo = [(j, m) for m in a.modes.split(",") for j in jobs]
    print(f"{len(jobs)} regions x {len(a.modes.split(','))} modes", flush=True)
    done = 0
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        for res in ex.map(lambda t: run_one(t[0], t[1], a.out, a.work), todo):
            done += 1
            if done % 20 == 0:
                print(f"{done}/{len(todo)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

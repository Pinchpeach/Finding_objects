#!/usr/bin/env python3
"""Stage 1 (source association) on many stored raw folders, with a set of environment switches (2.61.7).

    python run_stage1.py --sets NAME=KIND:ROOT[:FIELDS.csv] ... --out DIR [--env KEY=VALUE ...] [--jobs 4]

Stage 1 starts without the caller's ``V2_*`` variables (only ``V2_CACHE`` / ``V2_CACHE_DIR`` pass), so that a switch left in the shell cannot
change a run: every switch, ``V2_ASSOC_DIAG=1`` too, is given with ``--env``.

``KIND``: ``regions`` (``ROOT/<region>/raw`` for the regions of FIELDS.csv: the low-latitude calibration / confirmation
regions, with or without the collected spectra) or ``cosmos`` (``ROOT/<field>/raw/<tag>``, the deep COSMOS fields;
FIELDS.csv lists the fields).  Writes ``DIR/<set>/<region>.csv.gz``, the ``source_association.csv`` of the stage, and
``DIR/timing.csv`` (seconds per region).  Nothing else of the pipeline runs: Stage 1 is what the work order is about.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
STAGE1 = V2 / "Preprocess" / "01_source_association.py"


def raw_folders(kind: str, root: Path, fields: Path | None) -> list[tuple[str, Path]]:
    if kind == "regions":
        f = pd.read_csv(fields)
        return [(r.name, root / r.name / "raw") for r in f.itertuples()]
    if kind == "cosmos":
        f = pd.read_csv(fields)
        out = []
        for r in f.itertuples():
            d = sorted((root / r.name / "raw").glob("ra*"))
            if d:
                out.append((r.name, d[0]))
        return out
    raise ValueError(kind)


def run_one(raw: Path, out: Path, env: dict) -> float:
    if out.exists():
        return 0.0
    e = {k: v for k, v in os.environ.items() if not k.startswith("V2_") or k in ("V2_CACHE", "V2_CACHE_DIR")}
    e.update({"PYTHONHASHSEED": "0", **env})
    tmp = out.with_suffix("")  # .csv
    tmp.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    subprocess.run([sys.executable, str(STAGE1), "--raw-dir", str(raw), "--out", str(tmp)], env=e, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # fmt: skip
    dt = time.time() - t0
    pd.read_csv(tmp, low_memory=False).to_csv(out, index=False)
    tmp.unlink()
    return dt


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--env", nargs="*", default=[])
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    t0 = RI.start()
    env = dict(kv.split("=", 1) for kv in a.env)
    jobs, meta = [], []
    for spec in a.sets:
        name, rest = spec.split("=", 1)
        parts = rest.split(":")
        kind, root = parts[0], Path(parts[1])
        fields = Path(parts[2]) if len(parts) > 2 else None
        for region, raw in raw_folders(kind, root, fields):
            jobs.append((raw, a.out / name / f"{region}.csv.gz"))
            meta.append((name, region))
    with ThreadPoolExecutor(a.jobs) as ex:
        times = list(ex.map(lambda j: run_one(j[0], j[1], env), jobs))
    t = pd.DataFrame([dict(set=n, region=r, seconds=round(s, 2)) for (n, r), s in zip(meta, times)])
    t.to_csv(a.out / "timing.csv", index=False)
    print(f"{len(jobs)} regions, {t.seconds.sum():.0f} s of stage 1")
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

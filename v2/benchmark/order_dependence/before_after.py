#!/usr/bin/env python3
"""Two sets of full pipeline runs of the same fields compared object by object (2.61.0).

    python before_after.py --fields-root DIR --a RUNS_A --b RUNS_B [--seed-b N] --out CSV

``--fields-root`` holds ``<field>/raw/<tag>/*.csv`` (the raw data of the runs; with ``--seed-b`` the rows of the raw
files of B were permuted with ``shuffle_check.py root --seeds N``, and the permutation is replayed here to give every
detection one key, ``(input file, row of the file as collected)``).  RUNS_A and RUNS_B hold ``<field>/{source_association.csv,
classified_objects.csv,objects_summary.csv,pipeline_summary.csv}``.

Per field and summed: objects (groups) in each run, objects that exist in only one run (a different set of members),
detections whose association status differs, labels of the objects that exist in both (``primary_class``,
``secondary_class``, ``high_confidence``), the number of rows of ``objects_summary.csv``, the high-confidence objects and
the seconds of Stage 1.
"""

from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shuffle_check as SC  # noqa: E402


def perms_for(raw: Path, seed: int) -> dict[str, np.ndarray]:
    """The permutations ``shuffle_raw`` applied to the csv files of ``raw`` with ``seed`` (same generator, same order)."""
    out = {}
    for p in sorted(raw.iterdir()):
        if p.suffix != ".csv" or p.name.startswith(SC.SKIP_PREFIX):
            continue
        n = len(pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False))
        out[p.name] = np.random.default_rng([seed, zlib.crc32(p.name.encode())]).permutation(n)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fields-root", type=Path, required=True)
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--seed-b", type=int, default=None)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for fdir in sorted(p for p in a.fields_root.glob("deep_cosmos_*") if (p / "field.json").exists()):
        name = fdir.name
        raw = next((fdir / "raw").iterdir())
        pa = pd.read_csv(a.a / name / "source_association.csv", low_memory=False)
        pb = pd.read_csv(a.b / name / "source_association.csv", low_memory=False)
        ma = SC.members(pa, {})
        mb = SC.members(pb, perms_for(raw, a.seed_b) if a.seed_b is not None else {})
        ca = pd.read_csv(a.a / name / "classified_objects.csv", low_memory=False)
        cb = pd.read_csv(a.b / name / "classified_objects.csv", low_memory=False)
        r = SC.compare_groups(ma, mb)
        r.update(SC.label_diff(ca, cb, ma, mb))
        sa = pd.read_csv(a.a / name / "objects_summary.csv", usecols=["object_id"])
        sb = pd.read_csv(a.b / name / "objects_summary.csv", usecols=["object_id"])
        r.update(
            field=name,
            summary_rows_a=len(sa),
            summary_rows_b=len(sb),
            high_conf_a=int(ca.high_confidence.astype(str).str.lower().eq("true").sum()),
            high_conf_b=int(cb.high_confidence.astype(str).str.lower().eq("true").sum()),
            stage1_s_a=float(pd.read_csv(a.a / name / "pipeline_summary.csv").set_index("stage").seconds.get("1_associate", np.nan)),
            stage1_s_b=float(pd.read_csv(a.b / name / "pipeline_summary.csv").set_index("stage").seconds.get("1_associate", np.nan)),
        )  # fmt: skip
        r.pop("by_catalog", None)
        rows.append(r)
        print(name, r, flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(a.out, index=False)
    s = d.drop(columns=["field"]).sum(numeric_only=True)
    print("SUM", s.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

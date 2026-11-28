#!/usr/bin/env python3
"""What ``same`` does when a detection has a third (or later) candidate that is another object (2.62.2).

    python third_candidate.py --root DIR --fields FIELDS.csv --out OUT [--jobs 4]

``V2_ASSOC_AMBIG=same`` looks at the two best candidates only: when their anchors are within ``SAME_OBJECT_ARCSEC`` (0.3'') it calls them fragments of one
object and takes the better, whatever the other candidates are.  The ambiguity itself is also decided on the two best scores (second >= 0.67 x best), so a
candidate list [A1, A2, C] with A1 and A2 fragments of one object and a competitor C is resolved to A1 although C may score nearly as well as A1.  This tool runs
Stage 1 with ``same`` + ``nearest`` on the stored raw folders, wraps ``_resolve_ambiguity`` and records, for every detection that ``same`` resolves, the later
candidates: how many there are, how far their anchors are from the best candidate's, and the ratio of their score to the best (``competitor`` = another object,
anchor farther than 0.3'', score ratio >= 0.67, i.e. a candidate that by itself would have made the row ambiguous).  Nothing in the pipeline changes.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _load_stage1():
    os.environ["V2_ASSOC_AMBIG"] = "same,nearest"
    sys.path.insert(0, str(V2 / "Preprocess"))
    spec = importlib.util.spec_from_file_location("s1_third", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s1_third"] = mod
    spec.loader.exec_module(mod)
    return mod


def scan_one(args) -> list[dict]:
    field, raw, tmp = args
    s1 = _load_stage1()
    rows: list[dict] = []
    original = s1._resolve_ambiguity

    def wrapped(candidates, groups):
        out = original(candidates, groups)
        if out[2] == "same_object":
            a0 = groups[candidates[0][2]]["anchor"]
            best = candidates[0][0]
            later = []
            for c in candidates[2:]:
                sep = s1.assess_pair(a0, groups[c[2]]["anchor"], None)["separation_arcsec"] or 0.0
                later.append((sep, c[0] / best if best else 0.0))
            comp = [x for x in later if x[0] >= s1.SAME_OBJECT_ARCSEC and x[1] >= s1.AMBIG_SCORE_RATIO]
            rows.append(dict(field=field, n_candidates=len(candidates), n_later=len(later), n_later_other_object=sum(1 for x in later if x[0] >= s1.SAME_OBJECT_ARCSEC),
                             competitor=bool(comp), best_competitor_ratio=max((x[1] for x in comp), default=0.0),
                             nearest_competitor_sep=min((x[0] for x in comp), default=float("nan"))))  # fmt: skip
        return out

    s1._resolve_ambiguity = wrapped
    s1.run(Path(raw), Path(tmp) / f"{field}.csv")
    return rows


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True, help="ROOT/<field>/raw/<tag> (deep COSMOS layout)")
    ap.add_argument("--fields", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    tmp = a.out / "_stage1"
    tmp.mkdir(exist_ok=True)
    jobs = []
    for name in pd.read_csv(a.fields).name:
        d = sorted((a.root / name / "raw").glob("ra*"))
        if d:
            jobs.append((name, str(d[0]), str(tmp)))
    with ProcessPoolExecutor(a.jobs) as ex:
        rows = [r for part in ex.map(scan_one, jobs) for r in part]
    d = pd.DataFrame(rows)
    d.to_csv(a.out / "same_resolved_rows.csv", index=False)
    summ = pd.DataFrame([dict(rows_resolved_by_same=len(d), with_3plus_candidates=int((d.n_candidates >= 3).sum()), with_later_other_object=int((d.n_later_other_object > 0).sum()),
                              with_competitor=int(d.competitor.sum()), competitor_share_of_3plus=round(float(d.competitor.sum() / max(1, (d.n_candidates >= 3).sum())), 4),
                              median_competitor_ratio=round(float(d.loc[d.competitor, "best_competitor_ratio"].median()), 3) if d.competitor.any() else float("nan"))])  # fmt: skip
    summ.to_csv(a.out / "summary.csv", index=False)
    print(summ.T.to_string(header=False))
    RI.write_args(a, t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

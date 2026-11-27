#!/usr/bin/env python3
"""How much the bot commits of the scientific cross validation moved the truth sample and the calibration (2.61.9).

    python history_table.py --out DIR [--since 2026-10-25]

Reads every commit that touched ``v2/Classifier/calibration/models.json`` straight from git (no network) and writes

  models_history.csv      one row per commit: the Platt coefficient, intercept, n, positives and negatives of every axis / class, the rule
                          precisions, and whether the class is usable for the output (``per_axis._usable``)
  exact_match_range.csv   per class: the lowest and highest exact-match and classified rate over the commits, and in how many commits a collector raised
  sample_states.csv       the distinct sets of truth ids a class had over the commits (SHA-256 of the sorted ids) and how many commits each set was in
  sample_history.csv      one row per commit and truth class: rows of ``independent_truth_predictions.csv``, how many truth ids it shares with the previous
                          commit (``kept``), the share, the exact-match rate and the classified rate

Only the Platt coefficients of the usable classes reach the output (``calibration/per_axis.annotate`` -> the ``*_reliability`` columns); see
WORK_REPORT_2026-11-27g.md.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

MODELS = "v2/Classifier/calibration/models.json"
PRED = "v2/Classifier/validation/independent_truth/independent_truth_predictions.csv"
MIN_SAMPLES, MIN_POS, MIN_NEG = 100, 20, 20  # calibration/per_axis.py


def git(*args) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def show(commit: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def usable(m: dict) -> bool:
    return bool(m.get("method") == "platt" and int(m.get("n", 0)) >= MIN_SAMPLES and int(m.get("positive", 0)) >= MIN_POS and int(m.get("negative", 0)) >= MIN_NEG)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--since", default="2026-10-25")
    a = ap.parse_args()
    log = git("log", "--reverse", "--format=%h|%ad|%an", "--date=short", f"--since={a.since}", "--", MODELS, PRED).strip().splitlines()
    commits = [tuple(x.split("|")) for x in log]
    mrows, srows, prev_ids = [], [], {}
    for h, d, who in commits:
        txt = show(h, MODELS)
        if txt:
            m = json.loads(txt)
            for axis, classes in m.get("axes", {}).items():
                for cls, e in classes.items():
                    mrows.append(dict(commit=h, date=d, author=who, kind="axis", axis=axis, cls=cls, method=e.get("method"), coef=e.get("coef"), intercept=e.get("intercept"),
                                      n=e.get("n"), positive=e.get("positive"), negative=e.get("negative"), usable=usable(e)))  # fmt: skip
            for axis, rules in m.get("rules", {}).items():
                for key, e in rules.items():
                    mrows.append(dict(commit=h, date=d, author=who, kind="rule", axis=axis, cls=key, method=e.get("method"), coef=None, intercept=None, n=e.get("n"),
                                      positive=e.get("correct"), negative=None, usable=e.get("precision")))  # fmt: skip
        ptxt = show(h, PRED)
        if ptxt:
            p = pd.read_csv(io.StringIO(ptxt), usecols=lambda c: c in ("truth_id", "axis", "truth_class", "match", "classified", "collectors"), dtype={"truth_id": str})
            # rows in which a collector raised (an archive that was down or refused): ``status`` of a collector log entry starts with "error"
            p["_err"] = [bool(c) and ('"status": "error' in c) for c in p["collectors"].fillna("")] if "collectors" in p else False
            for (axis, cls), g in p.groupby(["axis", "truth_class"]):
                ids = set(g.truth_id)
                before = prev_ids.get((axis, cls))
                kept = len(ids & before) if before is not None else None
                state = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:10]  # the set of truth ids of the class, order free
                srows.append(dict(commit=h, date=d, axis=axis, truth_class=cls, rows=len(g), set_sha256_10=state, kept_from_previous=kept,
                                  kept_share=round(kept / len(before), 3) if before else None, exact=round(float(g.match.astype(bool).mean()), 3),
                                  classified=round(float(g.classified.astype(bool).mean()), 3), archive_error_rows=int(g["_err"].sum())))  # fmt: skip
                prev_ids[(axis, cls)] = ids
    a.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(mrows).to_csv(a.out / "models_history.csv", index=False)
    pd.DataFrame(srows).to_csv(a.out / "sample_history.csv", index=False)
    sh0 = pd.DataFrame(srows)
    states = (sh0.groupby(["truth_class", "set_sha256_10"]).agg(commits=("commit", "nunique"), first=("date", "min"), last=("date", "max"), rows=("rows", "first")).reset_index()
              .sort_values(["truth_class", "commits"], ascending=[True, False]))  # fmt: skip
    states.to_csv(a.out / "sample_states.csv", index=False)
    rng = sh0.groupby("truth_class").agg(exact_min=("exact", "min"), exact_max=("exact", "max"), classified_min=("classified", "min"), classified_max=("classified", "max"),
                                         commits_with_archive_error=("archive_error_rows", lambda x: int((x > 0).sum())), commits=("commit", "nunique")).round(3)  # fmt: skip
    rng.to_csv(a.out / "exact_match_range.csv")
    mh = pd.DataFrame(mrows)
    u = mh[(mh.kind == "axis") & (mh.method == "platt")]
    with pd.option_context("display.width", 220, "display.max_columns", 20, "display.max_rows", 200):
        print(u.pivot_table(index=["date", "commit"], columns="cls", values=["coef", "n"], aggfunc="first").round(3).to_string())
        sh = pd.DataFrame(srows)
        print(sh.dropna(subset=["kept_share"]).groupby("truth_class").kept_share.describe().round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

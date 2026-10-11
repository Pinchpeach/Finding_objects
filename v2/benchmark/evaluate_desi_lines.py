#!/usr/bin/env python3
"""DESI FastSpecFit vs SDSS emission-line classification on the same galaxies
(2.7.0; truth built by build_desi_lines_truth.py).

Both spectra go through the same rules (Classifier/subclass.py galaxy_lines:
WHAN, BPT, [N II]/H-alpha, Dn4000).  The SDSS result (Portsmouth / MPA-JHU)
is the reference; reported: coverage of each route, agreement where both
decide, the confusion matrix, and agreement by DESI rule.

    python v2/benchmark/evaluate_desi_lines.py [--out metrics.json]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import evaluate_subclass as ev  # noqa: E402

SDSS, DESI = "sdss_dr18_spectroscopy__", "desi_dr1_fastspecfit__"


def _row(r: dict, src: str, prefix: str) -> dict:
    out = {}
    for k, v in r.items():
        if k.startswith(src + "_line_") or k == src + "_d4000_n":
            if isinstance(v, float) and v != v:
                continue
            out[prefix + k[len(src) + 1:]] = v
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=BENCH / "desi_lines_truth" / "desi_lines_metrics.json")
    a = p.parse_args()
    sc = ev.load_subclass()
    d = pd.read_csv(BENCH / "desi_lines_truth" / "overlap.csv.gz", low_memory=False)
    recs = d.to_dict("records")
    s = [sc.galaxy_lines(_row(r, "sdss", SDSS)) for r in recs]
    t = [sc.galaxy_lines(_row(r, "desi", DESI)) for r in recs]
    d["sdss_class"] = [x[0] if x else None for x in s]
    d["sdss_rule"] = [x[1] if x else None for x in s]
    d["desi_class"] = [x[0] if x else None for x in t]
    d["desi_rule"] = [x[1] if x else None for x in t]
    both = d.sdss_class.notna() & d.desi_class.notna()
    agree = d.sdss_class[both] == d.desi_class[both]
    # Adjacent classes on the BPT sequence (SF - composite - AGN) differ by line
    # ratio noise near a boundary; reported separately from the exact match.
    order = {"STAR_FORMING": 0, "COMPOSITE": 1, "AGN": 2}
    adj = [(a_ == b_) or (a_ in order and b_ in order and abs(order[a_] - order[b_]) == 1)
           for a_, b_ in zip(d.sdss_class[both], d.desi_class[both])]
    out = {
        "n": int(len(d)),
        "z_median": round(float(d.z.median()), 3),
        "sdss_decided": int(d.sdss_class.notna().sum()),
        "desi_decided": int(d.desi_class.notna().sum()),
        "both_decided": int(both.sum()),
        "desi_only": int((d.desi_class.notna() & d.sdss_class.isna()).sum()),
        "agreement": round(float(agree.mean()), 4) if both.any() else None,
        "agreement_within_adjacent": round(float(pd.Series(adj).mean()), 4) if both.any() else None,
        "confusion_sdss_rows_desi_cols": pd.crosstab(d.sdss_class[both], d.desi_class[both]).to_dict(orient="index"),
        "agreement_by_desi_rule": {k: {"n": int(len(g)), "agreement": round(float((g.sdss_class == g.desi_class).mean()), 4)}
                                   for k, g in d[both].groupby("desi_rule")},
        "class_fraction": {"sdss": d.sdss_class[both].value_counts(normalize=True).round(4).to_dict(),
                           "desi": d.desi_class[both].value_counts(normalize=True).round(4).to_dict()},
    }
    print(json.dumps(out, indent=1))
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Association counts of one run, for the A/B experiment.

assoc_stats.py ASSOC_CSV [SHIFTED_ASSOC_CSV] -> JSON on stdout
  n_groups, per low-resolution catalogue the rows matched to another
  object, rows down-weighted by the photometric prior, and (shifted run)
  the rows matched although their positions were moved by 2' (false
  associations, as NWAY's shifted-catalogue calibration).
"""
import json
import sys

import pandas as pd

CATS = ("AllWISE", "2MASS PSC")


def counts(f, tag):
    a = pd.read_csv(f, low_memory=False)
    out = {f"{tag}groups": int(a.object_id.nunique())}
    for c in CATS:
        r = a[a.catalog == c]
        key = c.split()[0].lower()
        out[f"{tag}{key}_rows"] = int(len(r))
        out[f"{tag}{key}_matched"] = int((r.association_status == "matched").sum())
        if "phot_weight" in r:
            out[f"{tag}{key}_downweighted"] = int((pd.to_numeric(r.phot_weight, errors="coerce") < 1).sum())
    return out


res = counts(sys.argv[1], "")
if len(sys.argv) > 2:
    res |= counts(sys.argv[2], "shifted_")
print(json.dumps(res))
if len(sys.argv) > 3:
    # Per-row match diagnostics of the low-resolution catalogues, real and
    # shifted, for calibrating an acceptance threshold at a target false-match
    # rate (NWAY p_any calibration; benchmark/calibrate_assoc_threshold.py).
    keep = ["catalog", "association_status", "association_method", "association_confidence", "normalized_separation",
            "match_separation_arcsec", "source_density_arcsec2", "candidate_count", "object_anchor_catalog", "phot_weight"]
    parts = []
    for run, f in (("real", sys.argv[1]), ("shifted", sys.argv[2])):
        a = pd.read_csv(f, low_memory=False)
        a = a[a.catalog.isin(CATS)]
        parts.append(a[[c for c in keep if c in a]].assign(run=run))
    pd.concat(parts).to_csv(sys.argv[3], index=False)

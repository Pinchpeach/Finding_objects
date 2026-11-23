#!/usr/bin/env python3
"""Recall of X-ray-selected AGN in the deep COSMOS fields (2.56.0, measurement only).

Truth: Chandra COSMOS Legacy optical/IR identifications (Marchesi et al.
2016, ApJ 817, 34; VizieR J/ApJ/817/34/catalog; 4,016 X-ray sources, 97 %
with a counterpart).  Classes as in that paper (sect. 6): the spectroscopic
type when there is one (spec_type 1 = broad-line AGN, 2 = non-BLAGN, 0 =
star), else the SED type (phot_type 1 = unobscured AGN, 2 = obscured AGN,
3 = galaxy, 5 = star).  "Type 1" (BLAGN / unobscured) is the QSO truth: X-ray
selection does not depend on optical colour, so this is the faint QSO
population without the colour pre-selection of SDSS / DESI targets.  Type 2
sources are host-dominated and expected as GALAXY; their labels are counted only.

The nine deep_cosmos fields of experiment-ab-fields.yml (6' radius) are
classified blind (no spectroscopic / literature collectors).  The 2.52.0
calibration/test split is kept (prior_layer_study.split: odd fields =
calibration, even = test) and reported separately; nothing is tuned here.

    python v2/benchmark/measure_cosmos_xray_agn.py --runs DIR   # DIR/deep_cosmos_N/blind/classified_objects.csv
"""

from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
TRUTH = B / "cosmos_xray_agn" / "chandra_cosmos_legacy_ids.csv.gz"
FIELDS = {
    "deep_cosmos_1": (149.85, 1.95), "deep_cosmos_2": (149.85, 2.21), "deep_cosmos_3": (149.85, 2.47),
    "deep_cosmos_4": (150.12, 1.95), "deep_cosmos_5": (150.12, 2.21), "deep_cosmos_6": (150.12, 2.47),
    "deep_cosmos_7": (150.39, 1.95), "deep_cosmos_8": (150.39, 2.21), "deep_cosmos_9": (150.39, 2.47),
}
RADIUS_ARCMIN, EDGE_ARCMIN, MATCH_ARCSEC = 6.0, 0.25, 1.0
R_BINS = [(-np.inf, 21.0), (21.0, 22.0), (22.0, 23.0), (23.0, 24.0), (24.0, np.inf)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def truth_type(t: pd.DataFrame) -> pd.Series:
    sp, ph = t.Clsp, t.Clph
    out = pd.Series("UNKNOWN", index=t.index)
    out[ph.isin([2, 3])] = "TYPE2"
    out[ph == 1] = "TYPE1"
    out[ph == 5] = "STAR"
    out[sp == 2] = "TYPE2"
    out[sp == 1] = "TYPE1"
    out[sp == 0] = "STAR"
    return out


def sep_arcsec(ra1, de1, ra2, de2):
    d = np.radians
    x = np.sin(d(de2 - de1) / 2) ** 2 + np.cos(d(de1)) * np.cos(d(de2)) * np.sin(d(ra2 - ra1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(x))) * 3600


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=B / "cosmos_xray_agn")
    a = ap.parse_args()
    t = pd.read_csv(TRUTH)
    t["ra"] = t.RAOdeg.fillna(t.RAJ2000)  # optical counterpart position, X-ray if none
    t["dec"] = t.DEOdeg.fillna(t.DEJ2000)
    t["ttype"] = truth_type(t)
    t["spec"] = t.Clsp.isin([0, 1, 2])
    rows = []
    for f, (ra0, de0) in FIELDS.items():
        p = a.runs / f / "blind" / "classified_objects.csv"
        if not p.exists():
            print("missing", p)
            continue
        o = pd.read_csv(p, low_memory=False, usecols=lambda c: c in ("object_id", "ra", "dec", "primary_class", "classification_status", "std_mag__ls_r", "p_qso"))
        tf = t[sep_arcsec(ra0, de0, t.ra, t.dec) <= (RADIUS_ARCMIN - EDGE_ARCMIN) * 60].copy()
        for _, r in tf.iterrows():
            s = sep_arcsec(r.ra, r.dec, o.ra.values, o.dec.values)
            j = int(np.argmin(s)) if len(s) else -1
            hit = j >= 0 and s[j] <= MATCH_ARCSEC
            rows.append({"field": f, "split": "cal" if int(f.rsplit("_", 1)[1]) % 2 else "test", "ID": r.ID, "ttype": r.ttype,
                         "spec": r.spec, "zbest": r.zbest, "imag": r.imag, "matched": hit,
                         "ours": o.primary_class.iloc[j] if hit else None, "p_qso": o.p_qso.iloc[j] if hit else np.nan,
                         "ls_r": o.std_mag__ls_r.iloc[j] if hit else np.nan, "sep": s[j] if hit else np.nan})
    d = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out / "matched_truth.csv.gz", index=False)
    res = {"fields": sorted(d.field.unique()), "truth_in_fields": d.ttype.value_counts().to_dict(), "tables": {}}
    lines = []
    for split in ("cal", "test", "all"):
        for subset, sel in (("type1_all", d.ttype == "TYPE1"), ("type1_spec", (d.ttype == "TYPE1") & d.spec), ("type2_all", d.ttype == "TYPE2")):
            x = d[sel & ((d.split == split) if split != "all" else True)]
            tab = []
            for lo, hi in R_BINS + [("no_r", None)]:
                if lo == "no_r":
                    y, lab = x[x.matched & x.ls_r.isna()], "matched, no LS r"
                else:
                    y, lab = x[x.matched & (x.ls_r >= lo) & (x.ls_r < hi)], f"r {lo}-{hi}"
                n = len(y)
                c = y.ours.value_counts().to_dict()
                k = int(c.get("QSO", 0))
                tab.append({"bin": lab, "n": n, "QSO": k, "GALAXY": int(c.get("GALAXY", 0)), "STAR": int(c.get("STAR", 0)),
                            "UNKNOWN": int(c.get("UNKNOWN", 0)), "qso_recall": round(k / n, 4) if n else None, "wilson95": wilson(k, n)})
            n_all, n_m = len(x), int(x.matched.sum())
            k_all = int((x.ours == "QSO").sum())
            res["tables"][f"{split}/{subset}"] = {"truth": n_all, "matched": n_m, "qso": k_all,
                                                  "qso_recall_of_matched": round(k_all / n_m, 4) if n_m else None,
                                                  "wilson95": wilson(k_all, n_m), "by_r": tab}
            lines.append(f"{split:4s} {subset:11s} truth {n_all:4d} matched {n_m:4d} QSO {k_all:4d} recall {k_all / n_m if n_m else float('nan'):.3f} {wilson(k_all, n_m)}")
    (a.out / "metrics.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print("\n".join(lines))
    for key in ("cal/type1_all", "test/type1_all", "all/type1_spec", "all/type2_all"):
        print(key)
        print(pd.DataFrame(res["tables"][key]["by_r"]).to_string(index=False))


if __name__ == "__main__":
    main()

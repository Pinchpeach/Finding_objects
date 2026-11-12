#!/usr/bin/env python3
"""Paired A/B comparison of pipeline variants on the same collected fields.

Layout (written by .github/workflows/experiment-ab-fields.yml):
  ROOT/<variant>/<field>/{field.json, truth/, objects_blind.csv.gz}
  ROOT/<variant>/<field>/assoc_stats.json   (association counts, shifted test)

For every variant the truth objects are matched as in
score_independent_fields.field_matches (blind run, benchmark objects
excluded).  Variants are compared on the truth objects matched in all of
them: accuracy, fixed / broken objects, fragments next to truth objects.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

import field_stats as FS
import score_independent_fields as S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--base", default="base")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--aggregate-only", action="store_true", help="no per-object files (locked set C protocol)")
    ap.add_argument("--nboot", type=int, default=1000)
    a = ap.parse_args()
    variants = sorted(p.name for p in a.root.iterdir() if p.is_dir())
    bench = S.benchmark_positions()
    per = {}
    stats = []
    cover = []
    for v in variants:
        rows = []
        for fdir in sorted(p for p in (a.root / v).iterdir() if (p / "field.json").exists() and (p / "objects_blind.csv.gz").exists()):
            m, info = S.field_matches(fdir, "blind", bench)
            cover.append({"variant": v, "field": fdir.name, "n_truth": info["n_truth"], "unmatched": info["unmatched"], "in_bench": info["in_bench"]})
            ev = fdir / "objects_blind_evidence.csv.gz"
            if not m.empty and ev.exists() and "object_id" in m:
                # fused class probabilities of the matched objects (risk-coverage / abstention calibration)
                # fused probabilities, and the balanced-training ones before the
                # position / magnitude priors (2.52.0: prior-layer calibration)
                p = pd.read_csv(ev, usecols=lambda c: c == "object_id" or (c.startswith("p_") and c[2:].split("_")[0] in ("star", "galaxy", "qso")))
                m = m.merge(p.drop_duplicates("object_id"), on="object_id", how="left")
            if not m.empty:
                m.insert(0, "field", fdir.name)
                rows.append(m)
            st = fdir / "assoc_stats.json"
            if st.exists():
                stats.append({"variant": v, "field": fdir.name, **json.loads(st.read_text())})
        per[v] = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    key = ["field", "t_ra", "t_dec"]
    common = None
    for v, m in per.items():
        k = m[key].round(6).apply(tuple, axis=1)
        common = set(k) if common is None else common & set(k)
    out = []
    base = per[a.base].assign(k=per[a.base][key].round(6).apply(tuple, axis=1)).set_index("k")
    for v, m in per.items():
        m = m.assign(k=m[key].round(6).apply(tuple, axis=1)).set_index("k")
        m = m[m.index.isin(common)]
        b = base.loc[m.index]
        ok, okb = m.ours == m.t_truth, b.ours == b.t_truth
        r = dict(variant=v, n=len(m), acc=round(100 * ok.mean(), 3), unknown=int((m.ours == "UNKNOWN").sum()),
                 fixed=int((ok & ~okb).sum()), broken=int((~ok & okb).sum()),
                 truth_with_fragments=int(m.t_n_fragments.gt(0).sum()))
        for c in S.C:
            t = m.t_truth == c
            r[f"recall_{c}"] = round(100 * ok[t].mean(), 2) if t.any() else None
        # field-bootstrap CI, balanced accuracy, precision, baselines and the
        # paired McNemar test against the base variant (2.51.0, review 3.4)
        r.update(FS.summary(m, a.nboot))
        if v != a.base:
            r["mcnemar_p"], r["only_variant_right"], r["only_base_right"] = FS.mcnemar(ok.to_numpy(), okb.to_numpy())
        cv = [c for c in cover if c["variant"] == v]
        if cv:
            nt = sum(c["n_truth"] - c["in_bench"] for c in cv)
            r["unmatched_truth_pct"] = round(100 * sum(c["unmatched"] for c in cv) / max(nt, 1), 2)
        out.append(r)
        if v != a.base and "allwise__W1mag" in m and "allwise__W1mag" in b:
            w, wb = pd.to_numeric(m.allwise__W1mag, errors="coerce"), pd.to_numeric(b.allwise__W1mag, errors="coerce")
            d = (w - wb).abs()
            r["w1_changed"] = int((d > 0.01).sum())
            r["w1_median_abs_diff"] = round(float(d[d > 0.01].median()), 3) if (d > 0.01).any() else 0.0
        if a.out and not a.aggregate_only:
            pcols = [c for c in m.columns if c.startswith("p_") and c[2:].split("_")[0] in ("star", "galaxy", "qso")]
            mags = [c for c in ("std_mag__ls_r", "std_mag__ps1_r", "std_mag__sdss_r", "gaia_dr3__phot_g_mean_mag", "classification_status",
                                "t_survey", "t_ra", "t_dec") if c in m]
            m[["field", "t_truth", "ours"] + pcols + mags].to_csv(a.out / f"truth_probs_{v}.csv.gz", index=False)
            # every wrong or UNKNOWN truth object of this variant, for error analysis
            keep = [c for c in ("field", "t_ra", "t_dec", "t_truth", "t_survey", "t_n_fragments", "ours", "catalogs", "unknown_reason",
                                "primary_confidence", "classification_basis", "gaia_dr3__phot_g_mean_mag", "std_mag__ls_r",
                                "std_mag__ps1_r", "std_mag__sdss_r", "desi_legacy_surveys_dr10__type", "subclass",
                                "p_star", "p_galaxy", "p_qso") if c in m]
            a.out.mkdir(parents=True, exist_ok=True)
            m[~ok][keep].to_csv(a.out / f"errors_{v}.csv.gz", index=False)
        if v != a.base and a.out and not a.aggregate_only:
            diff = m[ok != okb][["field", "t_ra", "t_dec", "t_truth", "t_survey", "ours"]].assign(base=b.ours[ok != okb])
            a.out.mkdir(parents=True, exist_ok=True)
            diff.to_csv(a.out / f"changed_{v}.csv", index=False)
    res = pd.DataFrame(out)
    print(res.to_string(index=False))
    if stats:
        st = pd.DataFrame(stats)
        agg = st.drop(columns="field").groupby("variant").sum(numeric_only=True)
        print(agg.to_string())
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        res.to_csv(a.out / "ab_summary.csv", index=False)
        if stats and not a.aggregate_only:
            st.to_csv(a.out / "assoc_stats.csv", index=False)


if __name__ == "__main__":
    main()

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

import score_independent_fields as S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--base", default="base")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    variants = sorted(p.name for p in a.root.iterdir() if p.is_dir())
    bench = S.benchmark_positions()
    per = {}
    stats = []
    for v in variants:
        rows = []
        for fdir in sorted(p for p in (a.root / v).iterdir() if (p / "field.json").exists() and (p / "objects_blind.csv.gz").exists()):
            m, _ = S.field_matches(fdir, "blind", bench)
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
        out.append(r)
        if v != a.base and "allwise__W1mag" in m and "allwise__W1mag" in b:
            w, wb = pd.to_numeric(m.allwise__W1mag, errors="coerce"), pd.to_numeric(b.allwise__W1mag, errors="coerce")
            d = (w - wb).abs()
            r["w1_changed"] = int((d > 0.01).sum())
            r["w1_median_abs_diff"] = round(float(d[d > 0.01].median()), 3) if (d > 0.01).any() else 0.0
        if v != a.base and a.out:
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
        if stats:
            st.to_csv(a.out / "assoc_stats.csv", index=False)


if __name__ == "__main__":
    main()

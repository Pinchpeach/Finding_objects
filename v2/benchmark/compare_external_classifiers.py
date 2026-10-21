#!/usr/bin/env python3
"""Head-to-head on the benchmark test split: our classifier against the labels
other systems give the same objects (2026-10-21 comparison, see
benchmark/COMPARISON_2026-10-21.md).

Other systems, applied to exactly the objects they cover:
* Gaia DR3 DSC-Combmod (Delchambre et al. 2023): argmax of star (+WD, binary),
  galaxy, quasar probabilities;
* LS photometry ML alone (our LS-GBM-001, a DESI-style tree model on
  Legacy Surveys grzW1W2 + morphology; cf. Chaussidon et al. 2023);
* LS Tractor morphology + WISE W1-W2 >= 0.8 (Vega; Stern et al. 2012);
* point/extended: LS Tractor PSF vs resolved, and PS1 iPSF - iKron > 0.05.

    python v2/benchmark/compare_external_classifiers.py --truth T --catalog-root R --manifest M
"""
import argparse, importlib.util, json, tempfile
from pathlib import Path
import numpy as np, pandas as pd

B = Path(__file__).resolve().parent


def stage_table(truth_p, root, manifest_p):
    spec = importlib.util.spec_from_file_location("ev", B / "evaluate_rule_baseline.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    truth, manifest = pd.read_csv(truth_p), pd.read_csv(manifest_p)
    ev.pre = ev.load_script("02_integrate_objects.py")
    raw = ev.wide(truth, ev.read_catalogs(root))
    s3, s4, s5 = (ev.load_script(n) for n in ("03_extract_features.py", "04_build_evidence.py", "05_likelihood_vectors.py"))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        raw.to_csv(td / "o.csv", index=False)
        s3.run(td / "o.csv", ev.PRE / "classification_rules.csv", td / "f.csv")
        s4.run(td / "f.csv", ev.PRE / "classification_rules.csv", td / "e.csv")
        s5.run(td / "e.csv", td / "l.csv")
        f = pd.read_csv(td / "f.csv", low_memory=False)
        l = pd.read_csv(td / "l.csv", low_memory=False)
    keep = [c for c in l.columns if c not in f.columns or c == "benchmark_id"]
    d = truth[["benchmark_id", "truth_class"]].merge(manifest[["benchmark_id", "split"]], on="benchmark_id")
    return d.merge(f, on="benchmark_id").merge(l[keep], on="benchmark_id")


ap = argparse.ArgumentParser()
ap.add_argument("--truth", type=Path, required=True)
ap.add_argument("--catalog-root", type=Path, required=True)
ap.add_argument("--manifest", type=Path, required=True)
a = ap.parse_args()
d = stage_table(a.truth, a.catalog_root, a.manifest)
d = d.loc[:, ~d.columns.duplicated()]
d = d[d.split.eq("test")].copy()
C = ["STAR", "GALAXY", "QSO"]
g = lambda c: pd.to_numeric(d.get(c, pd.Series(np.nan, index=d.index)), errors="coerce")
def ev_prob(rule):
    out = {c: np.full(len(d), np.nan) for c in C}
    for i, raw in enumerate(d.evidence_json):
        try: ev = json.loads(raw) if isinstance(raw, str) else []
        except Exception: ev = []
        for e in ev:
            if e.get("rule_id") == rule and e.get("class") in C:
                v = e.get("raw_score", e.get("score"))
                try: out[e["class"]][i] = float(v)
                except (TypeError, ValueError): pass
    p = pd.DataFrame(out, index=d.index)
    return p
labels = {}
# 1 Gaia DR3 DSC-Combmod (Delchambre+2023): argmax over star (incl. WD, binary), galaxy, quasar
ps = g("gaia_dr3__classprob_dsc_combmod_star").fillna(0) + g("gaia_dr3__classprob_dsc_combmod_whitedwarf").fillna(0) + g("gaia_dr3__classprob_dsc_combmod_binarystar").fillna(0)
dsc = pd.DataFrame({"STAR": ps, "GALAXY": g("gaia_dr3__classprob_dsc_combmod_galaxy"), "QSO": g("gaia_dr3__classprob_dsc_combmod_quasar")})
has = g("gaia_dr3__classprob_dsc_combmod_quasar").notna()
labels["Gaia DR3 DSC-Combmod"] = dsc.idxmax(axis=1).where(has)
# 2 single-survey ML: LS-GBM (DESI-style tree model on LS grzW1W2 + morphology, Chaussidon+2023-like)
gb = ev_prob("LS-GBM-001"); hg = gb.notna().any(axis=1)
labels["LS photometry ML only (LS-GBM)"] = gb.fillna(-1).idxmax(axis=1).where(hg)
# 3 morphology + WISE colour cut: Tractor PSF/extended + Stern+2012 W1-W2>=0.8 (Vega)
typ = d.get("desi_legacy_surveys_dr10__type", pd.Series("", index=d.index)).astype(str).str.upper().str.strip()
w12 = g("allwise__W1mag") - g("allwise__W2mag")
lab = pd.Series(np.where(typ.isin(["REX", "EXP", "DEV", "SER", "COMP"]), "GALAXY", np.where(w12 >= 0.8, "QSO", "STAR")), index=d.index)
labels["LS morphology + WISE W1-W2>=0.8 cut"] = lab.where(typ.isin(["PSF", "REX", "EXP", "DEV", "SER", "COMP"]) & (typ.ne("PSF") | w12.notna()))
ours = d.primary_class
y = d.truth_class
def score(pred, mask):
    m = mask & pred.notna()
    p, t = pred[m], y[m]
    cls = p.ne("UNKNOWN")
    rec = {c: round(100 * float((p[t == c] == c).mean()), 1) if (t == c).any() else None for c in C}
    return dict(n=int(m.sum()), cover=round(100 * m.sum() / mask.sum(), 1), acc_all=round(100 * float((p == t).mean()), 2),
                acc_cls=round(100 * float((p[cls] == t[cls]).mean()), 2) if cls.any() else None, recall=rec)
allm = pd.Series(True, index=d.index)
print(f"test objects: {len(d)}  class mix: {y.value_counts().to_dict()}")
print("ours (all):", score(ours, allm))
for name, lab in labels.items():
    m = lab.notna()
    print(f"\n{name}: covers {m.sum()} objects")
    print("   theirs:", score(lab, allm))
    print("   ours on same objects:", score(ours, m))
# star/galaxy (2-class) comparison: point vs extended
pt = y.isin(["STAR", "QSO"])
for name, pred in (("LS Tractor PSF vs extended", typ.map(lambda t: "POINT" if t == "PSF" else ("EXT" if t in ("REX","EXP","DEV","SER","COMP") else None))),
                   ("PS1 iPSF-iKron>0.05 (Farrow+2014-style)", (g("pan_starrs1_dr2_meanobject__iMeanPSFMag") - g("pan_starrs1_dr2_meanobject__iMeanKronMag")).map(lambda x: None if not np.isfinite(x) or abs(x) > 5 else ("EXT" if x > 0.05 else "POINT")))):
    m = pred.notna()
    t2 = np.where(pt, "POINT", "EXT")
    o2 = ours.map({"STAR": "POINT", "QSO": "POINT", "GALAXY": "EXT"})
    print(f"\n{name}: n={int(m.sum())} acc {100*float((pred[m]==t2[m]).mean()):.2f}% | ours collapsed to point/extended on same: {100*float((o2[m]==t2[m]).mean()):.2f}%")

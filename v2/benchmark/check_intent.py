"""Does the coarse classifier behave as designed?  (2.28.0)

Runs Stages 3-5 on a benchmark truth set (as evaluate_rule_baseline.py does)
and checks the design rules of Stage 5 rather than its accuracy:

1. decision rules: NO_EVIDENCE <=> no usable evidence; CLASSIFIED only at
   confidence >= min_confidence; LOW_CONFIDENCE only below it (or a small
   margin); UNKNOWN never carries a class.
2. evidence direction: adding one more piece of evidence for class c (a
   real item of that rule, copied from another object) must not lower the
   probability of c or of its class group (the sign constraint of 2.11.0,
   which the tree part of the hybrid fusion does not guarantee).
3. calibration: among classified objects, accuracy per confidence bin is
   close to the mean confidence (the abstention threshold assumes this).
4. footprint keys (X-ray, radio): kept out of the trees, and a detection
   raises QSO (absence is not evidence; 2.26.0 linear-only keys).

Usage: check_intent.py --truth T --catalog-root R --manifest M [--split test]
"""

import argparse
import json
import random
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import evaluate_rule_baseline as base

PRE = Path(__file__).resolve().parents[1] / "Preprocess"


def stages(truth, root):
    base.pre = base.load_script("02_integrate_objects.py")
    raw = base.wide(truth, base.read_catalogs(root))
    s3, s4, s5 = (base.load_script(f) for f in ("03_extract_features.py", "04_build_evidence.py", "05_likelihood_vectors.py"))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        raw.to_csv(td / "o.csv", index=False)
        s3.run(td / "o.csv", PRE / "classification_rules.csv", td / "f.csv")
        s4.run(td / "f.csv", PRE / "classification_rules.csv", td / "e.csv")
        s5.run(td / "e.csv", td / "l.csv")
        return pd.read_csv(td / "e.csv", low_memory=False), pd.read_csv(td / "l.csv", low_memory=False), s5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--catalog-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--per-key", type=int, default=200, help="objects per evidence key in check 2")
    a = ap.parse_args()
    truth = pd.read_csv(a.truth)
    ev, lk, s5 = stages(truth, a.catalog_root)
    man = pd.read_csv(a.manifest)[["benchmark_id", "split"]]
    lk = lk.merge(truth[["benchmark_id", "truth_class"]], on="benchmark_id").merge(man, on="benchmark_id")
    ev = ev.set_index("benchmark_id")
    model = s5.load_model()
    min_conf = float(model.get("min_confidence", s5.MIN_CONFIDENCE))
    C = s5.CLASSES
    out = {}

    # 1. decision rules
    items = {b: json.loads(ev.at[b, "evidence_json"]) if isinstance(ev.at[b, "evidence_json"], str) else [] for b in lk.benchmark_id}
    fused = dict(zip(lk.benchmark_id, s5.fuse_many([items[b] for b in lk.benchmark_id], model, s5.MODEL_PATH.parent)))
    bad = defaultdict(int)
    for r in lk.itertuples():
        _, used = fused[r.benchmark_id]
        st, cls, conf = r.classification_status, r.primary_class, r.primary_confidence
        if (used == 0) != (st == "NO_EVIDENCE") and st != "WITHIN_LARGE_GALAXY":
            bad["no_evidence_mismatch"] += 1
        if st == "CLASSIFIED" and not (conf >= min_conf or cls == "STAR"):  # decisive motion may lift STAR
            bad["classified_below_threshold"] += 1
        if st == "LOW_CONFIDENCE" and conf >= min_conf and r.primary_margin >= float(model.get("min_margin", 0.0)):
            bad["low_confidence_above_threshold"] += 1
        if (cls == "UNKNOWN") != (st != "CLASSIFIED"):
            bad["label_status_mismatch"] += 1
    out["1_decision_rules"] = {"rows": len(lk), "violations": dict(bad)}

    # 2. evidence direction (counterfactual: one more real item for class c)
    te = lk[lk.split.eq(a.split)] if a.split != "all" else lk
    templates = {}
    for b in lk.benchmark_id:
        for e in items[b]:
            if e.get("kind") == "linear_feature":
                continue
            c = {"WD": "STAR", "BINARY": "STAR"}.get(e.get("class"), e.get("class"))
            k = f"{e.get('rule_id')}:{c}"
            # The strongest real item of the key: probability-type rules
            # (LS-GBM, colour kNN, DSC) also emit low scores, which are
            # evidence against the class and rightly lower it.
            try:
                sc = float(e.get("raw_score", e.get("score")))
            except (TypeError, ValueError):
                continue
            if (c in C or c in s5.GROUPS) and sc >= 0.8 and sc > float(templates.get(k, {}).get("_s", 0)):
                templates[k] = {**e, "_s": sc}
    rng = random.Random(0)
    direction = {}
    for k, tmpl in sorted(templates.items()):
        c = k.rsplit(":", 1)[1]
        own = [C.index(x) for x in s5.GROUPS.get(c, (c,))]
        rows = [b for b in te.benchmark_id if not any(f"{e.get('rule_id')}:{e.get('class')}" == k for e in items[b])]
        rows = rng.sample(rows, min(a.per_key, len(rows)))
        if not rows:
            continue
        before = s5.fuse_many([items[b] for b in rows], model, s5.MODEL_PATH.parent)
        after = s5.fuse_many([items[b] + [tmpl] for b in rows], model, s5.MODEL_PATH.parent)
        d = np.array([sum(p1[C[i]] for i in own) - sum(p0[C[i]] for i in own) for (p0, _), (p1, _) in zip(before, after)])
        direction[k] = {
            "n": len(d),
            "lowered_>0.01": int((d < -0.01).sum()),
            "median_change": round(float(np.median(d)), 4),
            "largest_drop": round(float(d.min()), 4),
        }
    out["2_evidence_direction"] = {k: v for k, v in direction.items() if v["lowered_>0.01"] > 0}
    out["2_keys_checked"] = len(direction)

    # 3. calibration of classified objects (test split)
    cl = te[te.classification_status.eq("CLASSIFIED")]
    bins = pd.cut(cl.primary_confidence, [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001], right=False)
    cal = cl.assign(ok=cl.primary_class.eq(cl.truth_class)).groupby(bins, observed=True).agg(
        n=("ok", "size"), accuracy=("ok", "mean"), mean_conf=("primary_confidence", "mean")
    )
    out["3_calibration"] = {str(i): {k: round(float(v), 3) for k, v in row.items()} for i, row in cal.iterrows()}

    # 4. footprint keys: absence is no evidence, so they must stay out of the
    # trees (whose missing-value branches would learn the footprint) and
    # their linear weights must point towards QSO / extragalactic.
    pref = tuple((model.get("provenance") or {}).get("linear_only_keys") or ())
    tree_keys = (model.get("gbm") or {}).get("keys") or []
    lin = {k: v for k, v in model.get("coef", {}).items() if k.startswith(pref) and k.endswith("_detected")}
    out["4_footprint_keys"] = {
        "in_trees": [k for k in tree_keys if k.startswith(pref)],
        "detected_weights": {k: {c: round(w, 2) for c, w in v.items()} for k, v in lin.items()},
    }
    print("\nINTENT " + json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

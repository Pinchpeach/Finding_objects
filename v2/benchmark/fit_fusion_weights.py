#!/usr/bin/env python3
"""Fit Stage-5 coarse fusion weights on the benchmark train split.

Stage 5 is a linear log-odds model over evidence keys ``RULE:CLASS`` whose
value is ``logit(score)``.  This fits that same model (multinomial logistic
regression, L2) on the deterministic **train** split of the SDSS
spectroscopic benchmark, picks the regularization and the abstention
threshold on the **calibration** split, and reports the untouched **test**
split.  Keys with fewer than ``--min-support`` non-zero train rows are left
out, so Stage 5 keeps their hand-set prior weights (e.g. Gaia DSC, SIMBAD and
NED evidence, which this benchmark does not contain).
"""

from __future__ import annotations
import argparse, importlib.util, json, tempfile
from pathlib import Path
import numpy as np, pandas as pd

V2 = Path(__file__).resolve().parents[1]
PRE = V2 / "Preprocess"
CLASSES = ["STAR", "GALAXY", "QSO"]
GBM_BLEND = 0.5


def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def evidence_table(truth, catalog_root):
    base = load(Path(__file__).with_name("evaluate_rule_baseline.py"), "rule_baseline")
    base.pre = load(PRE / "02_integrate_objects.py", "integrate")
    raw = base.wide(truth, base.read_catalogs(catalog_root))
    s3 = load(PRE / "03_extract_features.py", "s3")
    s4 = load(PRE / "04_build_evidence.py", "s4")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        raw.to_csv(td / "o.csv", index=False)
        s3.run(td / "o.csv", PRE / "classification_rules.csv", td / "f.csv")
        s4.run(td / "f.csv", PRE / "classification_rules.csv", td / "e.csv")
        return pd.read_csv(td / "e.csv", usecols=["benchmark_id", "evidence_json"])


def design(evidence, s5, missing=0.0):
    rows = []
    kinds = {}
    for raw in evidence.evidence_json:
        x, k = s5.evidence_features(json.loads(raw) if isinstance(raw, str) else [])
        rows.append(x)
        kinds.update(k)
    keys = sorted({k for r in rows for k in r})
    X = np.array([[r.get(k, missing) for k in keys] for r in rows], dtype=float)
    used = np.array([len(r) > 0 for r in rows])
    return X, keys, kinds, used


def _groups(specs):
    """Comma-separated prefix groups (``--augment-drop`` / ``--report-drop``)."""
    return [[p for p in g.split(",") if p] for g in specs]


def augment(X, y, keys, groups, weight, missing):
    """Missing-feature augmentation: per group, one extra copy (sample weight
    ``weight``) of every row that has any of the group's keys, with those keys
    set to ``missing`` (0 = logit-neutral for the linear fit, NaN for trees);
    copies left without any evidence are skipped."""
    present = np.isfinite if missing != missing else (lambda v: v != 0)
    Xo, yo, wo = [X], [y], [np.ones(len(y))]
    for g in groups:
        cols = np.array([any(k.startswith(p) for p in g) for k in keys])
        has = present(X[:, cols]).any(axis=1)
        Xa = X[has].copy()
        Xa[:, cols] = missing
        ok = present(Xa).any(axis=1)
        Xo.append(Xa[ok])
        yo.append(y[has][ok])
        wo.append(np.full(int(ok.sum()), weight))
    return np.vstack(Xo), np.concatenate(yo), np.concatenate(wo)


def _wll(Z, yi, w):
    """Weighted multinomial log-loss of raw class scores ``Z``."""
    z = Z - Z.max(axis=1, keepdims=True)
    lp = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
    return float(-np.average(lp[np.arange(len(yi)), yi], weights=w))


def _evidence_key(item):
    """``RULE:CLASS`` key of a Stage-4 item, as ``evidence_features`` builds it."""
    c = item.get("class")
    if item.get("kind") != "linear_feature" and c in {"WD", "BINARY"}:
        c = "STAR"
    return f"{item.get('rule_id')}:{c}"


def coverage_curve(p, y, used, grid):
    conf = p.max(axis=1)
    pred = np.array(CLASSES)[p.argmax(axis=1)]
    out = []
    for t in grid:
        c = used & (conf >= t)
        out.append(
            {
                "threshold": float(t),
                "coverage": float(c.mean()),
                "accuracy": float((pred[c] == y[c]).mean()) if c.any() else None,
            }
        )
    return out


def ece(p, y, bins=10):
    """Expected calibration error of the top-class probability."""
    conf = p.max(axis=1)
    hit = np.array(CLASSES)[p.argmax(axis=1)] == y
    edges = np.linspace(1 / 3, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & ((conf < hi) | (hi == 1))
        if m.any():
            total += m.mean() * abs(hit[m].mean() - conf[m].mean())
    return float(total)


def export_trees(clf, path, features):
    """Flatten a fitted HistGradientBoostingClassifier into the arrays
    ``Preprocess/ls_gbm.raw_scores`` evaluates (numpy-only inference)."""
    feat, thr, mleft, left, right, leaf, value, start, tcls = [], [], [], [], [], [], [], [], []
    offset = 0
    for it in clf._predictors:
        for k, pred in enumerate(it):
            n = pred.nodes
            if n["is_categorical"].any():
                raise ValueError("categorical splits are not exported")
            start.append(offset)
            tcls.append(k)
            feat.append(n["feature_idx"].astype(np.int64))
            thr.append(n["num_threshold"].astype(float))
            mleft.append(n["missing_go_to_left"].astype(bool))
            left.append(n["left"].astype(np.int64))
            right.append(n["right"].astype(np.int64))
            leaf.append(n["is_leaf"].astype(bool))
            value.append(n["value"].astype(float))
            offset += len(n)
    np.savez_compressed(
        path,
        feature=np.concatenate(feat),
        threshold=np.concatenate(thr),
        missing_left=np.concatenate(mleft),
        left=np.concatenate(left),
        right=np.concatenate(right),
        is_leaf=np.concatenate(leaf),
        value=np.concatenate(value),
        tree_start=np.array(start, np.int64),
        tree_class=np.array(tcls, np.int64),
        baseline=np.asarray(clf._baseline_prediction, float).ravel(),
        n_classes=np.int64(len(clf.classes_)),
        classes=np.array(list(clf.classes_)),
        features=np.array(features),
    )


def fit_gbm(a, ev, s5, keys, keep, y, tr, ca, used):
    """Hybrid tree part: same supported keys, augmentation and splits as the
    linear fit, but absent evidence is a missing value (not logit 0), so a
    tree can tell "no morphology" from "neutral morphology"."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    Xn, keys_n, _, _ = design(ev, s5, missing=np.nan)
    assert keys_n == keys
    if a.drop_keys:
        Xn[:, [any(k.startswith(p) for p in a.drop_keys) for k in keys]] = np.nan
    # Footprint-limited surveys: a missing X-ray / radio counterpart says
    # where the object is, not what it is (eRASS1 covers half the sky; 33 % of
    # SDSS-truth but 4 % of DESI-truth QSOs have one), so these keys stay out
    # of the trees, whose missing-value branches would learn the footprint.
    keep = keep & ~np.array([k.startswith(tuple(a.linear_only)) for k in keys])
    sup = [k for k, m in zip(keys, keep) if m]
    Xs = Xn[:, keep]
    groups = _groups(a.augment_drop)
    Xf, yf, wf = augment(Xs[tr & used], y[tr & used], sup, groups, a.augment_weight, np.nan)
    Xc, yc, wc = augment(Xs[ca & used], y[ca & used], sup, groups, a.augment_weight, np.nan)
    yi = None
    best = None
    # Small grid chosen by calibration log-loss (2.25.0 experiment: shallow
    # trees, 7 leaves, lr 0.03 won; deeper trees overfit the 9k train rows).
    for lr in (0.03, 0.05):
        for leaves in (7, 15):
            clf = HistGradientBoostingClassifier(
                learning_rate=lr,
                max_leaf_nodes=leaves,
                max_iter=1500,
                l2_regularization=1.0,
                early_stopping=True,
                validation_fraction=0.15,
                random_state=0,
            ).fit(Xf, yf, sample_weight=wf)
            Z = clf._raw_predict(Xc)
            if yi is None:  # classes_ = sorted labels of yf, the same for every fit
                yi = np.array([list(clf.classes_).index(v) for v in yc])
            ll = _wll(Z, yi, wc)
            print(f"gbm lr={lr} leaves={leaves} iters={clf.n_iter_} cal log-loss={ll:.4f}")
            if best is None or ll < best[0]:
                best = (ll, clf, Z, lr, leaves)
    ll, clf, Z, lr, leaves = best

    # Temperature scaling (Guo et al. 2017, ICML): one scalar on the
    # calibration split, so the probabilities used for abstention are calibrated.
    def nll(T):
        return _wll(Z / T, yi, wc)

    T = float(min(np.round(np.arange(0.5, 3.001, 0.05), 2), key=nll))
    path = a.out.with_name(a.out.stem + "_gbm.npz")
    export_trees(clf, path, sup)
    print(f"gbm: lr={lr} leaves={leaves} iters={clf.n_iter_} temperature={T} -> {path}")
    return {
        "file": path.name,
        "keys": sup,
        "temperature": T,
        "learning_rate": lr,
        "max_leaf_nodes": leaves,
        "iterations": int(clf.n_iter_),
        "calibration_log_loss": nll(T),
        # Geometric-mean weight of the trees against the linear model.  0.5 on
        # the 2.25.0 calibration split: never below the linear model in any
        # missing-evidence case and keeps its Gaia-only faint-star recall,
        # which trees alone lowered (0.92 -> 0.87).
        "blend": GBM_BLEND,
    }


def main():
    ap = argparse.ArgumentParser()
    # Several truth sets may be combined (same order in each list); each keeps
    # its own deterministic train/calibration/test split and is reported apart.
    ap.add_argument("--truth", type=Path, nargs="+", required=True)
    ap.add_argument("--catalog-root", type=Path, nargs="+", required=True)
    ap.add_argument("--manifest", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, default=PRE / "fusion_weights.json")
    ap.add_argument("--linear-only", nargs="*", default=[], help="evidence-key prefixes kept out of the --gbm trees")
    ap.add_argument("--drop-keys", nargs="*", default=[], help="evidence-key prefixes to exclude (ablation)")
    ap.add_argument(
        "--augment-drop",
        nargs="*",
        default=[],
        help="augmentation groups, each a comma-separated list of evidence-key prefixes dropped together "
        "in an extra copy of every train row that has them (e.g. 'LS-MORPH,PS1-MORPH,SDSS-PHOTO' 'LS-'), "
        "so the remaining weights also learn the case where they are missing",
    )
    ap.add_argument(
        "--target-scope",
        choices=("pooled", "each"),
        default="pooled",
        help="'each': the abstention threshold must reach --target-accuracy on every dataset's calibration split",
    )
    ap.add_argument("--augment-weight", type=float, default=1.0, help="sample weight of the augmented copies")
    ap.add_argument(
        "--report-drop",
        nargs="*",
        default=None,
        help="also report test accuracy with these evidence prefixes removed (default: --augment-drop)",
    )
    ap.add_argument("--min-support", type=int, default=30)
    ap.add_argument("--gbm", action="store_true", help="fit the hybrid tree model (see module docstring)")
    ap.add_argument(
        "--target-accuracy",
        type=float,
        default=0.95,
        help="calibration-split accuracy the abstention threshold must reach",
    )
    a = ap.parse_args()
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss

    s5 = load(PRE / "05_likelihood_vectors.py", "s5")
    if not len(a.truth) == len(a.catalog_root) == len(a.manifest):
        ap.error("--truth/--catalog-root/--manifest counts differ")
    parts = []
    for t, root, man in zip(a.truth, a.catalog_root, a.manifest):
        e = evidence_table(pd.read_csv(t), root).merge(
            pd.read_csv(man)[["benchmark_id", "truth_class", "split"]], on="benchmark_id"
        )
        e["dataset"] = t.parent.name
        parts.append(e)
    ev = pd.concat(parts, ignore_index=True)
    X, keys, kinds, used = design(ev, s5)
    y = ev.truth_class.to_numpy()
    dropped = np.array([any(k.startswith(p) for p in a.drop_keys) for k in keys], dtype=bool)
    if a.drop_keys:
        X[:, dropped] = 0.0
    tr = ev.split.eq("train").to_numpy()
    ca = ev.split.eq("calibration").to_numpy()
    te = ev.split.eq("test").to_numpy()
    support = (X[tr] != 0).sum(axis=0)
    keep = support >= a.min_support
    Xk = X[:, keep]
    kept = [k for k, m in zip(keys, keep) if m]
    fit_rows = tr & used
    Xfit, yfit = Xk[fit_rows], y[fit_rows]
    Xcal, ycal = Xk[ca & used], y[ca & used]
    if a.augment_drop:
        # Missing-feature augmentation: faint objects in real fields often lack
        # e.g. a resolved-morphology measurement that nearly every benchmark
        # object has.  Without this the colour weights learn only the
        # conditional "given morphology" separation (red point source = star)
        # and send faint red galaxies to STAR.
        # Each argument is one augmentation group: comma-separated prefixes
        # dropped together in one extra copy (e.g. all morphology; or every
        # Legacy Surveys rule, as when that archive is unavailable).
        groups = _groups(a.augment_drop)
        Xfit, yfit, wfit = augment(Xfit, yfit, kept, groups, a.augment_weight, 0.0)
        Xcal, ycal, wcal = augment(Xcal, ycal, kept, groups, a.augment_weight, 0.0)
    else:
        wfit = np.ones(len(yfit))
        wcal = np.ones(len(ycal))
    groups_of = {"EXTRAGALACTIC": ("GALAXY", "QSO"), "POINT_SOURCE": ("STAR", "QSO")}

    def fit_best(cols):
        best = None
        for C in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0):
            m = LogisticRegression(C=C, max_iter=2000).fit(Xfit[:, cols], yfit, sample_weight=wfit)
            ll = log_loss(ycal, m.predict_proba(Xcal[:, cols]), labels=list(m.classes_), sample_weight=wcal)
            if best is None or ll < best[0]:
                best = (ll, C, m)
        return best

    # Sign constraint (2.11.0): evidence for class c ("RULE:c", logit of its
    # score) must raise the odds of c (or of its class group) above every
    # other class.  Collinear benchmark evidence can make the unconstrained fit
    # learn the opposite (Gaia DSC "STAR" got a negative STAR weight, so a
    # Gaia-only star was called GALAXY).  Violating keys are removed and the
    # fit repeated; they keep the literature prior weights in Stage 5.
    cols = list(range(len(kept)))
    sign_dropped = []
    while True:
        ll, C, m = fit_best(cols)
        order = [list(m.classes_).index(c) for c in CLASSES]
        bad = []
        for jj, j in enumerate(cols):
            key = kept[j]
            cls = key.rsplit(":", 1)[-1]
            if kinds.get(key) == "linear_feature":
                continue
            own = groups_of.get(cls, (cls,)) if cls in CLASSES or cls in groups_of else None
            if not own:
                continue
            w = {c: m.coef_[order[i], jj] for i, c in enumerate(CLASSES)}
            if max(w[c] for c in own) <= max((w[c] for c in CLASSES if c not in own), default=-np.inf):
                bad.append(j)
        if not bad:
            break
        sign_dropped += [kept[j] for j in bad]
        cols = [j for j in cols if j not in bad]
    print("sign-constraint dropped:", sign_dropped)
    kept = [kept[j] for j in cols]
    coef = {k: {c: float(m.coef_[order[i], j]) for i, c in enumerate(CLASSES)} for j, k in enumerate(kept)}
    model = {
        "version": 1,
        "classes": CLASSES,
        "intercept": {c: float(m.intercept_[order[i]]) for i, c in enumerate(CLASSES)},
        "coef": coef,
        "min_margin": 0.0,
        "training_prior": {c: float((y[fit_rows] == c).mean()) for c in CLASSES},
        "semantics": "multinomial-logistic probability fitted on class-balanced spectroscopic benchmarks (equal priors); evidence keys without training support use prior weights",
        "provenance": {
            "benchmarks": [str(t) for t in a.truth],
            "dropped_keys": a.drop_keys,
            "linear_only_keys": a.linear_only,
            "train_rows": int(fit_rows.sum()),
            "augment_drop": a.augment_drop,
            "augment_weight": a.augment_weight,
            "augmented_train_rows": int(len(yfit)),
            "calibration_rows": int((ca & used).sum()),
            "C": C,
            "calibration_log_loss": float(ll),
            "min_support": a.min_support,
            "support": {k: int(s) for k, s in zip(keys, support)},
            "prior_weight_keys": [k for k, mk, dk in zip(keys, keep, dropped) if not (mk or dk)] + sign_dropped,
            "sign_dropped_keys": sign_dropped,
        },
    }
    if a.drop_keys:
        # Ablation: these keys are removed from the evidence (fit and every
        # evaluation below), not left to their Stage-5 prior weights.
        model["provenance"]["excluded_keys"] = [k for k, dk in zip(keys, dropped) if dk]

    if a.gbm:
        model["gbm"] = fit_gbm(a, ev, s5, keys, keep, y, tr, ca, used)
        model["semantics"] = (
            "hybrid: gradient-boosted trees over benchmark-supported evidence keys (temperature-calibrated), "
            "plus prior weights for keys without training support; fitted on class-balanced benchmarks"
        )

    # Probabilities exactly as Stage 5 will compute them, without the
    # --drop-keys evidence (otherwise fuse_many would add it back with its
    # prior weights) and without any ``drop`` (rule or key prefixes).
    def probs(mask, drop=()):
        drop = tuple(a.drop_keys) + tuple(drop)
        lists = []
        for raw in ev.evidence_json[mask]:
            items = json.loads(raw) if isinstance(raw, str) else []
            if drop:
                items = [
                    i
                    for i in items
                    if not str(i.get("rule_id", "")).startswith(drop) and not _evidence_key(i).startswith(drop)
                ]
            lists.append(items)
        return np.array([[p[c] for c in CLASSES] for p, _ in s5.fuse_many(lists, model, a.out.parent)]).reshape(
            -1, len(CLASSES)
        )

    # Floor = Stage 5's MIN_CONFIDENCE (0.50): below it the top class is more
    # likely wrong than right.  Without the floor the 2.25.0 hybrid model
    # reached the target at the lowest grid value (0.34) and real fields lost
    # all LOW_CONFIDENCE abstentions -- mostly LS-only objects at r ~ 24.5,
    # fainter than any benchmark object (DESI field validation, 3 fields).
    grid = np.round(np.arange(s5.MIN_CONFIDENCE, 0.991, 0.01), 2)
    pca = probs(ca)
    curve = coverage_curve(pca, y[ca], used[ca], grid)
    if a.target_scope == "each":
        # Faint objects (e.g. DESI) are harder than bright ones (SDSS); a pooled
        # target lets the larger bright set hide the faint set's errors.
        curves = []
        for name in ev.dataset[ca].unique():  # train-only sets (desi_fusion) have no calibration rows
            mk = ca & ev.dataset.eq(name).to_numpy()
            curves.append(coverage_curve(probs(mk), y[mk], used[mk], grid))
        ok = [
            r
            for r, *rest in zip(curve, *curves)
            if all(c["accuracy"] is not None and c["accuracy"] >= a.target_accuracy for c in rest)
        ]
    else:
        ok = [r for r in curve if r["accuracy"] is not None and r["accuracy"] >= a.target_accuracy]
    model["min_confidence"] = ok[0]["threshold"] if ok else 0.9
    model["provenance"]["calibration_curve"] = curve
    model["provenance"]["target_calibration_accuracy"] = a.target_accuracy
    model["provenance"]["target_scope"] = a.target_scope
    test = {}
    for name in ev.dataset[te].unique():
        mask = te & ev.dataset.eq(name).to_numpy()
        pte = probs(mask)
        yte = y[mask]
        ute = used[mask]
        conf = pte.max(axis=1)
        pred = np.array(CLASSES)[pte.argmax(axis=1)]
        cl = ute & (conf >= model["min_confidence"])
        test[name] = {
            "rows": int(mask.sum()),
            "classified": int(cl.sum()),
            "coverage": float(cl.mean()),
            "accuracy_when_classified": float((pred[cl] == yte[cl]).mean()) if cl.any() else None,
            "accuracy_all_unknown_wrong": float((np.where(cl, pred, "UNKNOWN") == yte).mean()),
            "recall": {c: float((pred[yte == c] == c).mean()) for c in CLASSES},
            "log_loss_used": float(log_loss(yte[ute], pte[ute][:, np.argsort(CLASSES)], labels=sorted(CLASSES))),
            "expected_calibration_error": ece(pte[ute], yte[ute]),
            "accuracy_by_threshold": coverage_curve(pte, yte, ute, (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)),
        }
        rdrop = a.augment_drop if a.report_drop is None else a.report_drop
        for g in _groups(rdrop):
            # Same test rows with a group of evidence removed: how the model
            # behaves on objects that lack it (e.g. faint, unresolved fits).
            pd_ = probs(mask, g)
            pr = np.array(CLASSES)[pd_.argmax(axis=1)]
            test[name]["without_" + "+".join(g)] = {
                "argmax_accuracy": float((pr == yte).mean()),
                "recall": {c: float((pr[yte == c] == c).mean()) for c in CLASSES},
            }
    model["provenance"]["test"] = test
    a.out.write_text(json.dumps(model, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "C": C,
                "kept_keys": len(kept),
                "prior_keys": model["provenance"]["prior_weight_keys"],
                "min_confidence": model["min_confidence"],
                "test": test,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()

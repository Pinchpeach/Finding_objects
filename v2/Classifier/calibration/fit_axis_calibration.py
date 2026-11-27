#!/usr/bin/env python3
"""Fit per-axis calibration from independent truth/evaluation rows.

Two methods (2.15.0):
* rule_precision: most axis labels come from rules without a score, so the
  calibrated probability of a label is the measured precision of the rule
  that produced it -- the share of rows with that (status, label) whose truth
  is that label -- on the independent truth sets (class-balanced, so a
  precision for that mix, not a sky-prior posterior).  Only for labels that
  are among the axis's truth classes (otherwise there is nothing to be right
  about), with at least MIN_RULE_ROWS rows; the Wilson 95 % lower bound is
  stored with it.
* platt: one-vs-rest logistic calibration of a raw score (unchanged).

Input columns: axis, truth_class, predicted_class, raw_score.  A class model is
written only when both positive and negative support are adequate.  Rows whose
truth source overlaps the evidence source may be excluded with `leakage=1`.

2.61.9: the fit is no longer part of the automatic commit of the cross-validation workflow.  Its coefficients are a deterministic function of the
predictions file (checked: a refit of the predictions of four bot commits reproduces their ``models.json``), so a change of the coefficients is a change of the
truth list or of an archive.  A refit is an explicit run (``refit_calibration``) and the result is committed by hand with a version number;
``--fitted-on-json`` stamps the provenance (SHA-256 of the truth list and of the predictions, the run status, the commit) into the file as ``fitted_on``.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

MIN_SAMPLES = 100
MIN_POSITIVES = 20
MIN_NEGATIVES = 20
MIN_RULE_ROWS = 20


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return (c - r) / d


def rule_precision(df: pd.DataFrame) -> dict:
    out = {}
    if "status" not in df:
        return out
    for axis, g in df.groupby("axis"):
        truth = set(g["truth_class"].dropna().astype(str))
        res = {}
        for (status, label), h in g.groupby([g["status"].astype(str), g["predicted_class"].astype(str)]):
            if label not in truth:
                continue
            # A broader family label is right for its members (Mira labelled LPV):
            # the validator's family_match credits exactly those cases.
            ok = (
                h["family_match"].fillna(False).astype(bool)
                if "family_match" in h
                else h["truth_class"].astype(str).eq(label)
            )
            n = len(h)
            k = int(ok.sum())
            if n < MIN_RULE_ROWS:
                continue
            res[f"{status}|{label}"] = {
                "method": "rule_precision",
                "n": n,
                "correct": k,
                "precision": round(k / n, 4),
                "wilson_lower_95": round(wilson_lower(k, n), 4),
                "truth_classes": sorted(truth),
            }
        out[axis] = res
    return out


def fit(inp: Path, out: Path, fitted_on: dict | None = None):
    from sklearn.linear_model import LogisticRegression

    df = pd.read_csv(inp)
    required = {"axis", "truth_class", "predicted_class", "raw_score"}
    if not required.issubset(df.columns):
        raise KeyError(f"missing columns: {required-set(df.columns)}")
    if "leakage" in df:
        df = df[~df["leakage"].fillna(False).astype(bool)].copy()
    rules = rule_precision(df)
    # Rule precisions measured by separate truth jobs (e.g. 2.22.0
    # benchmark/new_targets) carry "external_source" and are kept on refit.
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8")).get("rules", {})
            for axis, entries in prev.items():
                for key, rm in entries.items():
                    if rm.get("external_source") and key not in rules.get(axis, {}):
                        rules.setdefault(axis, {})[key] = rm
        except (OSError, ValueError):
            pass
    df["raw_score"] = pd.to_numeric(df["raw_score"], errors="coerce")
    df = df.dropna(subset=["raw_score"])
    result = {
        "schema_version": 2,
        "policy": {
            "method": "platt",
            "min_samples": MIN_SAMPLES,
            "min_positives": MIN_POSITIVES,
            "min_negatives": MIN_NEGATIVES,
            "min_rule_rows": MIN_RULE_ROWS,
        },
        "axes": {},
        "rules": rules,
    }
    if fitted_on:
        result["fitted_on"] = fitted_on
    for axis, g in df.groupby("axis"):
        classes = sorted(set(g["truth_class"].dropna().astype(str)) | set(g["predicted_class"].dropna().astype(str)))
        result["axes"][axis] = {}
        for label in classes:
            y = (g["truth_class"].astype(str) == label).astype(int)
            n = len(g)
            pos = int(y.sum())
            neg = n - pos
            meta = {"n": n, "positive": pos, "negative": neg, "truth_independent": True}
            if n < MIN_SAMPLES or pos < MIN_POSITIVES or neg < MIN_NEGATIVES:
                result["axes"][axis][label] = {
                    **meta,
                    "method": "withheld",
                    "reason": "insufficient independent truth support",
                }
                continue
            # Score for the candidate class: zero when a different class was predicted.
            x = (
                (g["raw_score"].clip(0, 1) * (g["predicted_class"].astype(str) == label).astype(float))
                .to_numpy()
                .reshape(-1, 1)
            )
            m = LogisticRegression(solver="lbfgs").fit(x, y)
            result["axes"][axis][label] = {
                **meta,
                "method": "platt",
                "coef": float(m.coef_[0, 0]),
                "intercept": float(m.intercept_[0]),
            }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fitted-on-json", type=Path, help="a JSON object stored as `fitted_on` (the provenance of this fit)")
    a = p.parse_args()
    fit(a.input, a.out, json.loads(a.fitted_on_json.read_text(encoding="utf-8")) if a.fitted_on_json else None)


if __name__ == "__main__":
    main()

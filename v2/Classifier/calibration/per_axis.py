"""Per-axis reliability utilities.

Kept apart from raw evidence.  A model is only usable when it was fit on an
independent truth set meeting minimum sample/positive/negative counts;
otherwise the reliability columns stay NaN.

What the number means (2.51.0, scientific review 2026-11-11): most truth sets
behind these models hold only the target classes (e.g. Cepheid / LPV / Mira /
RR Lyrae, or HASH PNe), so the value is the agreement of the rule with
those labels, not its precision against contaminants on the sky; it was
previously reported as "calibrated_probability" with status CALIBRATED.
Columns are now ``{axis}_reliability`` with ``{axis}_reliability_status``:

  PRECISION_SKY_SAMPLE   precision on a sky-random sample passing the rule
                         (contaminants included; build_truth.py samples)
  AGREEMENT_TARGET_SET   agreement within a target-class-only truth set
  NO_MODEL / INSUFFICIENT_TRUTH
"""

from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd

MIN_SAMPLES = 100
MIN_POSITIVES = 20
MIN_NEGATIVES = 20


def sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def load_models(path: Path):
    if not path.exists():
        return {"axes": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"axes": {}}


def _usable(model):
    return bool(
        model
        and model.get("method") == "platt"
        and int(model.get("n", 0)) >= MIN_SAMPLES
        and int(model.get("positive", 0)) >= MIN_POSITIVES
        and int(model.get("negative", 0)) >= MIN_NEGATIVES
    )


def calibrate_score(score, model):
    try:
        x = float(score)
    except Exception:
        return None
    if not math.isfinite(x) or not _usable(model):
        return None
    return sigmoid(float(model["coef"]) * x + float(model["intercept"]))


def annotate(
    df: pd.DataFrame, model_path: Path, axes=("physical", "variability", "compact", "extragalactic", "phenomenon")
):
    models = load_models(model_path)
    out = df.copy()
    for axis in axes:
        axis_models = models.get("axes", {}).get(axis, {})
        probs = []
        statuses = []
        methods = []
        labels = out[f"{axis}_class"] if f"{axis}_class" in out else pd.Series("UNKNOWN", index=out.index)
        scores = out[f"{axis}_confidence"] if f"{axis}_confidence" in out else pd.Series(None, index=out.index)
        rule_models = models.get("rules", {}).get(axis, {})
        stat = out[f"{axis}_status"].astype(str) if f"{axis}_status" in out else pd.Series("", index=out.index)
        for label, score, st in zip(labels.astype(str), scores, stat):
            rm = rule_models.get(f"{st}|{label}")
            if rm and rm.get("method") == "rule_precision":
                # Measured agreement / precision of the rule that produced this label (2.15.0).
                probs.append(float(rm["precision"]))
                statuses.append("PRECISION_SKY_SAMPLE" if rm.get("external_source") else "AGREEMENT_TARGET_SET")
                methods.append("rule_precision")
                continue
            model = axis_models.get(label)
            p = calibrate_score(score, model)
            probs.append(p)
            if p is None:
                statuses.append("INSUFFICIENT_TRUTH" if model else "NO_MODEL")
                methods.append(None)
            else:
                # Platt fits use the same target-class-only variability set.
                statuses.append("AGREEMENT_TARGET_SET")
                methods.append(model.get("method"))
        out[f"{axis}_reliability"] = probs
        out[f"{axis}_reliability_status"] = statuses
        out[f"{axis}_reliability_method"] = methods
    return out

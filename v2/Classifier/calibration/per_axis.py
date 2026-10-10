"""Per-axis calibration utilities.

Calibration is intentionally separated from raw evidence.  A model is only
considered usable when it was fit on an independent truth set meeting minimum
sample/positive/negative counts.  Otherwise probability columns remain NaN.
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
        for label, score in zip(labels.astype(str), scores):
            model = axis_models.get(label)
            p = calibrate_score(score, model)
            probs.append(p)
            if p is None:
                statuses.append("UNCALIBRATED_INSUFFICIENT_TRUTH" if model else "UNCALIBRATED_NO_MODEL")
                methods.append(None)
            else:
                statuses.append("CALIBRATED")
                methods.append(model.get("method"))
        out[f"{axis}_calibrated_probability"] = probs
        out[f"{axis}_calibration_status"] = statuses
        out[f"{axis}_calibration_method"] = methods
    return out

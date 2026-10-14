#!/usr/bin/env python3
"""Transition wrapper for the validated learned primary classifier."""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "benchmark" / "train_validate_classifier.py"), run_name="__main__"
)

#!/usr/bin/env python3
"""Transition wrapper for the validated radio/X-ray adaptive classifier."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1]/"benchmark"/"train_validate_rx_adaptive.py"),run_name="__main__")

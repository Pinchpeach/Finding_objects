"""GUI-independent backend of the standalone app: runs the v2 pipeline in a
worker thread and reports progress through a callback, so the same code
serves the desktop GUI, a CLI, and tests."""
from __future__ import annotations
import threading, traceback
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
SUMMARY_COLUMNS = ["object_id", "catalogs", "primary_class", "primary_confidence",
                   "classification_status", "p_star", "p_galaxy", "p_qso"]


@dataclass
class Job:
    work: Path
    ra: float | None = None
    dec: float | None = None
    radius_arcmin: float | None = None
    raw_dir: Path | None = None
    min_confidence: float | None = None


def _pipeline():
    import importlib.util, sys
    if str(V2) not in sys.path:
        sys.path.insert(0, str(V2))
    spec = importlib.util.spec_from_file_location("v2_pipeline", V2 / "pipeline.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def run_job(job: Job, log=print) -> pd.DataFrame:
    """Run collection (unless raw_dir is given) and classification; return the summary table."""
    log(f"start: {job}")
    out = _pipeline().run(job.work, job.raw_dir, job.ra, job.dec, job.radius_arcmin, job.min_confidence)
    cols = [c for c in SUMMARY_COLUMNS if c in out.columns]
    log(f"done: {len(out)} objects")
    return out[cols]


def run_in_background(job: Job, log, on_done, on_error) -> threading.Thread:
    def target():
        try:
            on_done(run_job(job, log))
        except Exception as exc:  # surfaced in the GUI, never swallowed
            on_error(exc, traceback.format_exc())
    t = threading.Thread(target=target, daemon=True)
    t.start()
    return t

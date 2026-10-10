#!/usr/bin/env python3
"""One-command v2 pipeline: collect -> associate -> integrate -> features ->
evidence -> coarse STAR/GALAXY/QSO -> detailed multi-axis classification.

Examples::

    # Full run for a sky position (queries the survey archives):
    python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 0.5 --work runs/ngc4522

    # Re-run classification on already-collected raw catalogs:
    python v2/pipeline.py --raw-dir v2/rawdata --work runs/ngc4522

    # ... keeping only objects within 0.2 arcmin of a position:
    python v2/pipeline.py --raw-dir v2/rawdata --ra 188.4155 --dec 9.1751 --radius 0.2 --work runs/core

Tables pass between stages in memory. ``--work`` receives
``source_association.csv``, ``classified_objects.csv`` and the per-stage wall
time ``pipeline_summary.csv``; ``--keep-intermediate`` also writes every stage
table for inspection.
"""

from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import pandas as pd

V2 = Path(__file__).resolve().parent
PRE = V2 / "Preprocess"
CLS = V2 / "Classifier"
GET = V2 / "Get_data"
if str(V2) not in sys.path:
    sys.path.insert(0, str(V2))
from common import load_module  # noqa: E402

RESULT = "classified_objects.csv"
ASSOCIATION = "source_association.csv"
INTERMEDIATE = {
    "2_integrate": "integrated_objects.csv",
    "3_features": "features.csv",
    "4_evidence": "evidence.csv",
    "5_coarse": "likelihood_vectors.csv",
    "6_prepare": "classifier_input.csv",
}


def run(
    work: Path,
    raw_dir: Path | None = None,
    ra: float | None = None,
    dec: float | None = None,
    radius: float | None = None,
    min_confidence: float | None = None,
    workers: int = 6,
    field_prior: bool = False,
    keep_intermediate: bool = False,
) -> pd.DataFrame:
    """Run every stage; tables pass between stages in memory.

    ``source_association.csv``, ``classified_objects.csv`` and
    ``pipeline_summary.csv`` are always written; the other stage tables only
    with ``keep_intermediate`` (each is a full copy of the wide object table).
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    timings = []

    def step(name, fn, *args):
        t = time.monotonic()
        result = fn(*args)
        timings.append({"stage": name, "seconds": round(time.monotonic() - t, 3)})
        print(f"[pipeline] {name}: {timings[-1]['seconds']} s", flush=True)
        return result

    def keep(name):
        return work / INTERMEDIATE[name] if keep_intermediate else None

    collect = raw_dir is None
    if collect:
        if None in (ra, dec, radius):
            raise ValueError("give --raw-dir, or --ra/--dec/--radius to collect")
        raw_dir = work / "raw"
        step("collect", load_module(GET / "controller.py").collect_all, ra, dec, radius, raw_dir, workers)
    raw_dir = Path(raw_dir)

    rules = PRE / "classification_rules.csv"
    s1, s2, s3, s4, s5 = (
        load_module(PRE / f)
        for f in (
            "01_source_association.py",
            "02_integrate_objects.py",
            "03_extract_features.py",
            "04_build_evidence.py",
            "05_likelihood_vectors.py",
        )
    )
    prepare = load_module(CLS / "01_prepare_input.py")
    control = load_module(CLS / "control.py")

    assoc = step("1_associate", s1.run, raw_dir, work / ASSOCIATION)
    df = step("2_integrate", s2.run, assoc, raw_dir, keep("2_integrate"))
    df = step("3_features", s3.run, df, rules, keep("3_features"))
    df = step("4_evidence", s4.run, df, rules, keep("4_evidence"))
    df = step("5_coarse", s5.run, df, keep("5_coarse"), s5.MODEL_PATH, min_confidence, field_prior)
    df = step("6_prepare", prepare.run, df, keep("6_prepare"))
    df = step("7_classify", control.run, df)

    # Real catalogue designations instead of the run-local OBJ ids; fragments
    # of one large galaxy grouped under it; with a centre, distance from it
    # (and, for already-collected data, the cone cut).
    names = load_module(V2 / "designations.py")
    hosts = load_module(V2 / "host_groups.py")
    out = hosts.consolidate(names.annotate(df, assoc), names.PRIORITY)
    if out.n_components.gt(0).any():  # hosts may have inherited a nucleus spectrum
        out = load_module(CLS / "subclass.py").annotate(out)
    out = names.annotate(out, assoc, None if None in (ra, dec) else (ra, dec), None if collect else radius)
    out.to_csv(work / RESULT, index=False)

    summary = pd.DataFrame(timings)
    summary.to_csv(work / "pipeline_summary.csv", index=False)
    print(
        f"[pipeline] {len(out)} objects; primary classes {out.primary_class.value_counts().to_dict()}; "
        f"total {summary.seconds.sum():.1f} s -> {work / RESULT}",
        flush=True,
    )
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", type=Path, required=True, help="output directory for all stage products")
    p.add_argument("--raw-dir", type=Path, help="use already-collected raw catalog CSVs instead of querying")
    p.add_argument("--ra", type=float, help="ICRS RA in degrees")
    p.add_argument("--dec", type=float, help="ICRS Dec in degrees")
    p.add_argument(
        "--radius", type=float, help="cone radius in arcminutes (with --raw-dir: keep only objects inside it)"
    )
    p.add_argument(
        "--min-confidence",
        type=float,
        help="coarse abstention threshold; higher = fewer but more reliable labels "
        "(e.g. 0.8: ~94%% accuracy at ~73%% coverage on faint DESI objects)",
    )
    p.add_argument("--workers", type=int, default=6, help="parallel archive queries during collection")
    p.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="also write every stage table (integrated_objects.csv ... classifier_input.csv)",
    )
    p.add_argument(
        "--field-prior",
        action="store_true",
        help="re-weight coarse classes by this field's EM-estimated class mix (off by default)",
    )
    a = p.parse_args()
    if a.raw_dir is None and None in (a.ra, a.dec, a.radius):
        p.error("give --raw-dir, or all of --ra/--dec/--radius")
    if (a.ra is None) != (a.dec is None):
        p.error("give both --ra and --dec")
    if a.radius is not None and a.radius <= 0:
        p.error("--radius must be > 0")
    run(
        a.work,
        a.raw_dir,
        a.ra,
        a.dec,
        a.radius,
        a.min_confidence,
        max(1, a.workers),
        a.field_prior,
        a.keep_intermediate,
    )


if __name__ == "__main__":
    main()

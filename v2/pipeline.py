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

Every stage writes its CSV into ``--work`` so intermediate products stay
inspectable; per-stage wall time is written to ``pipeline_summary.csv``.
"""
from __future__ import annotations
import argparse, importlib.util, sys, time
from pathlib import Path
import pandas as pd

V2 = Path(__file__).resolve().parent
PRE = V2 / "Preprocess"
CLS = V2 / "Classifier"
GET = V2 / "Get_data"


def _load(path: Path, name: str):
    for p in (str(path.parent),):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EMPTY_RESULT_COLUMNS = ["object_id", "designation", "ra", "dec", "catalogs", "primary_class", "primary_confidence",
                        "classification_status", "subclass", "subclass_tags", "subclass_status"]


def run(work: Path, raw_dir: Path | None = None, ra: float | None = None, dec: float | None = None,
        radius: float | None = None, min_confidence: float | None = None, workers: int = 6,
        field_prior: bool = False) -> pd.DataFrame:
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    timings = []

    def step(name, fn, *args):
        t = time.monotonic()
        fn(*args)
        timings.append({"stage": name, "seconds": round(time.monotonic() - t, 3)})
        print(f"[pipeline] {name}: {timings[-1]['seconds']} s", flush=True)

    collect = raw_dir is None
    if collect:
        if None in (ra, dec, radius):
            raise ValueError("give --raw-dir, or --ra/--dec/--radius to collect")
        controller = _load(GET / "controller.py", "v2_get_data_controller")
        # One raw folder per search position: Stage 1 reads every CSV in the
        # folder, so a shared folder mixed earlier searches into later results.
        raw_dir = work / "raw" / controller._tag(ra, dec, radius)
        step("collect", controller.collect_all, ra, dec, radius, raw_dir, workers)

    rules = PRE / "classification_rules.csv"
    s1 = _load(PRE / "01_source_association.py", "v2_stage1")
    s2 = _load(PRE / "02_integrate_objects.py", "v2_stage2")
    s3 = _load(PRE / "03_extract_features.py", "v2_stage3")
    s4 = _load(PRE / "04_build_evidence.py", "v2_stage4")
    s5 = _load(PRE / "05_likelihood_vectors.py", "v2_stage5")
    prep = _load(CLS / "01_prepare_input.py", "v2_classifier_prepare")
    control = _load(CLS / "control.py", "v2_classifier_control")

    step("1_associate", s1.run, Path(raw_dir), work / "source_association.csv")
    if pd.read_csv(work / "source_association.csv").empty:
        # Nothing detected (empty sky patch, tiny radius, or every archive
        # down): an empty result, not a failure of the later stages.
        out = pd.DataFrame(columns=EMPTY_RESULT_COLUMNS)
        out.to_csv(work / "classified_objects.csv", index=False)
        pd.DataFrame(timings).to_csv(work / "pipeline_summary.csv", index=False)
        print("[pipeline] 0 objects: no detections in the search area", flush=True)
        return out
    step("2_integrate", s2.run, work / "source_association.csv", Path(raw_dir), work / "integrated_objects.csv")
    step("3_features", s3.run, work / "integrated_objects.csv", rules, work / "features.csv")
    step("4_evidence", s4.run, work / "features.csv", rules, work / "evidence.csv")
    step("5_coarse", s5.run, work / "evidence.csv", work / "likelihood_vectors.csv", s5.MODEL_PATH, min_confidence, field_prior)
    step("6_prepare", prep.run, work / "likelihood_vectors.csv", work / "classifier_input.csv")
    step("7_classify", control.run, work / "classifier_input.csv", work / "classified_objects.csv")

    # Real catalogue designations instead of the run-local OBJ ids; fragments
    # of one large galaxy grouped under it; with a centre, distance from it
    # (and, for already-collected data, the cone cut).
    names = _load(V2 / "designations.py", "v2_designations")
    hosts = _load(V2 / "host_groups.py", "v2_host_groups")
    assoc = pd.read_csv(work / "source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"})
    out = names.annotate(pd.read_csv(work / "classified_objects.csv", low_memory=False), assoc)
    out = hosts.consolidate(out, names.PRIORITY)
    if out.n_components.gt(0).any():        # hosts may have inherited a nucleus spectrum
        out = _load(CLS / "subclass.py", "v2_subclass").annotate(out)
    out = names.annotate(out, assoc, None if None in (ra, dec) else (ra, dec), None if collect else radius)
    out.to_csv(work / "classified_objects.csv", index=False)

    summary = pd.DataFrame(timings)
    summary.to_csv(work / "pipeline_summary.csv", index=False)
    print(f"[pipeline] {len(out)} objects; primary classes {out.primary_class.value_counts().to_dict()}; "
          f"total {summary.seconds.sum():.1f} s -> {work / 'classified_objects.csv'}", flush=True)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", type=Path, required=True, help="output directory for all stage products")
    p.add_argument("--raw-dir", type=Path, help="use already-collected raw catalog CSVs instead of querying")
    p.add_argument("--ra", type=float, help="ICRS RA in degrees")
    p.add_argument("--dec", type=float, help="ICRS Dec in degrees")
    p.add_argument("--radius", type=float, help="cone radius in arcminutes (with --raw-dir: keep only objects inside it)")
    p.add_argument("--min-confidence", type=float,
                   help="coarse abstention threshold; higher = fewer but more reliable labels "
                        "(e.g. 0.8: ~94%% accuracy at ~73%% coverage on faint DESI objects)")
    p.add_argument("--workers", type=int, default=6, help="parallel archive queries during collection")
    p.add_argument("--field-prior", action="store_true",
                   help="re-weight coarse classes by this field's EM-estimated class mix (off by default)")
    a = p.parse_args()
    if a.raw_dir is None and None in (a.ra, a.dec, a.radius):
        p.error("give --raw-dir, or all of --ra/--dec/--radius")
    if (a.ra is None) != (a.dec is None):
        p.error("give both --ra and --dec")
    if a.radius is not None and a.radius <= 0:
        p.error("--radius must be > 0")
    run(a.work, a.raw_dir, a.ra, a.dec, a.radius, a.min_confidence, max(1, a.workers), a.field_prior)


def exit_now(code: int = 0) -> None:
    """Exit after a finished run without interpreter teardown.  All outputs are
    written and closed by then.  Teardown after a run with archive queries
    segfaulted in CI after the results were written (scientific
    cross-validation, compact-pulsar shard, twice), also with no Python
    thread left alive, i.e. in a C extension's cleanup.  Callers use this
    only after success; errors still raise and exit normally."""
    import os
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
    exit_now(0)

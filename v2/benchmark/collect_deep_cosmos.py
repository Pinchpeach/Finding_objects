#!/usr/bin/env python3
"""Collect the nine deep COSMOS fields blind, with their COSMOS2020 truth (2.57.0).

The same inputs as ``.github/workflows/experiment-ab-fields.yml`` (``fieldset=deep``):
the nine 6' fields of ``measure_cosmos_xray_agn.FIELDS``, every collector except the
spectroscopic and literature ones (the workflow's blind list), and the COSMOS2020
Classic rows of each cone as truth.  For use where the archives are reachable from
the machine itself; the workflow does the same on GitHub Actions.

    python v2/benchmark/collect_deep_cosmos.py --out DIR [--fields deep_cosmos_1,deep_cosmos_2]

writes ``DIR/<field>/{raw/<tag>/*.csv, truth/J_ApJS_258_11_classic.csv.gz, field.json}``.
A field whose collection summary shows no failed key archive is not collected again;
a failed key archive is asked again with ``controller.retry_failed`` (2.57.0), up to
``--retries`` times.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
REPO = V2.parent
FIELDS = {
    "deep_cosmos_1": (149.85, 1.95),
    "deep_cosmos_2": (149.85, 2.21),
    "deep_cosmos_3": (149.85, 2.47),
    "deep_cosmos_4": (150.12, 1.95),
    "deep_cosmos_5": (150.12, 2.21),
    "deep_cosmos_6": (150.12, 2.47),
    "deep_cosmos_7": (150.39, 1.95),
    "deep_cosmos_8": (150.39, 2.21),
    "deep_cosmos_9": (150.39, 2.47),
}
RADIUS_ARCMIN = 6.0
# Not collected: the workflow drops these files from the blind run (spectra and literature compilations).
NOT_BLIND = (
    "lamost_spectroscopy",
    "sdss_spectroscopy",
    "desi_spectroscopy",
    "desi_fastspec",
    "simbad",
    "ned",
    "bzcat",
    "pn_spectroscopy",
    "hash_pn",
    "asas_sn_supernova",
    "asiago_supernova",
    "agb_suh2021",
    "atnf_pulsar",
    "galaxy_clusters",
)


def _load(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gaia_source(raw: Path) -> str:
    """ "tap" when the collected Gaia rows come from the ESA archive, "vizier_fallback" for the VizieR copy,
    "empty" without rows, "none" without a file."""
    import pandas as pd

    files = sorted(raw.glob("gaia_dr3_ra*.csv"))
    if not files:
        return "none"
    st = pd.read_csv(files[0], usecols=lambda c: c == "gaia_base_query_status", dtype=str, keep_default_na=False)
    return str(st.iloc[0, 0]) if len(st) and st.shape[1] else "empty"


def collect_field(name: str, out: Path, workers: int, retries: int) -> dict:
    ra, dec = FIELDS[name]
    ctl = _load(V2 / "Get_data" / "controller.py", "deep_controller")
    cov = _load(V2 / "catalog_coverage.py", "deep_coverage")
    truth = _load(REPO / ".github" / "scripts" / "independent_truth_field.py", "deep_truth")
    fdir = out / name
    raw = fdir / "raw" / ctl._tag(ra, dec, RADIUS_ARCMIN)
    if not (fdir / "truth" / "J_ApJS_258_11_classic.csv.gz").exists():
        truth.truth_deep(ra, dec, RADIUS_ARCMIN, fdir / "truth")
    (fdir / "field.json").write_text(json.dumps({"ra": ra, "dec": dec, "radius_arcmin": RADIUS_ARCMIN}))
    full = list(ctl.COLLECTORS)
    ctl.COLLECTORS[:] = [c for c in full if c not in NOT_BLIND]  # collect_all reads the module list
    try:
        if not list(raw.glob("collection_summary_*.csv")):
            ctl.collect_all(ra, dec, RADIUS_ARCMIN, raw, workers)
        for k in range(retries):
            todo = ctl.failed_collectors(raw, "key")
            if not todo:
                break
            print(f"[{name}] key archives to ask again ({k + 1}/{retries}): {todo}", flush=True)
            ctl.retry_failed(raw, ra, dec, RADIUS_ARCMIN, workers, "key")
    finally:
        ctl.COLLECTORS[:] = full
    state = cov.summarize(raw)
    return {
        "field": name,
        "gaia_source": gaia_source(raw),
        "failed": [f["collector"] for f in state.get("failed", [])],
        "alternative": [a["collector"] for a in state.get("alternative", [])],
        "key_failed": state.get("key_failed", False),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fields", default="", help="comma list; default: every field of the list")
    p.add_argument(
        "--fields-file", type=Path, help="fields csv (name, ra, dec, r), e.g. deep_cosmos_fields_2.csv (2.59.0)"
    )
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument(
        "--require-gaia-tap",
        action="store_true",
        help="fail unless every field's Gaia rows are the ESA archive's, not the VizieR copy",
    )
    a = p.parse_args()
    if a.fields_file:
        import pandas as pd

        t = pd.read_csv(a.fields_file)
        if "r" in t and not (t.r.astype(float) == RADIUS_ARCMIN).all():
            p.error(f"every field of {a.fields_file} must have radius {RADIUS_ARCMIN}'")
        FIELDS.clear()
        FIELDS.update({r.name: (float(r.ra), float(r.dec)) for r in t.itertuples()})
    results = []
    for name in (a.fields.split(",") if a.fields else list(FIELDS)):
        results.append(collect_field(name.strip(), a.out, a.workers, a.retries))
        print(json.dumps(results[-1]), flush=True)
    (a.out / "collection_state.json").write_text(json.dumps(results, indent=1))
    copy = [r["field"] for r in results if r["gaia_source"] == "vizier_fallback"]
    if a.require_gaia_tap and copy:
        print(f"Gaia came from the VizieR copy in {copy}: not a baseline collection (ESA archive down?)", flush=True)
        return 2
    return 1 if any(r["key_failed"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

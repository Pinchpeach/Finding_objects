"""Run every v2 catalog collector independently for one sky position."""

from __future__ import annotations

import argparse
import importlib
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GET_DATA = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "rawdata"
# Collectors import shared helpers such as ``_catalog_utils`` by bare name;
# make that work when this module is imported from elsewhere.
for _p in (GET_DATA, GET_DATA.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from common import load_module  # noqa: E402

COLLECTORS = [
    "gaia_dr3",
    "gaia_dr3_variability_sos_vizier",
    "sdss_dr18",
    "panstarrs1",
    "desi_legacy",
    "galex",
    "twomass",
    "allwise",
    "lotss",
    "first",
    "nvss",
    "vlass",
    "xmm",
    "chandra",
    "erosita",
    "sdss_spectroscopy",
    "desi_spectroscopy",
    "lamost_spectroscopy",
    "atnf_pulsar",
    "agb_suh2021",
    "sga2020",
    "simbad",
    "ned",
]


def _load_collector(name: str):
    module = load_module(GET_DATA / f"{name}.py", f"v2_collector_{name}")
    if not callable(getattr(module, "fetch", None)):
        raise AttributeError(f"{name} has no callable fetch()")
    if not callable(getattr(module, "save", None)):
        raise AttributeError(f"{name} has no callable save()")
    return module


def _tag(ra: float, dec: float, radius_arcmin: float) -> str:
    def clean(value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".").replace("-", "m").replace(".", "p")

    return f"ra{clean(ra)}_dec{clean(dec)}_r{clean(radius_arcmin)}arcmin"


# Wall-time budget per archive.  Several services (TAP in particular) can
# hang without a socket timeout; one stuck archive must not stall the run.
COLLECTOR_BUDGET_S = 300.0


def _collect_one(
    name: str, ra: float, dec: float, radius_arcmin: float, out_dir: Path, tag: str, cancelled=None
) -> dict:
    started = time.monotonic()
    output = out_dir / f"{name}_{tag}.csv"
    try:
        module = _load_collector(name)
        df = module.fetch(ra, dec, radius_arcmin)
        if df is None:
            df = pd.DataFrame()
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        if cancelled is not None and cancelled.is_set():
            raise TimeoutError(f"{name} finished after the {COLLECTOR_BUDGET_S:.0f} s budget; result discarded")

        module.save(df, output)
        if not output.exists():
            raise RuntimeError(f"{name}.save() returned without writing {output}")
        status = "ok" if len(df) else "empty"
        error = ""
        rows = len(df)
        output_file = str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output)
    except TimeoutError as exc:
        status, rows, output_file, error = "timeout", 0, "", repr(exc)
        traceback.print_exc()
    except Exception as exc:
        # Network libraries often wrap timeouts in package-specific exceptions.
        message = repr(exc)
        status = "timeout" if "timeout" in message.lower() or "timed out" in message.lower() else "error"
        rows, output_file, error = 0, "", message
        traceback.print_exc()
    result = {
        "collector": name,
        "status": status,
        "rows": rows,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "output_file": output_file,
        "error": error,
    }
    print(f"[{name}] {status}: {rows} rows ({result['elapsed_seconds']} s)", flush=True)
    return result


# Imported once in the main thread before parallel collection: concurrent
# first imports of astropy/astroquery fail ("partially initialized module").
_SHARED_IMPORTS = (
    "astropy",
    "astropy.units",
    "astropy.coordinates",
    "astropy.table",
    "requests",
    "pyvo",
    "astroquery.vizier",
    "astroquery.gaia",
    "astroquery.sdss",
    "astroquery.simbad",
    "astroquery.ipac.ned",
    "astroquery.heasarc",
    "astroquery.xmatch",
)


def _preload() -> None:
    for name in _SHARED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:  # a missing optional package only affects its collector
            print(f"[preload] {name}: {exc!r}", flush=True)
    for name in COLLECTORS:
        try:
            _load_collector(name)
        except Exception as exc:
            print(f"[preload] collector {name}: {exc!r}", flush=True)


def _run_bounded(job, names, workers: int, budget_s: float) -> list[dict]:
    """Run ``job(name, cancelled_event)`` for each name on at most ``workers``
    daemon threads; a job over ``budget_s`` is reported as a timeout and its
    slot reused (the thread cannot be killed, but its late result is dropped)."""
    import threading

    results: dict[str, dict] = {}
    pending = list(names)
    running: dict[str, tuple[threading.Thread, float, threading.Event]] = {}

    def target(name, event):
        out = job(name, event)
        results.setdefault(name, out)  # a late result never replaces the timeout record

    while pending or running:
        while pending and len(running) < max(1, workers):
            name = pending.pop(0)
            event = threading.Event()
            thread = threading.Thread(target=target, args=(name, event), daemon=True)
            running[name] = (thread, time.monotonic(), event)
            thread.start()
        now = time.monotonic()
        for name, (thread, t0, event) in list(running.items()):
            if not thread.is_alive():
                del running[name]
            elif now - t0 > budget_s:
                event.set()
                del running[name]
                results[name] = {
                    "collector": name,
                    "status": "timeout",
                    "rows": 0,
                    "elapsed_seconds": round(now - t0, 3),
                    "output_file": "",
                    "error": f"exceeded {budget_s:.0f} s collector budget",
                }
                print(f"[{name}] timeout: abandoned after {budget_s:.0f} s", flush=True)
        if running:
            time.sleep(0.2)
    return [results[n] for n in names]


def collect_all(
    ra: float,
    dec: float,
    radius_arcmin: float,
    out_dir: Path = DEFAULT_OUT,
    workers: int = 1,
    budget_s: float = COLLECTOR_BUDGET_S,
) -> pd.DataFrame:
    """Run every collector; ``workers`` > 1 queries archives concurrently.

    Collection is network-bound and the collectors mostly hit different
    services, so concurrent queries cut wall time; each collector still
    fails independently and the summary keeps COLLECTORS order.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = _tag(ra, dec, radius_arcmin)
    started = time.monotonic()
    if workers > 1:
        _preload()
    results = _run_bounded(
        lambda n, c: _collect_one(n, ra, dec, radius_arcmin, out_dir, tag, c), COLLECTORS, workers, budget_s
    )

    summary = pd.DataFrame(results)
    summary_path = out_dir / f"collection_summary_{tag}.csv"
    summary.to_csv(summary_path, index=False)
    print(
        f"Completed: {len(summary)}/{len(COLLECTORS)} collectors attempted in "
        f"{time.monotonic() - started:.1f} s (workers={workers})",
        flush=True,
    )
    print(f"Summary: {summary_path}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ra", type=float, required=True, help="ICRS RA in degrees")
    parser.add_argument("--dec", type=float, required=True, help="ICRS Dec in degrees")
    parser.add_argument("--radius", type=float, required=True, help="Cone radius in arcminutes")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=6, help="concurrent archive queries")
    args = parser.parse_args()
    if args.radius <= 0:
        parser.error("--radius must be > 0")
    collect_all(args.ra, args.dec, args.radius, args.out_dir, max(1, args.workers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

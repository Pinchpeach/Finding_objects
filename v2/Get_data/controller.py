"""Run every v2 catalog collector independently for one sky position."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
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
if str(GET_DATA) not in sys.path:
    sys.path.insert(0, str(GET_DATA))
import archive_cache  # noqa: E402  (local cache / mirror of collector results, 2.9.1)
import footprint  # noqa: E402  (documented survey edges, 2.54.0)
import throttle  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

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
    "tgss",
    "vlass",
    "xmm",
    "chandra",
    "erosita",
    "mystix_mpcm",
    "sdss_spectroscopy",
    "desi_spectroscopy",
    "desi_fastspec",
    "lamost_spectroscopy",
    "ztf_periodic",
    "atnf_pulsar",
    "bzcat",
    "agb_suh2021",
    "sga2020",
    "galaxy_zoo_desi",
    "galaxy_clusters",
    "simbad",
    "ned",
]


_MODULES: dict[str, tuple[tuple, object]] = {}


def _load_collector(name: str):
    """Collector module, executed once per file version (2.19.0: was on every
    call, and _preload() re-ran all 26 on every collect_all)."""
    path = GET_DATA / f"{name}.py"
    st = path.stat()
    key = (st.st_mtime_ns, st.st_size)
    hit = _MODULES.get(name)
    if hit is not None and hit[0] == key:
        return hit[1]
    module = _exec_collector(name, path)
    _MODULES[name] = (key, module)
    return module


def _exec_collector(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"v2_collector_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load collector: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
# A collector may set a shorter ``BUDGET_S`` (2.55.0).
COLLECTOR_BUDGET_S = 300.0
# The archives the classification rests on (archive_health.py, the locked-set
# gate): never skipped for a recent failure, since a re-run right after an
# outage is how a user recovers them (archive_cache.recent_failure).
CORE = ("gaia_dr3", "desi_legacy", "panstarrs1", "allwise", "twomass")
# A core collector that failed a moment ago is asked again; one that declares
# RETRY_BUDGET_S is then waited for only that long.  Only collectors without an
# internal fallback declare it: Gaia (ESA TAP, then VizieR) and Pan-STARRS1
# (MAST, then VizieR) need their full budget to reach the fallback (PR #71
# review).  Legacy Surveys: with the Data Lab TAP down (2026-11-17) its three
# 80 s attempts made every re-run wait 246-300 s, while a healthy LS cone
# takes 5-16 s, so one attempt (90 s) still catches a recovery.


def _budget(name: str, default: float) -> float:
    try:
        b = min(default, float(getattr(_load_collector(name), "BUDGET_S", default)))
    except Exception:
        b = default
    if name in CORE and archive_cache.recent_failure(name):
        try:
            retry = getattr(_load_collector(name), "RETRY_BUDGET_S", None)
        except Exception:
            retry = None
        if retry is not None:
            b = min(b, float(retry))
    return b


def _collect_one(
    name: str, ra: float, dec: float, radius_arcmin: float, out_dir: Path, tag: str, cancelled=None
) -> dict:
    started = time.monotonic()
    output = out_dir / f"{name}_{tag}.csv"
    cache = "off"
    try:
        module = _load_collector(name)
        if footprint.outside(getattr(module, "FOOTPRINT", None), ra, dec, radius_arcmin):
            # The whole cone is outside the survey's documented sky: no request
            # (2.54.0).  Not a failure (catalog_coverage counts error / timeout).
            result = {
                "collector": name,
                "status": "outside_footprint",
                "rows": 0,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "output_file": "",
                "error": "",
                "cache": "off",
            }
            print(f"[{name}] outside_footprint: not queried", flush=True)
            return result
        source = GET_DATA / f"{name}.py"
        df = archive_cache.get(
            name, source, ra, dec, radius_arcmin, float(getattr(module, "CACHE_FILTER_MARGIN_ARCMIN", 0.0))
        )
        prev = None if (df is not None or name in CORE) else archive_cache.recent_failure(name, ra, dec, radius_arcmin)
        if prev:
            # Failed a moment ago: not asked again until the memory expires (2.55.0).
            age = time.time() - float(prev.get("t", 0))
            result = {
                "collector": name,
                "status": "error",
                "rows": 0,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "output_file": "",
                "error": f"skipped: {prev.get('status')} {age:.0f} s ago, asked again after "
                f"{archive_cache.failure_memory_s():.0f} s ({str(prev.get('error', ''))[:160]})",
                "cache": "recent_failure",
            }
            print(f"[{name}] error: skipped, failed {age:.0f} s ago", flush=True)
            return result
        if df is not None:
            cache = "hit"
        else:
            cache = "miss" if archive_cache.enabled() else "off"
            df = module.fetch(ra, dec, radius_arcmin)
            if df is None:
                df = pd.DataFrame()
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)
            if not (cancelled is not None and cancelled.is_set()):
                archive_cache.put(name, source, ra, dec, radius_arcmin, df)
        if cancelled is not None and cancelled.is_set():
            raise TimeoutError(f"{name} finished after its collector budget; result discarded")

        # Written under a temporary name and renamed only if the budget has not
        # run out meanwhile: Stage 1 reads every *.csv in the folder, so a file
        # finished after the timeout would be used although reported as a
        # timeout (2.23.0).
        part = output.with_name(output.name + ".part")
        module.save(df, part)
        if not part.exists():
            raise RuntimeError(f"{name}.save() returned without writing {part}")
        if cancelled is not None and cancelled.is_set():
            part.unlink(missing_ok=True)
            raise TimeoutError(f"{name} finished after its collector budget; result discarded")
        os.replace(part, output)
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
        "cache": cache,
    }
    print(f"[{name}] {status}: {rows} rows ({result['elapsed_seconds']} s, cache {cache})", flush=True)
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


def _disable_astroquery_cache() -> None:
    """astroquery keeps its own on-disk response cache (~/.astropy/cache) that
    is never pruned and duplicates archive_cache; turn it off (2.19.0)."""
    try:
        from astroquery import cache_conf

        cache_conf.cache_active = False
    except Exception:
        pass


def _run_bounded(job, names, workers: int, budget_s: float | dict) -> list[dict]:
    """Run ``job(name, cancelled_event)`` for each name on at most ``workers``
    daemon threads; a job over ``budget_s`` (seconds, or per name) is reported as a timeout and its
    slot reused (the thread cannot be killed, but its late result is dropped)."""
    import threading

    limit = (lambda n: budget_s.get(n, COLLECTOR_BUDGET_S)) if isinstance(budget_s, dict) else (lambda n: budget_s)
    results: dict[str, dict] = {}
    lock = threading.Lock()  # the job's result and the timeout record never both win
    pending = list(names)
    running: dict[str, tuple[threading.Thread, float, threading.Event]] = {}

    def target(name, event):
        out = job(name, event)
        with lock:
            if not event.is_set():  # a late result never replaces the timeout record
                results[name] = out

    while pending or running:
        while pending and len(running) < max(1, workers):
            name = pending.pop(0)
            event = threading.Event()
            # named after the collector: throttle's V2_HTTP_LOG lines carry it (2.54.0)
            thread = threading.Thread(target=target, args=(name, event), name=name, daemon=True)
            running[name] = (thread, time.monotonic(), event)
            thread.start()
        now = time.monotonic()
        for name, (thread, t0, event) in list(running.items()):
            with lock:
                done = name in results
                if not done and thread.is_alive() and now - t0 > limit(name):
                    event.set()
            if done or not thread.is_alive():
                del running[name]
            elif event.is_set():
                del running[name]
                results[name] = {
                    "collector": name,
                    "status": "timeout",
                    "rows": 0,
                    "elapsed_seconds": round(now - t0, 3),
                    "output_file": "",
                    "error": f"exceeded {limit(name):.0f} s collector budget",
                    "cache": "off",
                }
                print(f"[{name}] timeout: abandoned after {limit(name):.0f} s", flush=True)
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
    _disable_astroquery_cache()
    pruned = archive_cache.prune({n: GET_DATA / f"{n}.py" for n in COLLECTORS})
    if any(pruned.values()):
        print(f"[cache] pruned {pruned}", flush=True)
    if workers > 1:
        _preload()
    budgets = {n: _budget(n, budget_s) for n in COLLECTORS}
    results = _run_bounded(
        lambda n, c: _collect_one(n, ra, dec, radius_arcmin, out_dir, tag, c), COLLECTORS, workers, budgets
    )
    for r in results:  # remember failures of this search, forget recovered services (2.55.0)
        if r.get("cache") != "recent_failure" and r["status"] != "outside_footprint":
            archive_cache.note_outcome(
                r["collector"], r["status"], r.get("error", ""), ra, dec, radius_arcmin, r.get("elapsed_seconds")
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

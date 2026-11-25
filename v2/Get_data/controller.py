"""Run every v2 catalog collector independently for one sky position."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
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


# What a blind run drops anyway (spectroscopic and literature compilations: the workflows' blind copy removes these
# files, ``benchmark/collect_deep_cosmos.NOT_BLIND`` lists the same names).  A workflow that only scores the blind
# run has no use for their answers; asking for them costs requests, and NED's guidelines ask for no concurrent
# automated queries, which a matrix of parallel jobs makes (2.60.6).
BLIND_DROPPED = (
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


def skipped_collectors(value: str | None = None) -> set[str]:
    """Collectors ``V2_SKIP_COLLECTORS`` asks not to run: a comma list of names, ``blind`` for ``BLIND_DROPPED``.

    A name that is no collector (nor ``blind``) is an error: a typo must not leave NED switched on in a workflow
    that meant to switch it off.  Names in BLIND_DROPPED that are not collectors of this version are fine."""
    raw = os.environ.get("V2_SKIP_COLLECTORS", "") if value is None else value
    out: set[str] = set()
    for tok in (t.strip() for t in raw.split(",")):
        if not tok:
            continue
        if tok == "blind":
            out.update(BLIND_DROPPED)
        elif tok in COLLECTORS:
            out.add(tok)
        else:
            raise ValueError(
                f"V2_SKIP_COLLECTORS: {tok!r} is not a collector (known: {', '.join(COLLECTORS)}, or 'blind')"
            )
    return out


def collectors_to_run() -> list[str]:
    skip = skipped_collectors()
    run = [n for n in COLLECTORS if n not in skip]
    if len(run) != len(COLLECTORS):
        print(f"[collect] V2_SKIP_COLLECTORS: not asking {', '.join(n for n in COLLECTORS if n in skip)}", flush=True)
    return run


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
# takes 5-16 s, so one attempt (90 s) still catches a recovery.  2.57.0: its
# second path (the viewer catalogue, desi_legacy.py) is asked after 30 s and
# answers in 5-15 s, so it fits inside the 90 s as well.


def _budget(name: str, default: float, retry: bool = False) -> float:
    """Wall-time budget of one collector.  ``retry``: the user asked for this
    collector again after it failed (2.57.0), which counts as a recent failure
    whatever the failure memory says (it expires after 10 min)."""
    try:
        b = min(default, float(getattr(_load_collector(name), "BUDGET_S", default)))
    except Exception:
        b = default
    if retry or (name in CORE and archive_cache.recent_failure(name)):
        try:
            retry = getattr(_load_collector(name), "RETRY_BUDGET_S", None)
        except Exception:
            retry = None
        if retry is not None:
            b = min(b, float(retry))
    return b


def _collect_one(
    name: str, ra: float, dec: float, radius_arcmin: float, out_dir: Path, tag: str, cancelled=None, retry: bool = False
) -> dict:
    """Collect one archive.  ``retry``: asked for again by the user after a
    failure (2.57.0), so a remembered recent failure does not skip it."""
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
        if retry and df is not None and archive_cache.fallback(df):
            df = None  # asked again to get the primary source: not the alternative source's cached copy (2.57.0)
        prev = (
            None
            if (df is not None or name in CORE or retry)
            else archive_cache.recent_failure(name, ra, dec, radius_arcmin)
        )
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
    write_search(out_dir, ra, dec, radius_arcmin)
    _disable_astroquery_cache()
    pruned = archive_cache.prune({n: GET_DATA / f"{n}.py" for n in COLLECTORS})
    if any(pruned.values()):
        print(f"[cache] pruned {pruned}", flush=True)
    if workers > 1:
        _preload()
    names = collectors_to_run()
    budgets = {n: _budget(n, budget_s) for n in names}
    results = _run_bounded(
        lambda n, c: _collect_one(n, ra, dec, radius_arcmin, out_dir, tag, c), names, workers, budgets
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
        f"Completed: {len(summary)}/{len(names)} collectors attempted in "
        f"{time.monotonic() - started:.1f} s (workers={workers})",
        flush=True,
    )
    print(f"Summary: {summary_path}", flush=True)
    return summary


SEARCH_FILE = "search.json"
FAILED = ("error", "timeout")


def write_search(out_dir: Path, ra: float, dec: float, radius_arcmin: float) -> None:
    """Record the exact search cone next to the raw files (2.57.0).

    The folder tag rounds to 6 decimals, and the archive cache treats a cone as
    "the same" only to 1e-6 arcmin: a cone parsed back from the tag would miss
    the cache of every archive that already answered, and ``retry_failed``
    would ask them all again."""
    try:
        (Path(out_dir) / SEARCH_FILE).write_text(
            json.dumps({"ra": float(ra), "dec": float(dec), "radius_arcmin": float(radius_arcmin)}),
            encoding="utf-8",
        )
    except OSError:
        pass  # only the retry path needs it, and it then asks for the position


def read_search(raw_dir: Path) -> tuple[float, float, float] | None:
    """(ra, dec, radius_arcmin) of the collection in ``raw_dir``, or None."""
    try:
        d = json.loads((Path(raw_dir) / SEARCH_FILE).read_text(encoding="utf-8"))
        return float(d["ra"]), float(d["dec"]), float(d["radius_arcmin"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def last_collection(work: Path) -> Path | None:
    """Raw folder of the newest collection in ``work/raw`` (has a collection summary)."""
    try:
        folders = [d for d in (Path(work) / "raw").iterdir() if d.is_dir() and any(d.glob("collection_summary_*.csv"))]
    except OSError:
        return None
    return max(folders, key=lambda d: max(f.stat().st_mtime for f in d.glob("collection_summary_*.csv")), default=None)


def _coverage_module():
    spec = importlib.util.spec_from_file_location("v2_catalog_coverage_ctrl", ROOT / "catalog_coverage.py")
    cov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cov)
    return cov


def failed_collectors(raw_dir: Path, which: str = "key") -> list[str]:
    """Collectors of the collection in ``raw_dir`` worth asking again: those that failed
    (error / timeout) and those that answered from a reduced alternative source
    (catalog_coverage.ALTERNATIVE: Gaia from the VizieR copy while the ESA archive is down).
    ``which`` = "key" the archives the classification rests on (catalog_coverage.IMPACT),
    "all" every one of them."""
    files = sorted(Path(raw_dir).glob("collection_summary_*.csv"))
    if not files:
        return []
    cov = _coverage_module().summarize(raw_dir)
    names = [f["collector"] for f in cov.get("failed", [])] + [a["collector"] for a in cov.get("alternative", [])]
    if which == "all":
        return names
    key = {f["collector"] for f in cov.get("failed", []) if f.get("key")} | {
        a["collector"] for a in cov.get("alternative", [])
    }
    return [n for n in names if n in key]


def retry_failed(
    raw_dir: Path,
    ra: float,
    dec: float,
    radius_arcmin: float,
    workers: int = 1,
    which: str = "key",
    budget_s: float = COLLECTOR_BUDGET_S,
) -> pd.DataFrame:
    """Ask again only the collectors of the last collection in ``raw_dir`` that
    failed or answered from a reduced alternative source, and replace their rows
    in its collection summary (2.57.0).

    A run on a bad archive day (2026-11-23: Legacy Surveys timed out at
    300 s in the first COSMOS search, 270 objects instead of 3,582) was
    recovered by running everything again; the archives that had answered are
    served by ``archive_cache`` and cost nothing, but the rest of the run was
    redone and the user had to know to do it.  Here nothing that succeeded is
    asked at all, and nothing is re-collected when nothing failed.

    A retry is an explicit request: the 10-minute failure memory
    (``archive_cache``) does not skip it, and a collector that declares
    ``RETRY_BUDGET_S`` gets only that long (a healthy service answers in a
    fraction of it; the budget exists so that a retry during an outage is not
    another 5-minute wait).  Returns the rows that were re-collected."""
    raw_dir = Path(raw_dir)
    names = failed_collectors(raw_dir, which)
    if not names:
        print("[retry] no failed archives to ask again", flush=True)
        return pd.DataFrame()
    tag = _tag(ra, dec, radius_arcmin)
    started = time.monotonic()
    _disable_astroquery_cache()
    if workers > 1:
        _preload()
    print(f"[retry] asking again: {', '.join(names)}", flush=True)
    budgets = {n: _budget(n, budget_s, retry=True) for n in names}
    results = _run_bounded(
        lambda n, c: _collect_one(n, ra, dec, radius_arcmin, raw_dir, tag, c, retry=True), names, workers, budgets
    )
    for r in results:
        archive_cache.note_outcome(
            r["collector"], r["status"], r.get("error", ""), ra, dec, radius_arcmin, r.get("elapsed_seconds")
        )
    new = pd.DataFrame(results)
    summary_path = sorted(raw_dir.glob("collection_summary_*.csv"))[-1]
    old = pd.read_csv(summary_path, keep_default_na=False)
    keep = old[~old.collector.isin(new.collector)]
    merged = pd.concat([keep, new], ignore_index=True)
    order = {n: i for i, n in enumerate(COLLECTORS)}  # the summary keeps COLLECTORS order
    merged = merged.sort_values("collector", key=lambda c: c.map(order).fillna(len(order)), kind="stable")
    merged.to_csv(summary_path, index=False)
    after = _coverage_module().summarize(raw_dir)
    still = [f["collector"] for f in after.get("failed", []) if f["collector"] in names]
    reduced = [a["collector"] for a in after.get("alternative", []) if a["collector"] in names]
    print(
        f"[retry] {len(names) - len(still) - len(reduced)}/{len(names)} recovered in {time.monotonic() - started:.1f} s"
        + (f"; still failing: {', '.join(still)}" if still else "")
        + (f"; still from the alternative source: {', '.join(reduced)}" if reduced else ""),
        flush=True,
    )
    return new


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

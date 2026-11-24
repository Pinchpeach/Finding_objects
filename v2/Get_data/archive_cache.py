"""Local archive cache / mirror for collector results (2.9.1; review fixes 2.10.0).

Each successful ``fetch(ra, dec, radius)`` result is stored as gzip CSV under
``V2_CACHE_DIR`` (default ``~/.cache/finding_objects/v2``).  A later request
is served from the cache when a stored cone of the same collector *contains*
it (centre separation + requested radius <= stored radius); the rows are then
filtered to the requested cone (plus the collector's own search margin,
``CACHE_FILTER_MARGIN_ARCMIN``, e.g. SGA-2020 searches 10' beyond the field)
and ``query_radius_arcmin`` is set to the requested radius, as a fresh fetch
would.  Re-running a field, or zooming into part of it, needs no network.

Correctness rules:
* the key hashes every collector module in ``Get_data`` (shared helpers such
  as ``_catalog_utils.py`` and ``gaia_release.py`` included) and the Gaia
  release, so changing collection code never reuses old rows;
* only complete successful fetches are stored: errors, timeouts and partial
  results (any ``*_query_status`` that is not ok, e.g. a failed optional
  query) are not; the complete answer of an alternative source (the Gaia
  VizieR fallback) is kept for FALLBACK_TTL_DAYS only (2.54.0);
* empty results expire after ``EMPTY_TTL_DAYS`` (an archive outage can look
  like an empty answer), non-empty ones after ``TTL_DAYS`` (the archives
  here are fixed releases except SIMBAD / NED, which get ``LIVE_TTL_DAYS``);
* several processes (app worker, command line) may share the directory: data
  files are written to a unique temporary name and renamed, and the index is
  updated under a lock file;
* ``V2_CACHE=0`` disables the cache; ``prune()`` bounds its size on disk
  (``V2_CACHE_MAX_MB``, default 2048) and drops superseded code-hash folders.
"""

from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

TTL_DAYS = 90.0
LIVE_TTL_DAYS = 7.0
EMPTY_TTL_DAYS = 1.0
LIVE = {"simbad", "ned"}
OK_STATUS = {"", "ok", "tap", "missing_source_id", "nan", "<NA>", "None"}
# A complete answer from a collector's documented alternative source (Gaia DR3
# from its VizieR copy when the ESA TAP misses its budget) lacks a few
# columns only that source has (gaia_dr3.py).  2.54.0: kept FALLBACK_TTL_DAYS,
# so a re-run of the search does not repeat the ~60 s fallback, while the
# next day tries the primary source again (it was not cached at all: in the
# practical-use probe every warm re-run spent 56-60 s on Gaia).
# 2.57.0: "viewer_fallback" = the Legacy Surveys rows from the viewer catalogue
# when the Data Lab TAP did not answer (desi_legacy.py); same rows, kept a day.
FALLBACK_STATUS = {"vizier_fallback", "fallback_partial", "fallback_unavailable", "viewer_fallback"}
FALLBACK_TTL_DAYS = 1.0
SAME_TOL_ARCMIN = 1e-6
LOCK_STALE_S = 30.0
_LOCK = threading.Lock()
_HASH: dict[tuple, str] = {}


def enabled() -> bool:
    return os.environ.get("V2_CACHE", "1").strip() not in {"0", "false", "no", "off"}


def root() -> Path:
    return Path(os.environ.get("V2_CACHE_DIR", Path.home() / ".cache" / "finding_objects" / "v2"))


def _code_hash(source: Path) -> str:
    """Hash of every module in the collector's folder plus the Gaia release."""
    folder = Path(source).resolve().parent
    files = sorted(folder.glob("*.py"))
    sig = (str(folder), tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files))
    if sig not in _HASH:
        h = hashlib.sha1()
        for f in files:
            h.update(f.name.encode())
            h.update(f.read_bytes())
        _HASH[sig] = h.hexdigest()[:12]
    return _HASH[sig] + "-" + os.environ.get("V2_GAIA_RELEASE", "DR3").strip().upper()


def _sep_arcmin(ra1, dec1, ra2, dec2):
    """Haversine separation (exact 0 for identical points, stable at small angles)."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    a = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a)))) * 60.0


def _dir(name: str, source: Path) -> Path:
    return root() / name / _code_hash(source)


def _index(d: Path) -> list[dict]:
    try:
        return json.loads((d / "index.json").read_text())
    except Exception:
        return []


def _ttl(name: str, rows: int, fallback: bool = False) -> float:
    if rows == 0:
        return EMPTY_TTL_DAYS
    if fallback:
        return FALLBACK_TTL_DAYS
    return LIVE_TTL_DAYS if name in LIVE else TTL_DAYS


def _statuses(df: pd.DataFrame) -> set:
    out = set()
    for c in df.columns:
        if str(c).endswith("_query_status"):
            out |= set(df[c].astype(str).str.strip())
    return out


# Status columns that only a collector's alternative source writes (panstarrs1.py: the MAST path has no
# ps1_query_status).  An empty answer with such a column came from the alternative source (PR #73 review):
# an explicit retry (controller._collect_one(retry=True)) then asks the primary source instead of serving it
# from the cache.  Its cache time is one day either way (EMPTY_TTL_DAYS = FALLBACK_TTL_DAYS).
HEADER_ONLY_FALLBACK = frozenset({"ps1_query_status"})


def fallback(df: pd.DataFrame) -> bool:
    """True when the rows came from a collector's alternative source."""
    if df.empty and HEADER_ONLY_FALLBACK & {str(c) for c in df.columns}:
        return True
    return bool(_statuses(df) & FALLBACK_STATUS)


# Recent failures (2.55.0).  A collector whose service failed is retried by
# every new search; with NED and the HEASARC ATNF table failing (2.54.0 re-evaluation) a
# re-run of a cached 2' COSMOS search still took 111 s, all of it waiting on
# the two failing services.  controller.py skips a non-core collector that
# failed less than FAILURE_MEMORY_S ago (V2_FAILURE_MEMORY_S, 0 = off) and
# reports it as an error, so the missing-archive warning still shows it.
#
# Scope of a remembered failure (2.56.0).  2.55.0 remembered the collector
# name only, so one SDSS answer that could not be parsed at NGC 4522 switched
# SDSS spectroscopy off for the COSMOS and Galactic-plane searches that
# followed (2.55.0 evaluation).  A failure now stops
#   * the same cone, always (the re-run 2.55.0 was written for);
#   * every other cone only if it was a "timeout" (the service did not answer
#     inside its budget: the wait 2.55.0 removed, 60-300 s per search) or took
#     SLOW_FAILURE_S or more to fail (review), or if
#     the collector failed at two different cones inside the memory (an outage
#     that answers quickly with an error page).
# A quick "error" at one cone costs the next cone one more quick request, not
# a wait.  Any success of the collector forgets its failures.
FAILURE_MEMORY_S = 600.0
SAME_CONE_DEG = 1e-4  # 0.36": the same search, not a neighbouring one
# A failure that took this long is a wait like a timeout, and is applied to
# every cone too (2.56.0 review): e.g. the HEASARC TAP answered "System
# overloaded" only after 66 s, and SkyServer error pages retried five times
# take ~30 s; a quick parse error (< SLOW_FAILURE_S) still costs the next cone
# only one request.
SLOW_FAILURE_S = 30.0


def failure_memory_s() -> float:
    try:
        return max(0.0, float(os.environ.get("V2_FAILURE_MEMORY_S", FAILURE_MEMORY_S)))
    except ValueError:
        return FAILURE_MEMORY_S


def _failures_path() -> Path:
    return root() / "failures.json"


def _read_failures() -> dict:
    """{collector: [failure, ...]}; a 2.55.0 file ({collector: failure}) is read as service-wide."""
    try:
        d = json.loads(_failures_path().read_text())
    except Exception:
        return {}
    return {k: (v if isinstance(v, list) else [v]) for k, v in d.items() if isinstance(v, (list, dict))}


def _write_failures(d: dict) -> None:
    path = _failures_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(d, fh)
    os.replace(tmp, path)


def _cone(ra, dec, radius_arcmin):
    return None if ra is None or dec is None else (float(ra), float(dec), float(radius_arcmin or 0.0))


def _same_cone(e: dict, cone) -> bool:
    if cone is None or e.get("ra") is None:
        return False
    dra = abs((float(e["ra"]) - cone[0] + 180.0) % 360.0 - 180.0) * math.cos(math.radians(cone[1]))
    return (
        dra < SAME_CONE_DEG
        and abs(float(e["dec"]) - cone[1]) < SAME_CONE_DEG
        and abs(float(e.get("radius", 0.0)) - cone[2]) < 1e-3
    )


def _recent(entries: list) -> list:
    now = time.time()
    return [e for e in entries if now - float(e.get("t", 0)) <= failure_memory_s()]


def recent_failure(name: str, ra: float | None = None, dec: float | None = None, radius_arcmin: float | None = None):
    """The remembered failure of ``name`` that applies to this cone, else None.

    Without a position: the last failure of the collector at any cone.
    """
    if not enabled() or failure_memory_s() <= 0:
        return None
    entries = sorted(_recent(_read_failures().get(name, [])), key=lambda e: float(e.get("t", 0)))
    if not entries:
        return None
    cone = _cone(ra, dec, radius_arcmin)
    if cone is None:
        return entries[-1]
    same = [e for e in entries if _same_cone(e, cone)]
    if same:
        return same[-1]
    wide = [
        e
        for e in entries
        if e.get("status") == "timeout" or e.get("ra") is None or float(e.get("seconds", 0.0)) >= SLOW_FAILURE_S
    ]
    if wide:
        return wide[-1]
    return entries[-1] if len(entries) >= 2 else None  # one entry per cone (note_outcome)


def note_outcome(
    name: str,
    status: str,
    error: str = "",
    ra: float | None = None,
    dec: float | None = None,
    radius_arcmin: float | None = None,
    seconds: float | None = None,
) -> None:
    """Remember a failure (error / timeout) or forget the collector's failures after a success."""
    if not enabled() or failure_memory_s() <= 0:
        return
    try:
        root().mkdir(parents=True, exist_ok=True)
        with _LOCK, _FileLock(root() / "failures.lock"):
            d = {k: _recent(v) for k, v in _read_failures().items()}
            if status in ("error", "timeout"):
                cone = _cone(ra, dec, radius_arcmin)
                e = {"t": time.time(), "status": status, "error": str(error)[:300]}
                if seconds is not None:
                    e["seconds"] = float(seconds)
                if cone is not None:
                    e.update(ra=cone[0], dec=cone[1], radius=cone[2])
                d[name] = [x for x in d.get(name, []) if not _same_cone(x, cone)] + [e]
            else:
                d.pop(name, None)
            _write_failures({k: v for k, v in d.items() if v})
    except Exception as exc:  # never fail a collection over this
        print(f"[cache] failure memory not updated ({exc!r})", flush=True)


# Servers that failed (2.60.0).  A collector with two equivalent servers (SIMBAD: CDS Strasbourg and its
# Harvard-CfA mirror) asks the second when the first fails.  That failure was forgotten when the process ended,
# so every search paid for the failing server again: Strasbourg has answered 404 to every SIMBAD request since
# 2026-11-15, two requests and ~8 s of the 3-5 s pauses per search.  ``note_source(key, ok)`` remembers a failed
# server for the failure memory (V2_FAILURE_MEMORY_S, 600 s; 0 or V2_CACHE=0 = off) and any answer of it forgets
# the failure; ``source_down(key)`` tells the collector to ask that server last (never to skip it).
def _sources_path() -> Path:
    return root() / "sources.json"


def _read_sources() -> dict:
    try:
        d = json.loads(_sources_path().read_text())
    except Exception:
        return {}
    now = time.time()
    return {k: float(t) for k, t in d.items() if isinstance(t, (int, float)) and now - float(t) <= failure_memory_s()}


def down_keys() -> set:
    """Every server key remembered as failed (one read of the file)."""
    if not enabled() or failure_memory_s() <= 0:
        return set()
    return set(_read_sources())


def source_down(key: str) -> bool:
    """True when ``key`` (e.g. ``simbad:simbad.cds.unistra.fr``) failed less than the failure memory ago."""
    if not enabled() or failure_memory_s() <= 0:
        return False
    return key in _read_sources()


def note_source(key: str, ok: bool) -> None:
    """Remember that ``key`` failed (``ok`` False) or forget its failure (``ok`` True)."""
    if not enabled() or failure_memory_s() <= 0:
        return
    try:
        known = _read_sources()
        if ok and key not in known:
            return  # nothing to forget: no file access on the normal path
        root().mkdir(parents=True, exist_ok=True)
        with _LOCK, _FileLock(root() / "sources.lock"):
            d = _read_sources()
            if ok:
                d.pop(key, None)
            else:
                d[key] = time.time()
            path = _sources_path()
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(d, fh)
            os.replace(tmp, path)
    except Exception as exc:  # never fail a collection over this
        print(f"[cache] source memory not updated ({exc!r})", flush=True)


def cacheable(df: pd.DataFrame) -> bool:
    """False for partial results (a ``*_query_status`` column reporting a
    failure); an alternative source's complete answer is cacheable (briefly)."""
    return not (_statuses(df) - OK_STATUS - FALLBACK_STATUS)


def get(
    name: str, source: Path, ra: float, dec: float, radius_arcmin: float, margin_arcmin: float = 0.0
) -> pd.DataFrame | None:
    """Rows inside the requested cone from a containing cached cone, or None."""
    if not enabled():
        return None
    d = _dir(name, source)
    now = time.time()
    candidates = [
        e
        for e in _index(d)
        if now - e["t"] <= _ttl(name, e["rows"], e.get("fallback", False)) * 86400
        and _sep_arcmin(ra, dec, e["ra"], e["dec"]) + radius_arcmin <= e["r"] + SAME_TOL_ARCMIN
    ]
    # Smallest containing cone first; one whose file was pruned or is
    # unreadable falls through to the next instead of forcing a re-fetch (2.23.0).
    df = best = None
    for e in sorted(candidates, key=lambda e: e["r"]):
        try:
            # Text in, text out: 64-bit IDs (SDSS specObjID, DESI TARGETID) must
            # not pass through float; the collector's save() writes them back as read.
            df = pd.read_csv(d / e["file"], dtype=str, keep_default_na=False, na_filter=False)
            best = e
            break
        except Exception:
            continue
    if best is None:
        return None
    same_cone = (
        abs(best["r"] - radius_arcmin) < SAME_TOL_ARCMIN
        and _sep_arcmin(ra, dec, best["ra"], best["dec"]) < SAME_TOL_ARCMIN
    )
    if df.empty or same_cone:
        return df
    r = np.radians(pd.to_numeric(df.get("ra"), errors="coerce").to_numpy(float))
    de = np.radians(pd.to_numeric(df.get("dec"), errors="coerce").to_numpy(float))
    r0, d0 = math.radians(ra), math.radians(dec)
    a = np.sin((de - d0) / 2) ** 2 + math.cos(d0) * np.cos(de) * np.sin((r - r0) / 2) ** 2
    sep = np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))) * 60.0  # NaN position -> NaN -> dropped
    out = df[sep <= radius_arcmin + margin_arcmin].reset_index(drop=True)
    for col in ("query_radius_arcmin", "cone_radius_arcmin"):
        if col in out.columns:
            out[col] = repr(float(radius_arcmin))  # as a fresh fetch of this cone would record
    return out


class _FileLock:
    """Cross-process lock via an exclusively created file (stale after LOCK_STALE_S)."""

    def __init__(self, path: Path, timeout: float = 10.0):
        self.path, self.timeout = path, timeout

    def __enter__(self):
        t0 = time.monotonic()
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_S:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() - t0 > self.timeout:
                    raise TimeoutError(f"cache lock busy: {self.path}")
                time.sleep(0.05)

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def put(name: str, source: Path, ra: float, dec: float, radius_arcmin: float, df: pd.DataFrame) -> None:
    if not enabled() or not cacheable(df):
        return
    d = _dir(name, source)
    tmp = itmp = None
    try:
        d.mkdir(parents=True, exist_ok=True)
        fname = hashlib.sha1(f"{ra:.7f},{dec:.7f},{radius_arcmin:.5f}".encode()).hexdigest()[:16] + ".csv.gz"
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        os.close(fd)
        # level 1: write 1.41 -> 0.67 s for 5,000 x 65
        df.to_csv(tmp, index=False, compression={"method": "gzip", "compresslevel": 1})
        with _LOCK, _FileLock(d / "index.lock"):
            # Data file, index and expiry under one lock (2.19.0): a writer
            # could otherwise delete a file another writer had just renamed.
            os.replace(tmp, d / fname)
            tmp = None
            now = time.time()
            keep, drop = [], []
            for e in _index(d):
                if e["file"] == fname:
                    continue
                (drop if now - e["t"] > _ttl(name, e["rows"], e.get("fallback", False)) * 86400 else keep).append(e)
            keep.append(
                {
                    "ra": float(ra),
                    "dec": float(dec),
                    "r": float(radius_arcmin),
                    "rows": int(len(df)),
                    "t": now,
                    "file": fname,
                    "fallback": fallback(df),
                }
            )
            fd, itmp = tempfile.mkstemp(dir=d, suffix=".json.tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(keep, fh)
            os.replace(itmp, d / "index.json")
            itmp = None
            live = {e["file"] for e in keep}
            for e in drop:  # expired entries: remove their files
                if e["file"] not in live:
                    (d / e["file"]).unlink(missing_ok=True)
    except Exception as exc:  # a cache problem must never fail a collection
        print(f"[cache] {name}: not stored ({exc!r})", flush=True)
    finally:
        for t in (tmp, itmp):
            if t:
                Path(t).unlink(missing_ok=True)


# Disk bound (2.19.0).  Every change to the collector code moves a collector
# to a new hash folder; the old folders were never visited again, and inside
# a folder only a put() removed expired entries.
MAX_CACHE_MB = float(os.environ.get("V2_CACHE_MAX_MB", "2048"))
TMP_STALE_S = 3600.0


def prune(sources: dict[str, Path] | None = None, max_mb: float | None = None) -> dict:
    """Remove superseded code-hash folders (when ``sources`` maps collector
    name -> module path), stale temporary files, and, above ``max_mb``, the
    oldest data files.  Never raises."""
    out = {"folders": 0, "tmp": 0, "evicted": 0}
    if not enabled():
        return out
    base = root()
    try:
        if not base.is_dir():
            return out
        now = time.time()
        if sources:
            for name, src in sources.items():
                folder = base / name
                if not folder.is_dir():
                    continue
                # Compare the code hash only: the "-<Gaia release>" suffix
                # keeps one folder per release, so switching V2_GAIA_RELEASE
                # must not delete the other release's cache.
                current = _code_hash(src).split("-")[0]
                for sub in folder.iterdir():
                    if sub.is_dir() and sub.name.split("-")[0] != current:
                        _rmtree(sub)
                        out["folders"] += 1
        files = []
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            st = f.stat()
            if f.suffix == ".tmp" and now - st.st_mtime > TMP_STALE_S:
                f.unlink(missing_ok=True)
                out["tmp"] += 1
            elif f.name.endswith(".csv.gz"):
                files.append((st.st_mtime, st.st_size, f))
        limit = (MAX_CACHE_MB if max_mb is None else max_mb) * 1e6
        total = sum(sz for _, sz, _ in files)
        for _, sz, f in sorted(files):
            if total <= limit:
                break
            f.unlink(missing_ok=True)  # get() of its index entry then misses and re-fetches
            total -= sz
            out["evicted"] += 1
    except Exception as exc:
        print(f"[cache] prune: {exc!r}", flush=True)
    return out


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)

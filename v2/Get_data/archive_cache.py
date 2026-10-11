"""Local archive cache / mirror for collector results (2.9.1).

Each successful ``fetch(ra, dec, radius)`` result is stored as gzip CSV under
``V2_CACHE_DIR`` (default ``~/.cache/finding_objects/v2``).  A later request
is served from the cache when a stored cone of the same collector *contains*
it (centre separation + requested radius <= stored radius); the rows are then
filtered to the requested cone.  Re-running a field, or zooming into part of
it, needs no network.

Correctness rules:
* the key includes a hash of the collector's source file and the Gaia
  release, so changing a collector (columns, filters) never reuses old rows;
* only successful fetches are stored; errors and timeouts never are;
* empty results expire after ``EMPTY_TTL_DAYS`` (an archive outage can look
  like an empty answer), non-empty ones after ``TTL_DAYS`` (the archives
  here are fixed releases except SIMBAD / NED, which get ``LIVE_TTL_DAYS``);
* ``V2_CACHE=0`` disables the cache.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import threading
import time
from pathlib import Path

import pandas as pd

TTL_DAYS = 90.0
LIVE_TTL_DAYS = 7.0
EMPTY_TTL_DAYS = 1.0
LIVE = {"simbad", "ned"}
_LOCK = threading.Lock()


def enabled() -> bool:
    return os.environ.get("V2_CACHE", "1").strip() not in {"0", "false", "no", "off"}


def root() -> Path:
    return Path(os.environ.get("V2_CACHE_DIR", Path.home() / ".cache" / "finding_objects" / "v2"))


def _code_hash(source: Path) -> str:
    h = hashlib.sha1(source.read_bytes())
    h.update(os.environ.get("V2_GAIA_RELEASE", "DR3").upper().encode())
    return h.hexdigest()[:12]


def _sep_arcmin(ra1, dec1, ra2, dec2):
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 60.0


def _dir(name: str, source: Path) -> Path:
    return root() / name / _code_hash(source)


def _index(d: Path) -> list[dict]:
    try:
        return json.loads((d / "index.json").read_text())
    except Exception:
        return []


def _ttl(name: str, rows: int) -> float:
    if rows == 0:
        return EMPTY_TTL_DAYS
    return LIVE_TTL_DAYS if name in LIVE else TTL_DAYS


def get(name: str, source: Path, ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame | None:
    """Rows inside the requested cone from a containing cached cone, or None."""
    if not enabled():
        return None
    d = _dir(name, source)
    now = time.time()
    best = None
    for e in _index(d):
        if now - e["t"] > _ttl(name, e["rows"]) * 86400:
            continue
        if _sep_arcmin(ra, dec, e["ra"], e["dec"]) + radius_arcmin <= e["r"] + 1e-9:
            if best is None or e["r"] < best["r"]:
                best = e
    if best is None:
        return None
    try:
        # Text in, text out: 64-bit IDs (SDSS specObjID, DESI TARGETID) must
        # not pass through float; the collector's save() writes them back as read.
        df = pd.read_csv(d / best["file"], dtype=str, keep_default_na=False, na_filter=False)
    except Exception:
        return None
    same_cone = abs(best["r"] - radius_arcmin) < 1e-9 and _sep_arcmin(ra, dec, best["ra"], best["dec"]) < 1e-6
    if df.empty or same_cone:
        return df
    r = pd.to_numeric(df.get("ra"), errors="coerce")
    de = pd.to_numeric(df.get("dec"), errors="coerce")
    sep = [(_sep_arcmin(ra, dec, a, b) if a == a and b == b else math.inf) for a, b in zip(r, de)]
    return df[pd.Series(sep, index=df.index) <= radius_arcmin].reset_index(drop=True)


def put(name: str, source: Path, ra: float, dec: float, radius_arcmin: float, df: pd.DataFrame) -> None:
    if not enabled():
        return
    d = _dir(name, source)
    try:
        d.mkdir(parents=True, exist_ok=True)
        fname = hashlib.sha1(f"{ra:.7f},{dec:.7f},{radius_arcmin:.5f}".encode()).hexdigest()[:16] + ".csv.gz"
        df.to_csv(d / fname, index=False, compression={"method": "gzip", "compresslevel": 1})   # level 1: write 1.41 -> 0.67 s for 5,000 x 65
        with _LOCK:
            idx = [e for e in _index(d) if e["file"] != fname]
            idx.append({"ra": float(ra), "dec": float(dec), "r": float(radius_arcmin), "rows": int(len(df)),
                        "t": time.time(), "file": fname})
            tmp = d / "index.json.tmp"
            tmp.write_text(json.dumps(idx))
            tmp.replace(d / "index.json")
    except Exception as exc:          # a cache problem must never fail a collection
        print(f"[cache] {name}: not stored ({exc!r})", flush=True)

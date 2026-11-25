"""Small fixed catalogue tables kept on the user's own computer, downloaded once on first use (2.60.7).

Why.  A cold search spends most of its time in the 3-5 s pause before each request (``throttle.py``).  The two
lists the collectors ask for that are small, fixed and almost always empty in a 2' cone -- the Suh (2021) AGB tables
(18,381 rows) and the Roma-BZCAT 5th edition (3,561 rows) -- cost 2-13 requests each (VizieR mirror hops, 8-110 s)
to learn "no row here".  Held locally, a cone search of them is a table lookup (milliseconds) and needs no request.

What it is *not*.  Nothing is added to the repository or to the app bundle: ``THIRD_PARTY_NOTICES.md`` keeps saying
the program ships no catalogue data.  The user's computer downloads the table from VizieR itself, once, into the
user's own cache folder (the same thing ``astroquery`` does with its disk cache, and what a person does who clicks
"download table"), and nobody else receives it.

Contract.
* ``cone(key, ra, dec, radius_arcmin)`` returns what ``_catalog_utils.vizier_query`` returns (an astroquery
  ``TableList`` of astropy tables, tables without rows left out, the ``_r`` distance column first), so a collector
  switches between the remote and the local answer without any other change; ``None`` means "ask VizieR".
* Whether a list is used at all (``V2_LOCAL_LISTS``): ``auto`` (default) uses only the lists whose terms of use have
  been verified from the original text (``ListSpec.terms_verified``); ``all`` also the unverified ones; ``0`` none.
  ``V2_CACHE=0`` ("no on-disk state", the cold measurements) switches the store off too.
* First use downloads every table of the list from VizieR in one request (through the mirror failover of
  ``throttle.py``), checks the row counts against the fixed edition (a mismatch is never stored), and writes the
  tables and a manifest (VizieR table ids, download date, rows, SHA-256 of each file) under
  ``$V2_CACHE_DIR/lists/<key>/``.  The progress goes to the log (``[lists] ...``).  A failed download falls back to
  the remote cone for this search and is not retried for ``RETRY_AFTER_S``.
* The copy is re-downloaded when it is older than ``max_age_days``, when a file does not match its manifest hash,
  or when the user asks: ``python v2/Get_data/local_lists.py refresh [key]`` (``status`` and ``remove`` too;
  ``V2_LOCAL_LISTS_REFRESH=1`` forces the same for one run).
* Stored as gzip ECSV (text; masks kept with ``serialize_method=data_mask``), never as pickle: a cache folder can come
  from someone else (a shared drive, a copied folder, a restored backup), and reading it must not be able to run code
  (2.60.7 review).  The manifest hash detects a damaged file; it is not a security check, since it sits in the same
  folder.  A failed download is remembered across processes (``archive_cache.note_source``), and two processes never
  download the same list at once (a lock file in the list's folder).
* Same answer as VizieR: the rows are those within the radius of the table's own J2000 position, in table order;
  ``_r`` is the distance in arcmin to 4 decimals as VizieR prints it; columns, dtypes, masks and units are those of
  VizieR's own table (the tables are stored as downloaded, minus ``_r``).  ``test_local_lists.py`` and the
  comparison in ``benchmark/local_lists/`` check this against live VizieR cones.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_cache  # noqa: E402

RETRY_AFTER_S = 600.0  # after a failed download the remote cone is used for this long
DOWNLOAD_RADIUS_ARCMIN = 10800.0  # 180 deg: the whole sky in one cone, every row


@dataclass(frozen=True)
class ListSpec:
    key: str
    label: str
    tables: tuple  # VizieR table ids, in the order the collector asks them
    rows: dict  # expected rows per table: the fixed edition
    ra_col: str = "RAJ2000"
    dec_col: str = "DEJ2000"
    max_age_days: float = 365.0
    terms_verified: bool = False  # the terms of use were read in the original text and allow a private copy
    terms: str = ""  # what was found, with its source (see WORK_REPORT_2026-11-25b.md)


SPECS = {
    "suh2021_agb": ListSpec(
        "suh2021_agb",
        "Suh (2021) O-rich and C-rich AGB stars, J/ApJS/256/43 tables 9-12",
        (
            "J/ApJS/256/43/table9",
            "J/ApJS/256/43/table10",
            "J/ApJS/256/43/table11",
            "J/ApJS/256/43/table12",
        ),
        {
            "J/ApJS/256/43/table9": 5908,
            "J/ApJS/256/43/table10": 3596,
            "J/ApJS/256/43/table11": 5301,
            "J/ApJS/256/43/table12": 3576,
        },
        terms="DataCite rights of DOI 10.26093/cds/vizier.22560043: 'Refer to CDS usage' (CDS licence page unreadable)",
    ),
    "roma_bzcat5": ListSpec(
        "roma_bzcat5",
        "Roma-BZCAT 5th edition, VII/274/bzcat5",
        ("VII/274/bzcat5",),
        {"VII/274/bzcat5": 3561},
        terms="acknowledge the source by citing the paper or the book (original text via an earlier read); no sentence on copies",
    ),
}

_LOCK = threading.Lock()
_KEY_LOCKS: dict[str, threading.Lock] = {}
_MEMO: dict[str, tuple] = {}  # key -> (manifest hash, {table id: astropy Table})
_FAILED: dict[str, float] = {}  # key -> monotonic time of the last failed download


def mode() -> str:
    """``auto`` (verified lists), ``all`` (every list) or ``0`` (none); ``V2_CACHE=0`` also means none."""
    if not archive_cache.enabled():
        return "0"
    v = os.environ.get("V2_LOCAL_LISTS", "auto").strip().lower() or "auto"
    if v in {"0", "false", "no", "off"}:
        return "0"
    if v in {"auto", "all"}:
        return v
    # "1", "on", "yes" read like "switch it on" but would silently mean auto (= off today): refuse (2.60.7 review)
    raise ValueError(f"V2_LOCAL_LISTS={v!r}: use auto (verified lists only), all, or 0")


def usable(spec: ListSpec) -> bool:
    m = mode()
    return m == "all" or (m == "auto" and spec.terms_verified)


def store_dir(key: str) -> Path:
    return archive_cache.root() / "lists" / key


def _log(msg: str) -> None:
    print(f"[lists] {msg}", flush=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fname(table_id: str) -> str:
    return table_id.replace("/", "_") + ".ecsv.gz"


def status(spec: ListSpec) -> dict:
    """What is on disk for the list: ``{"present": bool, "age_days": float, "stale": bool, "manifest": dict}``."""
    d = store_dir(spec.key)
    try:
        man = json.loads((d / "manifest.json").read_text())
    except (OSError, ValueError):
        return {"present": False}
    try:
        age = (time.time() - datetime.fromisoformat(man["downloaded"]).timestamp()) / 86400.0
    except (KeyError, ValueError):
        return {"present": False}
    ok = all((d / _fname(t)).is_file() for t in spec.tables) and set(man.get("tables", {})) == set(spec.tables)
    return {"present": ok, "age_days": age, "stale": age > spec.max_age_days, "manifest": man}


def _download(spec: ListSpec) -> dict:
    """Ask VizieR for every table of the list (the whole sky in one request) and store them; the manifest."""
    from _catalog_utils import vizier_query

    t0 = time.monotonic()
    total = sum(spec.rows.values())
    _log(f"first use: downloading {spec.label} ({total:,} rows) from VizieR once; kept in {store_dir(spec.key)}")
    tabs = vizier_query(list(spec.tables), 0.0, 0.0, DOWNLOAD_RADIUS_ARCMIN)
    have = set(tabs.keys())
    out = {}
    for t in spec.tables:
        if t not in have:
            raise RuntimeError(f"{t}: not in VizieR's answer")
        tb = tabs[t].copy()
        if len(tb) != spec.rows[t]:
            raise RuntimeError(f"{t}: {len(tb)} rows, the fixed edition has {spec.rows[t]}; not stored")
        if "_r" in tb.colnames:
            tb.remove_column("_r")  # distance from (0, 0): meaningless; each cone computes its own
        for c in (spec.ra_col, spec.dec_col):
            if c not in tb.colnames:
                raise RuntimeError(f"{t}: position column {c} missing (got {tb.colnames[:12]})")
        out[t] = tb
    d = store_dir(spec.key)
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for t, tb in out.items():
        path = d / _fname(t)
        _write_table(tb, path)
        back = _read_table(path)
        if not _same_table(tb, back):  # the text round trip must give back VizieR's table, else nothing is stored
            path.unlink(missing_ok=True)
            raise RuntimeError(f"{t}: the stored copy does not read back as the downloaded table; not stored")
        files[t] = {"rows": len(tb), "sha256": _sha256(path), "bytes": path.stat().st_size}
    man = {
        "list": spec.key,
        "label": spec.label,
        "source": "VizieR (CDS) " + ", ".join(spec.tables),
        "downloaded": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tables": files,
        "terms_verified": spec.terms_verified,
        "terms": spec.terms,
        "note": "stored on this computer only; delete the folder or run local_lists.py remove to drop it",
    }
    _atomic_write_text(d / "manifest.json", json.dumps(man, indent=1) + "\n")
    _log(f"downloaded {total:,} rows in {time.monotonic() - t0:.0f} s")
    return man


def _load(spec: ListSpec, man: dict) -> dict:
    d = store_dir(spec.key)
    out = {}
    for t in spec.tables:
        path = d / _fname(t)
        if _sha256(path) != man["tables"][t]["sha256"]:
            raise ValueError(f"{path.name}: does not match the manifest hash")
        out[t] = _read_table(path)  # ECSV text: reading cannot run code, whoever wrote the folder
    return out


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _write_table(tb, path: Path) -> None:
    """gzip ECSV through a unique temporary name and a rename (two processes never share a temporary file)."""
    from astropy.table import MaskedColumn

    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
            tb.write(f, format="ascii.ecsv", serialize_method={MaskedColumn: "data_mask"})
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _read_table(path: Path):
    from astropy.table import Table

    with gzip.open(path, "rt", encoding="utf-8") as f:
        return Table.read(f.read(), format="ascii.ecsv")


def _same_table(a, b) -> bool:
    """Same columns, dtypes, values and masks (what a collector reads through ``to_pandas``)."""
    if a.colnames != b.colnames or len(a) != len(b):
        return False
    for c in a.colnames:
        x, y = a[c], b[c]
        if x.dtype != y.dtype:
            return False
        mx = np.ma.getmaskarray(x) if hasattr(x, "mask") else np.zeros(len(x), bool)
        my = np.ma.getmaskarray(y) if hasattr(y, "mask") else np.zeros(len(y), bool)
        if not np.array_equal(mx, my):
            return False
        vx, vy = np.asarray(x)[~mx], np.asarray(y)[~my]
        if vx.dtype.kind == "f":
            if not np.array_equal(vx, vy, equal_nan=True):
                return False
        elif not np.array_equal(vx, vy):
            return False
    return True


def _tables(spec: ListSpec):
    """The stored tables ({id: astropy Table}), downloading or re-downloading when needed; None: use VizieR."""
    with _LOCK:
        lock = _KEY_LOCKS.setdefault(spec.key, threading.Lock())
    with lock:  # one download per list even when several collectors start together
        st = status(spec)
        memo = _MEMO.get(spec.key)
        if memo is not None and st.get("present") and not st.get("stale") and memo[0] == st["manifest"]["downloaded"]:
            return memo[1]
        failed = _FAILED.get(spec.key)
        if failed is not None and time.monotonic() - failed < RETRY_AFTER_S:
            return None
        if archive_cache.source_down(_source_key(spec)):  # a failure in another process (the app: one per search)
            return None
        try:
            store_dir(spec.key).mkdir(parents=True, exist_ok=True)
            with _HeldLock(store_dir(spec.key) / ".lock", timeout=300.0):  # one process downloads
                tabs, st = _tables_locked(spec)
        except Exception as exc:
            _FAILED[spec.key] = time.monotonic()
            archive_cache.note_source(_source_key(spec), False, RETRY_AFTER_S)
            _log(f"{spec.label}: no local copy ({type(exc).__name__}: {str(exc)[:160]}); VizieR is asked for each cone")
            _MEMO.pop(spec.key, None)
            return None
        _MEMO[spec.key] = (st["manifest"]["downloaded"], tabs)
        return tabs


class _HeldLock:
    """``archive_cache._FileLock`` renewed while held (2.60.7 review, Codex): that lock is broken as stale after
    ``LOCK_STALE_S`` (30 s) without a touch, and a download can take longer (VizieR mirror failover).  A thread touches
    the lock file every quarter of that time, so a live holder keeps it; a crashed one still frees it after 30 s."""

    def __init__(self, path: Path, timeout: float):
        self.path, self._lock = path, archive_cache._FileLock(path, timeout=timeout)
        self._stop = threading.Event()
        self._beat = None

    def __enter__(self):
        self._lock.__enter__()

        def beat():
            while not self._stop.wait(max(0.05, archive_cache.LOCK_STALE_S / 4)):
                try:
                    os.utime(self.path, None)
                except OSError:
                    pass

        self._beat = threading.Thread(target=beat, daemon=True, name="lists-lock")
        self._beat.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._beat.join(timeout=5)
        return self._lock.__exit__(*exc)


def _source_key(spec: ListSpec) -> str:
    return f"lists:{spec.key}"


def _tables_locked(spec: ListSpec):
    """(tables, status) under the list's lock file: load the copy, or (re)download it; raises when neither works."""
    st = status(spec)  # read again: another process may have just written it
    need = not st.get("present") or st.get("stale") or os.environ.get("V2_LOCAL_LISTS_REFRESH") == "1"
    if st.get("present") and st.get("stale"):
        _log(f"{spec.label}: the copy is {st['age_days']:.0f} days old (limit {spec.max_age_days:.0f}), asking again")
    tabs = None
    if not need:
        try:
            tabs = _load(spec, st["manifest"])
        except Exception as exc:  # a damaged or unreadable file: the copy is rebuilt, not trusted
            _log(f"{spec.label}: the local copy is damaged ({type(exc).__name__}: {str(exc)[:100]}), downloading again")
            need = True
    if need:
        st = {"manifest": _download(spec)}
        tabs = _load(spec, st["manifest"])
    archive_cache.note_source(_source_key(spec), True)  # forget an earlier failure
    return tabs, st


def _separation_arcmin(ra1, dec1, ra2, dec2) -> np.ndarray:
    """Great-circle distance in arcmin (haversine); degrees in."""
    r1, d1, r2, d2 = (np.radians(np.asarray(x, dtype=float)) for x in (ra1, dec1, ra2, dec2))
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin((r2 - r1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))) * 60.0


_POS: dict[int, tuple] = {}  # id(table) -> (ra, dec) in degrees, parsed once


def positions(spec: ListSpec, tb):
    """J2000 positions of a stored table in degrees.  A column holding degrees is used as it is; a column of
    sexagesimal strings (Roma-BZCAT: ``12 24 54.46`` / ``+21 22 46.4``) is parsed at full double precision, which is
    the position VizieR measures its distance ``_r`` from."""
    hit = _POS.get(id(tb))
    if hit is not None and hit[0] is tb:
        return hit[1], hit[2]
    cols = []
    for name, unit in ((spec.ra_col, "hourangle"), (spec.dec_col, "deg")):
        col = tb[name]
        if col.dtype.kind in "US":
            from astropy.coordinates import Angle

            txt = np.ma.filled(col.astype(str), "")
            ok = np.array([bool(x.strip()) for x in txt])
            vals = np.full(len(txt), np.nan)
            if ok.any():
                parsed = Angle([x.strip() for x in txt[ok]], unit=unit)
                vals[ok] = parsed.degree
            cols.append(vals)
        else:
            cols.append(np.asarray(np.ma.filled(col.astype(float), np.nan), dtype=float))
    _POS[id(tb)] = (tb, cols[0], cols[1])
    return cols[0], cols[1]


def cone_from(spec: ListSpec, tables: dict, ra: float, dec: float, radius_arcmin: float):
    """The cone search of stored tables, shaped like VizieR's answer (see the module docstring)."""
    from astropy.table import MaskedColumn
    from astroquery.utils import TableList

    out = []
    for t in spec.tables:
        tb = tables[t]
        tra, tdec = positions(spec, tb)
        sep = _separation_arcmin(ra, dec, tra, tdec)
        keep = np.isfinite(sep) & (sep <= float(radius_arcmin))
        if not keep.any():
            continue  # VizieR leaves a table without rows out of its answer
        sub = tb[keep]
        if "_r" in sub.colnames:  # a table stored with VizieR's own distance column: it is recomputed for this cone
            sub.remove_column("_r")
        sub.add_column(MaskedColumn(np.round(sep[keep], 4), name="_r", mask=np.zeros(int(keep.sum()), bool)), index=0)
        out.append((t, sub))
    return TableList(out)


def cone(key: str, ra: float, dec: float, radius_arcmin: float):
    """VizieR-shaped answer for the list ``key`` from the local copy, or None (disabled, or no copy: ask VizieR)."""
    spec = SPECS[key]
    if not usable(spec):
        return None
    tables = _tables(spec)
    if tables is None:
        return None
    try:
        return cone_from(spec, tables, ra, dec, radius_arcmin)
    except (
        Exception
    ) as exc:  # whatever is wrong with the copy must not fail the collector: ask VizieR, as without the copy
        with _LOCK:
            _FAILED[spec.key] = time.monotonic()
            _MEMO.pop(spec.key, None)
        _log(f"{spec.label}: the local copy could not answer ({type(exc).__name__}: {str(exc)[:120]}); VizieR is asked")
        return None


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["status", "refresh", "remove"])
    ap.add_argument("key", nargs="?", choices=sorted(SPECS))
    a = ap.parse_args()
    keys = [a.key] if a.key else sorted(SPECS)
    for k in keys:
        spec = SPECS[k]
        if a.action == "status":
            st = status(spec)
            used = "used" if usable(spec) else "not used (terms not verified; V2_LOCAL_LISTS=all to use)"
            if st.get("present"):
                print(
                    f"{k}: present, {st['age_days']:.0f} days old (limit {spec.max_age_days:.0f}), {used}; {store_dir(k)}"
                )
            else:
                print(f"{k}: no local copy, {used}")
        elif a.action == "refresh":
            print(json.dumps(_download(spec), indent=1)[:400])
        else:
            d = store_dir(k)
            for p in sorted(d.glob("*")) if d.is_dir() else []:
                p.unlink()
            if d.is_dir():
                d.rmdir()
            print(f"{k}: removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

"""Row-access helpers shared by the sub-class classifier and the axes.

The Classifier modules are loaded by file path (``importlib``) from the
controllers, the pipeline, the benchmarks and the tests, not imported as a
package, so each consumer executes this small file itself (three lines, as
it did for ``simbad_otypes.py`` before).  The part worth sharing, the SIMBAD
otype hierarchy with its cached table, is loaded once per process by
``load`` and kept in ``sys.modules``.
"""

from __future__ import annotations
import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str, path: Path):
    """The module at ``path`` (absolute), executed once per process (cached as ``name``)."""
    m = sys.modules.get(name)
    if m is not None and getattr(m, "__file__", None) == str(path):
        return m
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.modules[name] = m
    return m


OTYPES = load("v2_simbad_otypes", ROOT / "simbad_otypes.py")


def num(row, *keys):
    """First finite float among ``keys``, else None (missing / NaN / text)."""
    for k in keys:
        try:
            x = float(row.get(k))
        except Exception:
            continue
        if math.isfinite(x):
            return x
    return None


def text(row, key):
    """Stripped string, or None for a missing / empty / "nan" value.  Unlike
    ``clean_text`` it keeps "None" and "<NA>" (the axes' historical rule)."""
    v = row.get(key)
    if v is None:
        return None
    v = str(v).strip()
    return None if not v or v.lower() == "nan" else v


def clean_text(row, *keys):
    """First non-empty string among ``keys``; NaN, "nan", "none" and "<NA>" count as missing."""
    for k in keys:
        v = row.get(k)
        if v is None or (isinstance(v, float) and v != v):
            continue
        s = str(v).strip()
        if s and s.lower() not in {"nan", "none", "<na>"}:
            return s
    return None


def flag(row, key):
    """Boolean catalogue flag: True / "1" / "1.0" / "true" / "t" / "yes"."""
    v = row.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "1.0", "true", "t", "yes"}


_ABSENT = object()


def axis_result(axis, label, confidence, status, evidence, subtype=_ABSENT):
    """One axis result with the keys axis, label, [subtype,] confidence,
    status, evidence in this order; ``subtype`` only when given (the axes
    without a leaf never had the key)."""
    out = {"axis": axis, "label": label}
    if subtype is not _ABSENT:
        out["subtype"] = subtype
    out["confidence"] = confidence
    out["status"] = status
    out["evidence"] = evidence
    return out

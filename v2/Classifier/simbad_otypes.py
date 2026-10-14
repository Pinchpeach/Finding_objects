"""SIMBAD object-type hierarchy (2.22.0).

SIMBAD returns the most specific type code (``cC*`` classical Cepheid,
``BLL`` BL Lac, ``Mi*`` Mira, ...), while the rules map a few general codes.
``resolve`` walks a code's lineage (``reference/simbad_otypedef.csv``: the
``path`` column of SIMBAD's ``otypedef`` table, fetched by
benchmark/new_targets/probe_catalogs.py) from the specific code to the root
and returns the first mapped one, so every child type inherits its parent's
class.  Candidate codes (``is_candidate``, e.g. ``Ce?``) are not resolved
unless asked: a candidate type is not a curated classification.
"""

from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "reference" / "simbad_otypedef.csv"


@lru_cache(maxsize=1)
def _table() -> dict:
    out = {}
    try:
        with open(TABLE, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                path = [p.strip() for p in (r.get("path") or "").split(">") if p.strip()]
                out[r["otype"].strip()] = (path[::-1], str(r.get("is_candidate", "0")).strip() in ("1", "1.0", "True"))
    except OSError:
        pass
    return out


def lineage(code, allow_candidate: bool = False) -> list:
    """Codes from ``code`` up to the root; [] for a candidate (unless allowed)
    and [code] for a code missing from the table."""
    c = str(code or "").strip()
    if not c or c.lower() == "nan":
        return []
    hit = _table().get(c)
    if hit is None:
        return [c]
    path, cand = hit
    if cand and not allow_candidate:
        return []
    return ([c] + path) if cand else path


def resolve(code, mapping: dict, allow_candidate: bool = False):
    """(mapped value, matched code) for the most specific mapped code, else (None, None)."""
    for c in lineage(code, allow_candidate):
        if c in mapping:
            return mapping[c], c
    return None, None


def is_a(code, ancestor: str) -> bool:
    return ancestor in lineage(code)

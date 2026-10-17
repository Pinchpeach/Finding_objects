"""Bookmarked objects, kept in one JSON file per user (2.23.0).

A bookmark is a snapshot of one classified object -- name, position, classes
and the results file it came from -- plus a free-text note, so it stays
useful after the run folder is moved or deleted.  Qt-free, so the store can
be tested and used without the GUI.

Location (one per user, next to the log file of app_log.py):
  Windows  %LOCALAPPDATA%\\FindingObjects\\bookmarks.json
  macOS    ~/Library/Application Support/FindingObjects/bookmarks.json
  Linux    $XDG_DATA_HOME/finding_objects/bookmarks.json (~/.local/share)
``FINDING_OBJECTS_BOOKMARKS`` overrides the path (tests, portable use).

Writes go to a temporary file that replaces the old one, so a crash cannot
leave a half-written file.  An unreadable file is kept as ``*.corrupt`` and
the store starts empty instead of failing.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path

from app_paths import user_file

FILE_NAME = "bookmarks.json"
SCHEMA = 1
# Two bookmarks closer than this, without names that tell them apart, are
# the same object (Gaia-level positions agree to far better than 1").
SAME_POSITION_ARCSEC = 1.0

# Snapshot fields copied from a results row; the first present one wins.
FIELDS = {
    "name": ("designation", "object_name", "object_id"),
    "ra": ("ra",),
    "dec": ("dec",),
    "primary_class": ("primary_class",),
    "confidence": ("primary_confidence",),
    "subclass": ("subclass",),
    "physical": ("physical_class",),
    "variability": ("variability_class",),
    "compact": ("compact_class",),
    "extragalactic": ("extragalactic_class",),
    "phenomenon": ("phenomenon_class",),
    "object_id": ("object_id",),
}


def default_path() -> Path:
    return user_file(FILE_NAME, "FINDING_OBJECTS_BOOKMARKS", "Application Support", "XDG_DATA_HOME", ".local/share")


def _clean(value):
    """JSON-safe scalar: NaN / None / pandas NA -> None, numpy -> Python."""
    if value is None:
        return None
    try:
        if value != value:  # NaN, pandas NA raises TypeError below
            return None
    except TypeError:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600.0


class BookmarkStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_path()
        self.items: list[dict] = []
        self.load()

    # ------------------------------------------------------------ file
    def load(self) -> list[dict]:
        self.items = []
        if not self.path.exists():
            return self.items
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("bookmarks", []) if isinstance(data, dict) else data
            self.items = [b for b in items if isinstance(b, dict) and b.get("id")]
        except (OSError, ValueError):
            try:  # keep the unreadable file for the user, start empty
                os.replace(self.path, self.path.with_suffix(".json.corrupt"))
            except OSError:
                pass
        return self.items

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        payload = {"schema": SCHEMA, "bookmarks": self.items}
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ queries
    def find(self, row) -> dict | None:
        """The bookmark of this object: same name, else same position."""
        snap = self.snapshot(row)
        for b in self.items:
            if snap["name"] and b.get("name") == snap["name"]:
                return b
        if snap["ra"] is None or snap["dec"] is None:
            return None
        for b in self.items:
            if b.get("ra") is None or b.get("dec") is None:
                continue
            same_place = _sep_arcsec(snap["ra"], snap["dec"], b["ra"], b["dec"]) < SAME_POSITION_ARCSEC
            if same_place and (not snap["name"] or not b.get("name")):
                return b
        return None

    def get(self, bookmark_id: str) -> dict | None:
        return next((b for b in self.items if b["id"] == bookmark_id), None)

    # ------------------------------------------------------------ changes
    @staticmethod
    def snapshot(row, source: str | None = None) -> dict:
        get = row.get if hasattr(row, "get") else (lambda k, d=None: d)
        snap = {}
        for key, columns in FIELDS.items():
            snap[key] = next((v for v in (_clean(get(c)) for c in columns) if v is not None), None)
        for key in ("ra", "dec", "confidence"):
            try:
                snap[key] = None if snap[key] is None else float(snap[key])
            except (TypeError, ValueError):
                snap[key] = None
        if source:
            snap["source"] = str(source)
        return snap

    def add(self, row, source: str | None = None, note: str = "") -> dict:
        """Bookmark a results row; an existing bookmark of the same object is
        refreshed (classes, source) and keeps its note and date."""
        snap = self.snapshot(row, source)
        old = self.find(row)
        if old is not None:
            old.update({k: v for k, v in snap.items() if v is not None})
            self.save()
            return old
        item = {"id": uuid.uuid4().hex, **snap, "note": note, "added": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.items.append(item)
        self.save()
        return item

    def remove(self, bookmark_id: str) -> bool:
        n = len(self.items)
        self.items = [b for b in self.items if b["id"] != bookmark_id]
        if len(self.items) != n:
            self.save()
            return True
        return False

    def toggle(self, row, source: str | None = None) -> bool:
        """Add when absent, remove when present; True if now bookmarked."""
        old = self.find(row)
        if old is not None:
            self.remove(old["id"])
            return False
        self.add(row, source)
        return True

    def set_note(self, bookmark_id: str, note: str) -> None:
        b = self.get(bookmark_id)
        if b is not None and b.get("note", "") != note:
            b["note"] = note
            self.save()

    # ------------------------------------------------------------ export
    def to_frame(self):
        import pandas as pd

        cols = [
            "name",
            "ra",
            "dec",
            "primary_class",
            "confidence",
            "subclass",
            "physical",
            "variability",
            "compact",
            "extragalactic",
            "phenomenon",
            "note",
            "added",
            "source",
            "object_id",
        ]
        return pd.DataFrame([{c: b.get(c) for c in cols} for b in self.items], columns=cols)

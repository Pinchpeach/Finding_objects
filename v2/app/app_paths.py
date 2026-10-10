"""Locate the v2 package both from a source checkout and from a PyInstaller
bundle (where data files live under ``sys._MEIPASS``)."""
from __future__ import annotations
import sys
from pathlib import Path


def v2_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "v2"
    return Path(__file__).resolve().parents[1]


def version() -> str:
    """The v2 release recorded in ``v2/VERSION`` (see ``v2/CHANGELOG.md``)."""
    try:
        return (v2_root() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"

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


def load_v2(relative: str):
    """Import a v2 module by its path relative to ``v2/`` (once; common.load_module)."""
    root = v2_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from common import load_module

    return load_module(root / relative)

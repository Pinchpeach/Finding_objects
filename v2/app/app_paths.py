"""Locate the v2 package both from a source checkout and from a PyInstaller
bundle (where data files live under ``sys._MEIPASS``), and the per-user files
of the app (log, bookmarks)."""

from __future__ import annotations
import os
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


def user_file(name: str, env: str, mac_dir: str, xdg_var: str, xdg_default: str) -> Path:
    """Per-user file of the app: ``$env`` when set, else
    Windows  %LOCALAPPDATA%\\FindingObjects\\<name>
    macOS    ~/Library/<mac_dir>/FindingObjects/<name>
    Linux    $<xdg_var>/finding_objects/<name> (~/<xdg_default> when unset)"""
    override = os.environ.get(env)
    if override:
        return Path(override).expanduser()
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "FindingObjects"
    elif sys.platform == "darwin":
        base = home / "Library" / mac_dir / "FindingObjects"
    else:
        base = Path(os.environ.get(xdg_var) or home / xdg_default) / "finding_objects"
    return base / name

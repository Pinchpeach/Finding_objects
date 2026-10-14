"""One persistent log file for the desktop app (2.21.0).

Every run appends to the same file instead of creating a new one: a run
header line, then the pipeline output with timestamps.  The file is opened in
append mode for every write, so a missing file (first start, or deleted while
the app is open) is simply created again.  Qt-free so it can be tested and
reused by the pipeline worker.

Location (one per user):
  Windows  %LOCALAPPDATA%\\FindingObjects\\finding_objects.log
  macOS    ~/Library/Logs/FindingObjects/finding_objects.log
  Linux    $XDG_STATE_HOME/finding_objects/finding_objects.log (~/.local/state)
``FINDING_OBJECTS_LOG`` overrides the path (tests, portable use).

The file is kept to about MAX_BYTES: when a run starts and the file is
larger, its oldest part is dropped (the same file is rewritten, no rotated
copies), so it cannot grow without bound over months of use.
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path

LOG_NAME = "finding_objects.log"
MAX_BYTES = 5_000_000
KEEP_BYTES = 2_000_000
RUN_MARK = "=" * 20


def default_path() -> Path:
    env = os.environ.get("FINDING_OBJECTS_LOG")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "FindingObjects"
    elif sys.platform == "darwin":
        base = home / "Library" / "Logs" / "FindingObjects"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or home / ".local" / "state") / "finding_objects"
    return base / LOG_NAME


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class AppLog:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_path()

    def ensure(self) -> Path:
        """Create the folder and an empty file when they do not exist."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        return self.path

    def write_lines(self, lines) -> None:
        """Append lines with a timestamp; never raises (logging must not stop a run)."""
        lines = [str(x).rstrip("\r\n") for x in lines]
        if not lines:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            t = _stamp()
            with open(self.path, "a", encoding="utf-8", newline="\n") as fh:  # "a" creates a missing file
                fh.write("".join(f"{t}  {x}\n" for x in lines))
        except OSError:
            pass

    def write(self, text: str) -> None:
        self.write_lines(str(text).split("\n"))

    def start_run(self, header: str) -> None:
        self.trim()
        self.write_lines([f"{RUN_MARK} {header} {RUN_MARK}"])

    def trim(self, max_bytes: int = MAX_BYTES, keep_bytes: int = KEEP_BYTES) -> None:
        """Drop the oldest part when the file exceeds ``max_bytes`` (cut at a line start)."""
        try:
            if not self.path.exists() or self.path.stat().st_size <= max_bytes:
                return
            with open(self.path, "rb") as fh:
                fh.seek(-keep_bytes, os.SEEK_END)
                tail = fh.read()
            cut = tail.find(b"\n")
            tail = tail[cut + 1 :] if cut >= 0 else tail
            tmp = self.path.with_suffix(".log.tmp")
            tmp.write_bytes(
                f"{_stamp()}  (older entries removed to keep the log under {max_bytes // 1_000_000} MB)\n".encode()
                + tail
            )
            os.replace(tmp, self.path)
        except OSError:
            pass

    def read_tail(self, max_bytes: int = KEEP_BYTES) -> str:
        """Last ``max_bytes`` of the log (whole lines), creating the file if missing."""
        try:
            self.ensure()
            size = self.path.stat().st_size
            with open(self.path, "rb") as fh:
                if size > max_bytes:
                    fh.seek(-max_bytes, os.SEEK_END)
                data = fh.read()
            if size > max_bytes:
                data = data[data.find(b"\n") + 1 :]
            return data.decode("utf-8", "replace")
        except OSError as exc:
            return f"(log file unavailable: {exc})"

    def clear(self) -> None:
        try:
            self.ensure()
            self.path.write_text("", encoding="utf-8")
        except OSError:
            pass

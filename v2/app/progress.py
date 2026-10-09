"""Turn the pipeline's log lines into progress (no Qt dependency, unit-testable).

The pipeline prints one line per finished archive query
(``[gaia_dr3] ok: 114 rows (33.2 s)``) and one per finished stage
(``[pipeline] 3_features: 0.81 s``); progress is the fraction of those done.
"""
from __future__ import annotations
import re

STAGES = ("1_associate", "2_integrate", "3_features", "4_evidence", "5_coarse", "6_prepare", "7_classify")
_COLLECTOR = re.compile(r"^\[(?P<name>[A-Za-z0-9_]+)\] (?P<status>ok|empty|error|timeout)\b")
_STAGE = re.compile(r"^\[pipeline\] (?P<stage>[0-9a-z_]+): (?P<sec>[0-9.]+) s")


def collector_count() -> int:
    try:
        import importlib.util, sys
        from pathlib import Path
        from app_paths import v2_root
        p = v2_root() / "Get_data" / "controller.py"
        sys.path.insert(0, str(p.parent))
        spec = importlib.util.spec_from_file_location("v2_controller_for_count", p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return len(m.COLLECTORS)
    except Exception:
        return 23


class ProgressTracker:
    def __init__(self, collecting: bool, n_collectors: int | None = None):
        self.n_collectors = (n_collectors if n_collectors is not None else collector_count()) if collecting else 0
        self.total = self.n_collectors + len(STAGES)
        self.done_collectors: dict[str, str] = {}
        self.done_stages: dict[str, float] = {}

    def feed(self, line: str) -> str | None:
        """Consume one log line; return a short human-readable status if it advanced."""
        line = line.strip()
        m = _STAGE.match(line)
        if m:
            stage = m["stage"]
            if stage in STAGES:
                self.done_stages[stage] = float(m["sec"])
                return f"stage {stage} done ({m['sec']} s)"
            return None
        m = _COLLECTOR.match(line)
        if m and m["name"] != "pipeline" and self.n_collectors:
            self.done_collectors[m["name"]] = m["status"]
            return f"{m['name']}: {m['status']}"
        return None

    @property
    def fraction(self) -> float:
        done = min(len(self.done_collectors), self.n_collectors) + len(self.done_stages)
        return done / self.total if self.total else 1.0

    @property
    def failed_archives(self) -> list[str]:
        return sorted(k for k, v in self.done_collectors.items() if v in ("error", "timeout"))

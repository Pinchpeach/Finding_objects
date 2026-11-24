#!/usr/bin/env python3
"""Requests and time per collector from a ``V2_HTTP_LOG=1`` run (2.60.0).

Every archive request waits 3-5 s first (``Get_data/throttle.py``, project rule 2.33.0), so what a collector costs
is mostly its number of requests.  ``pipeline.py`` run with ``V2_HTTP_LOG=1`` prints one ``[http]`` line per request
(``[http] <collector>[/<helper>] <host> <outcome> <seconds>s``; helper threads of a collector carry its name since
2.60.0, the Gaia TAP client's ``http.client`` requests are in the log since 2.60.0).  This script counts them.

    python v2/benchmark/request_counts.py LOG [LOG ...] [--work DIR ...] [--md]

``LOG``     the console output of a run (several: one row set per log, labelled by the file name without suffix)
``--work``  the pipeline's ``--work`` directory of the same run, one per log in the same order: its
            ``collection_summary_*.csv`` gives each collector's elapsed seconds and rows
``--whatif host=seconds,...``  calculation only (nothing in the pipeline changes): the collection time if the pause
            before a request to ``host`` were that many seconds instead of the 3-5 s (mean 4.0 s).  Each collector's
            elapsed time falls by its requests to the host x (4.0 - seconds); the collection time is the
            list-scheduling makespan of the collectors, in controller order, on ``--workers`` threads (6, the
            pipeline's default) -- the way controller._run_bounded hands out collectors.  The model is first
            compared with the measured collection time (``--measured``).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

LINE = re.compile(r"^\[http\] (\S+) (\S+) (.*?) ([0-9.]+)s$")


def parse(log: Path) -> pd.DataFrame:
    rows = []
    for line in log.read_text(errors="replace").splitlines():
        m = LINE.match(line)
        if m:
            name, host, outcome, sec = m.groups()
            rows.append(
                {"collector": name.split("/")[0], "thread": name, "host": host, "outcome": outcome, "s": float(sec)}
            )
    return pd.DataFrame(rows, columns=["collector", "thread", "host", "outcome", "s"])


def summary(work: Path) -> pd.DataFrame:
    files = sorted(work.rglob("collection_summary_*.csv"))
    if not files:
        return pd.DataFrame(columns=["collector", "status", "rows", "elapsed_seconds"])
    return pd.read_csv(files[0])[["collector", "status", "rows", "elapsed_seconds"]]


def table(log: Path, work: Path | None) -> pd.DataFrame:
    h = parse(log)
    by = defaultdict(Counter)
    for r in h.itertuples():
        by[r.collector][r.host] += 1
    out = pd.DataFrame(
        {
            "collector": list(by),
            "requests": [sum(c.values()) for c in by.values()],
            "hosts": [", ".join(f"{k} x{v}" for k, v in c.most_common()) for c in by.values()],
        }
    )
    if work is not None:
        out = out.merge(summary(work), on="collector", how="outer")
    out["requests"] = out["requests"].fillna(0).astype(int)
    out["hosts"] = out["hosts"].fillna("")
    out["pause_s_at_4"] = out["requests"] * 4.0  # mean of the 3-5 s pause
    sort = "elapsed_seconds" if "elapsed_seconds" in out else "requests"
    return out.sort_values(sort, ascending=False).reset_index(drop=True)


MEAN_PAUSE_S = (3.0 + 5.0) / 2


def makespan(times: list[float], workers: int = 6) -> float:
    """Time until the last collector ends when ``times`` (controller order) go to the first free of ``workers``."""
    free = [0.0] * max(1, workers)
    for t in times:
        i = min(range(len(free)), key=free.__getitem__)
        free[i] += float(t)
    return max(free) if times else 0.0


def whatif(log: Path, work: Path, pauses: dict[str, float], workers: int = 6) -> dict:
    """{"model_s": makespan of the measured elapsed times, "whatif_s": with the pauses of ``pauses`` per host}."""
    h = parse(log)
    s = summary(work)
    n = h.groupby(["collector", "host"]).size()
    new = []
    for r in s.itertuples():
        cut = sum(int(n.get((r.collector, host), 0)) * max(0.0, MEAN_PAUSE_S - p) for host, p in pauses.items())
        new.append(max(0.0, float(r.elapsed_seconds) - cut))
    base = [float(x) for x in s.elapsed_seconds]
    return {"model_s": makespan(base, workers), "whatif_s": makespan(new, workers), "collectors": list(s.collector)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("logs", nargs="+", type=Path)
    p.add_argument("--work", nargs="*", type=Path, default=[])
    p.add_argument("--md", action="store_true", help="markdown table")
    p.add_argument("--whatif", default="", help="host=seconds,host=seconds: a calculation, see above")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--measured", type=float, nargs="*", default=[], help="measured collection seconds per log")
    a = p.parse_args()
    pauses = {k: float(v) for k, v in (kv.split("=") for kv in a.whatif.split(",") if kv)}
    for i, log in enumerate(a.logs):
        t = table(log, a.work[i] if i < len(a.work) else None)
        print(f"\n## {log.stem}: {int(t.requests.sum())} requests")
        print(t.to_markdown(index=False) if a.md else t.to_string(index=False))
        if pauses and i < len(a.work):
            w = whatif(log, a.work[i], pauses, a.workers)
            m = f" (measured {a.measured[i]:.1f} s)" if i < len(a.measured) else ""
            print(
                f"collection time, list-scheduling model: {w['model_s']:.1f} s{m}; with pauses {pauses}: {w['whatif_s']:.1f} s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
